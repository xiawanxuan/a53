from datetime import datetime, timedelta
from typing import Optional, List
import numpy as np
from sqlalchemy import select, text, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import VibrationWaveform, WaveformUploadSession
from ..config.settings import settings
from ..config.yaml_config import yaml_config
from ..middleware.exceptions import WaveformIngestionException, BusinessException
from ..middleware.error_codes import ErrorCode
from ..logging_config.logger import logger


class WaveformRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_upload_session(
        self,
        batch_id: str,
        ship_id: int,
        point_id: int,
        total_segments: int,
        total_samples: int,
        sample_rate: float,
        start_time: datetime,
    ) -> WaveformUploadSession:
        session = WaveformUploadSession(
            batch_id=batch_id,
            ship_id=ship_id,
            point_id=point_id,
            total_segments=total_segments,
            received_segments=0,
            total_samples=total_samples,
            sample_rate=sample_rate,
            start_time=start_time,
            status=0,
        )
        self.db.add(session)
        await self.db.flush()
        logger.info(f"Created upload session: batch_id={batch_id}")
        return session

    async def get_upload_session(self, batch_id: str) -> Optional[WaveformUploadSession]:
        result = await self.db.execute(
            select(WaveformUploadSession).where(WaveformUploadSession.batch_id == batch_id)
        )
        return result.scalar_one_or_none()

    async def update_upload_session_progress(
        self,
        batch_id: str,
        samples_added: int,
        segment_time_end: Optional[datetime] = None,
    ) -> Optional[WaveformUploadSession]:
        session = await self.get_upload_session(batch_id)
        if not session:
            return None
        session.received_segments += 1
        if segment_time_end:
            session.end_time = segment_time_end
        await self.db.flush()
        return session

    async def mark_session_complete(self, batch_id: str, status: int = 1, error_msg: str = None) -> None:
        session = await self.get_upload_session(batch_id)
        if session:
            session.status = status
            if error_msg:
                session.error_message = error_msg
            await self.db.flush()

    async def bulk_insert_waveforms(
        self,
        ship_id: int,
        point_id: int,
        start_time: datetime,
        sample_rate: float,
        amplitudes: np.ndarray,
        batch_id: str,
        sample_offset: int = 0,
    ) -> int:
        if amplitudes.size == 0:
            raise WaveformIngestionException(ErrorCode.WAVEFORM_EMPTY)

        batch_size = settings.app.batch_insert_size
        total_inserted = 0
        n = amplitudes.size

        dt = timedelta(seconds=1.0 / sample_rate)

        for i in range(0, n, batch_size):
            chunk = amplitudes[i:i + batch_size]
            chunk_size = len(chunk)

            rows = []
            for j in range(chunk_size):
                sample_idx = sample_offset + i + j
                ts = start_time + dt * (i + j)
                rows.append({
                    "ship_id": ship_id,
                    "point_id": point_id,
                    "time": ts,
                    "amplitude": float(chunk[j]),
                    "sample_index": sample_idx,
                    "upload_batch_id": batch_id,
                })

            try:
                stmt = insert(VibrationWaveform).values(rows)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["ship_id", "point_id", "time", "sample_index"]
                )
                result = await self.db.execute(stmt)
                total_inserted += result.rowcount or chunk_size
            except Exception as e:
                logger.error(f"Bulk insert failed at chunk {i // batch_size}: {e}", exc_info=True)
                raise WaveformIngestionException(
                    ErrorCode.INGESTION_FAILED,
                    f"批量写入失败: {str(e)}"
                )

        logger.debug(
            f"Inserted {total_inserted} waveform points for ship_id={ship_id}, "
            f"point_id={point_id}, batch_id={batch_id}"
        )
        return total_inserted

    async def query_waveforms(
        self,
        ship_id: int,
        point_id: int,
        start_time: datetime,
        end_time: datetime,
        max_points: int = None,
    ) -> tuple:
        if max_points is None:
            max_points = yaml_config.get("query", "max_points_per_query", 1000000)

        query = (
            select(VibrationWaveform)
            .where(
                and_(
                    VibrationWaveform.ship_id == ship_id,
                    VibrationWaveform.point_id == point_id,
                    VibrationWaveform.time >= start_time,
                    VibrationWaveform.time <= end_time,
                )
            )
            .order_by(VibrationWaveform.sample_index, VibrationWaveform.time)
            .limit(max_points)
        )

        result = await self.db.execute(query)
        rows = list(result.scalars().all())

        timestamps = [row.time for row in rows]
        amplitudes = [row.amplitude for row in rows]
        sample_indices = [row.sample_index for row in rows]
        return timestamps, amplitudes, sample_indices

    async def query_waveforms_numpy(
        self,
        ship_id: int,
        point_id: int,
        start_time: datetime,
        end_time: datetime,
        max_points: int = None,
    ) -> Optional[np.ndarray]:
        timestamps, amplitudes, sample_indices = await self.query_waveforms(
            ship_id, point_id, start_time, end_time, max_points
        )
        if not amplitudes:
            return None
        return np.array(amplitudes, dtype=np.float64)


class WaveformBinaryParser:
    @staticmethod
    def parse(
        binary_data: bytes,
        dtype: str = "float32",
        byte_order: str = "little",
    ) -> np.ndarray:
        try:
            np_dtype = np.dtype(dtype)
            if byte_order == "little":
                np_dtype = np_dtype.newbyteorder("<")
            elif byte_order == "big":
                np_dtype = np_dtype.newbyteorder(">")

            data = np.frombuffer(binary_data, dtype=np_dtype)
            return data.astype(np.float64, copy=False)
        except Exception as e:
            logger.error(f"Binary parse failed: {e}", exc_info=True)
            raise WaveformIngestionException(
                ErrorCode.BINARY_PARSE_FAILED,
                f"二进制解析失败: {str(e)}"
            )

    @staticmethod
    def validate(data: np.ndarray, expected_count: int = None) -> None:
        if data.size == 0:
            raise WaveformIngestionException(ErrorCode.WAVEFORM_EMPTY)
        if expected_count is not None and data.size != expected_count:
            raise WaveformIngestionException(
                ErrorCode.SEGMENT_INVALID,
                f"样本数不匹配: 期望 {expected_count}, 实际 {data.size}"
            )
        if np.any(np.isnan(data)) or np.any(np.isinf(data)):
            raise WaveformIngestionException(
                ErrorCode.SEGMENT_INVALID,
                "波形数据包含无效值(NaN/Inf)"
            )
