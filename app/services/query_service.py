from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    WaveformQueryResponse,
    ShipResponse,
    MeasuringPointResponse,
    ModalIdentificationResponse,
    ModalParameter,
    FFTResult,
)
from ..repository import (
    ShipRepository,
    MeasuringPointRepository,
    WaveformRepository,
    TaskRepository,
    ModalResultRepository,
    FFTSpectrumRepository,
    resolve_ship_and_point,
)
from ..middleware.exceptions import BusinessException
from ..middleware.error_codes import ErrorCode
from ..config.yaml_config import yaml_config


class QueryService:
    def __init__(self, mysql_db: AsyncSession, timescale_db: AsyncSession):
        self.mysql_db = mysql_db
        self.timescale_db = timescale_db
        self.ship_repo = ShipRepository(mysql_db)
        self.point_repo = MeasuringPointRepository(mysql_db)
        self.waveform_repo = WaveformRepository(timescale_db)
        self.task_repo = TaskRepository(mysql_db)
        self.modal_repo = ModalResultRepository(mysql_db)
        self.fft_repo = FFTSpectrumRepository(mysql_db)

    async def list_ships(self) -> List[ShipResponse]:
        from sqlalchemy import select
        from ..models import Ship
        result = await self.mysql_db.execute(
            select(Ship).where(Ship.status == 1)
        )
        ships = list(result.scalars().all())
        return [ShipResponse.model_validate(s) for s in ships]

    async def get_ship(self, ship_code: str) -> ShipResponse:
        ship = await self.ship_repo.get_by_code(ship_code)
        if not ship:
            raise BusinessException(ErrorCode.SHIP_NOT_FOUND)
        return ShipResponse.model_validate(ship)

    async def list_measuring_points(
        self, ship_code: str
    ) -> List[MeasuringPointResponse]:
        ship = await self.ship_repo.get_by_code(ship_code)
        if not ship:
            raise BusinessException(ErrorCode.SHIP_NOT_FOUND)
        points = await self.point_repo.list_by_ship(ship.id)
        return [MeasuringPointResponse.model_validate(p) for p in points]

    async def get_measuring_point(
        self, ship_code: str, point_code: str
    ) -> MeasuringPointResponse:
        ship, point = await resolve_ship_and_point(self.mysql_db, ship_code, point_code)
        return MeasuringPointResponse.model_validate(point)

    async def query_waveform(
        self,
        ship_code: str,
        point_code: str,
        start_time: datetime,
        end_time: datetime,
        max_points: Optional[int] = None,
    ) -> WaveformQueryResponse:
        ship, point = await resolve_ship_and_point(self.mysql_db, ship_code, point_code)

        if start_time >= end_time:
            raise BusinessException(ErrorCode.QUERY_TIME_RANGE_INVALID)

        default_max = yaml_config.get("query", "max_points_per_query", 1000000)
        actual_max = min(max_points or default_max, default_max)

        sample_rate = float(point.sample_rate) if point.sample_rate else 1024.0

        timestamps, amplitudes, sample_indices = await self.waveform_repo.query_waveforms(
            ship_id=ship.id,
            point_id=point.id,
            start_time=start_time,
            end_time=end_time,
            max_points=actual_max,
        )

        if not timestamps:
            raise BusinessException(ErrorCode.DATA_NOT_FOUND)

        return WaveformQueryResponse(
            ship_code=ship_code,
            point_code=point_code,
            start_time=start_time,
            end_time=end_time,
            sample_rate=sample_rate,
            total_points=len(timestamps),
            timestamps=timestamps,
            amplitudes=amplitudes,
        )

    async def list_modal_tasks(
        self,
        ship_code: Optional[str] = None,
        point_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list:
        ship_id = None
        point_id = None

        if ship_code:
            ship = await self.ship_repo.get_by_code(ship_code)
            if not ship:
                raise BusinessException(ErrorCode.SHIP_NOT_FOUND)
            ship_id = ship.id

            if point_code:
                point = await self.point_repo.get_by_code(ship.id, point_code)
                if not point:
                    raise BusinessException(ErrorCode.POINT_NOT_FOUND)
                point_id = point.id

        tasks = await self.task_repo.list_tasks(
            ship_id=ship_id,
            point_id=point_id,
            start_time=start_time,
            end_time=end_time,
        )

        result = []
        for t in tasks:
            ship = await self.ship_repo.get_by_id(t.ship_id)
            point = await self.point_repo.get_by_id(t.point_id)
            result.append({
                "task_uuid": t.task_uuid,
                "ship_code": ship.ship_code if ship else None,
                "point_code": point.point_code if point else None,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "status": t.status,
                "sample_count": t.sample_count,
                "sample_rate": float(t.sample_rate) if t.sample_rate else None,
                "error_message": t.error_message,
                "failed_waveform_path": t.failed_waveform_path,
                "created_at": t.created_at,
            })
        return result

    async def get_modal_result(
        self, task_uuid: str
    ) -> Optional[ModalIdentificationResponse]:
        task = await self.task_repo.get_by_uuid(task_uuid)
        if not task:
            raise BusinessException(ErrorCode.TASK_NOT_FOUND)

        ship = await self.ship_repo.get_by_id(task.ship_id)
        point = await self.point_repo.get_by_id(task.point_id)

        if task.status != 2:
            return ModalIdentificationResponse(
                task_uuid=task.task_uuid,
                ship_code=ship.ship_code if ship else "",
                point_code=point.point_code if point else "",
                start_time=task.start_time,
                end_time=task.end_time,
                sample_count=task.sample_count or 0,
                sample_rate=float(task.sample_rate) if task.sample_rate else 1024.0,
                modal_parameters=[],
                fft=None,
            )

        modal_rows = await self.modal_repo.get_by_task_id(task.id)
        modal_params = [
            ModalParameter(
                mode_order=r.mode_order,
                natural_frequency=float(r.natural_frequency),
                damping_ratio=float(r.damping_ratio),
                amplitude=float(r.amplitude) if r.amplitude else None,
                phase_angle=float(r.phase_angle) if r.phase_angle else None,
                confidence=float(r.confidence) if r.confidence else None,
            )
            for r in modal_rows
        ]

        freqs, amps = await self.fft_repo.get_by_task_id(task.id)
        fft_result = None
        if freqs and amps:
            fft_result = FFTResult(
                frequencies=freqs,
                amplitudes=amps,
                sample_rate=float(task.sample_rate) if task.sample_rate else 1024.0,
                nfft=len(freqs),
            )

        return ModalIdentificationResponse(
            task_uuid=task.task_uuid,
            ship_code=ship.ship_code if ship else "",
            point_code=point.point_code if point else "",
            start_time=task.start_time,
            end_time=task.end_time,
            sample_count=task.sample_count or 0,
            sample_rate=float(task.sample_rate) if task.sample_rate else 1024.0,
            modal_parameters=modal_params,
            fft=fft_result,
        )
