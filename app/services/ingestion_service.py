from datetime import datetime
from typing import Optional
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import WaveformUploadStatus
from ..repository import (
    WaveformRepository,
    WaveformBinaryParser,
    resolve_ship_and_point,
)
from ..middleware.exceptions import BusinessException, WaveformIngestionException
from ..middleware.error_codes import ErrorCode
from ..logging_config.logger import logger, save_failed_waveform


class WaveformIngestionService:
    def __init__(self, mysql_db: AsyncSession, timescale_db: AsyncSession):
        self.mysql_db = mysql_db
        self.timescale_db = timescale_db
        self.waveform_repo = WaveformRepository(timescale_db)
        self.parser = WaveformBinaryParser()

    async def init_upload_session(
        self,
        ship_code: str,
        point_code: str,
        batch_id: str,
        total_segments: int,
        total_samples: int,
        sample_rate: float,
        start_time: datetime,
    ) -> dict:
        ship, point = await resolve_ship_and_point(self.mysql_db, ship_code, point_code)

        existing = await self.waveform_repo.get_upload_session(batch_id)
        if existing:
            return {
                "batch_id": batch_id,
                "ship_id": existing.ship_id,
                "point_id": existing.point_id,
                "received_segments": existing.received_segments,
                "total_segments": existing.total_segments,
                "status": existing.status,
            }

        session = await self.waveform_repo.create_upload_session(
            batch_id=batch_id,
            ship_id=ship.id,
            point_id=point.id,
            total_segments=total_segments,
            total_samples=total_samples,
            sample_rate=sample_rate,
            start_time=start_time,
        )
        await self.timescale_db.commit()
        return {
            "batch_id": batch_id,
            "ship_id": session.ship_id,
            "point_id": session.point_id,
            "received_segments": 0,
            "total_segments": total_segments,
            "status": 0,
        }

    async def ingest_segment(
        self,
        ship_code: str,
        point_code: str,
        batch_id: str,
        segment_index: int,
        total_segments: int,
        sample_offset: int,
        sample_count: int,
        start_time: datetime,
        sample_rate: float,
        binary_data: bytes,
        byte_order: str = "little",
        dtype: str = "float32",
    ) -> dict:
        ship, point = await resolve_ship_and_point(self.mysql_db, ship_code, point_code)

        session = await self.waveform_repo.get_upload_session(batch_id)
        if not session:
            session = await self.waveform_repo.create_upload_session(
                batch_id=batch_id,
                ship_id=ship.id,
                point_id=point.id,
                total_segments=total_segments,
                total_samples=sample_offset + sample_count,
                sample_rate=sample_rate,
                start_time=start_time,
            )

        try:
            waveform_data = self.parser.parse(binary_data, dtype=dtype, byte_order=byte_order)
            self.parser.validate(waveform_data, expected_count=sample_count)
        except WaveformIngestionException as e:
            await self.waveform_repo.mark_session_complete(batch_id, status=2, error_msg=str(e))
            await self.timescale_db.commit()
            save_failed_waveform(batch_id, binary_data, metadata={
                "segment_index": segment_index,
                "ship_code": ship_code,
                "point_code": point_code,
                "error": str(e),
            })
            raise

        try:
            dt = 1.0 / sample_rate
            segment_end_time = datetime.fromtimestamp(
                start_time.timestamp() + sample_count * dt
            )

            inserted = await self.waveform_repo.bulk_insert_waveforms(
                ship_id=ship.id,
                point_id=point.id,
                start_time=start_time,
                sample_rate=sample_rate,
                amplitudes=waveform_data,
                batch_id=batch_id,
                sample_offset=sample_offset,
            )

            updated_session = await self.waveform_repo.update_upload_session_progress(
                batch_id=batch_id,
                samples_added=inserted,
                segment_time_end=segment_end_time,
            )

            all_done = (
                updated_session
                and updated_session.received_segments >= updated_session.total_segments
            )
            if all_done:
                await self.waveform_repo.mark_session_complete(batch_id, status=1)

            await self.timescale_db.commit()

            return {
                "batch_id": batch_id,
                "inserted_points": inserted,
                "segment_index": segment_index,
                "received_segments": updated_session.received_segments if updated_session else 1,
                "total_segments": total_segments,
                "complete": all_done,
            }
        except Exception as e:
            await self.timescale_db.rollback()
            await self.waveform_repo.mark_session_complete(
                batch_id, status=2, error_msg=str(e)
            )
            await self.timescale_db.commit()
            save_failed_waveform(batch_id, binary_data, metadata={
                "segment_index": segment_index,
                "ship_code": ship_code,
                "point_code": point_code,
                "error": str(e),
            })
            raise WaveformIngestionException(
                ErrorCode.INGESTION_FAILED,
                f"分段写入失败: {str(e)}",
            )

    async def get_upload_status(self, batch_id: str) -> WaveformUploadStatus:
        session = await self.waveform_repo.get_upload_session(batch_id)
        if not session:
            raise BusinessException(ErrorCode.BATCH_NOT_FOUND)
        return WaveformUploadStatus(
            batch_id=session.batch_id,
            received_segments=session.received_segments,
            total_segments=session.total_segments,
            received_samples=session.total_samples if session.status == 1 else 0,
            total_samples=session.total_samples,
            status=session.status,
            error_message=session.error_message,
        )
