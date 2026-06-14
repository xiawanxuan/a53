from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import IdentificationTask, ModalResult, FFTSpectrum
from ..logging_config.logger import logger


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        ship_id: int,
        point_id: int,
        task_uuid: str,
        start_time: datetime,
        end_time: datetime,
        sample_count: int = 0,
        sample_rate: float = 0,
    ) -> IdentificationTask:
        task = IdentificationTask(
            ship_id=ship_id,
            point_id=point_id,
            task_uuid=task_uuid,
            start_time=start_time,
            end_time=end_time,
            status=1,
            sample_count=sample_count,
            sample_rate=sample_rate,
        )
        self.db.add(task)
        await self.db.flush()
        logger.info(f"Created identification task: {task_uuid}")
        return task

    async def get_by_uuid(self, task_uuid: str) -> Optional[IdentificationTask]:
        result = await self.db.execute(
            select(IdentificationTask).where(IdentificationTask.task_uuid == task_uuid)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        task_uuid: str,
        status: int,
        error_message: str = None,
        failed_path: str = None,
        sample_count: int = None,
        sample_rate: float = None,
    ) -> Optional[IdentificationTask]:
        task = await self.get_by_uuid(task_uuid)
        if not task:
            return None
        task.status = status
        if error_message is not None:
            task.error_message = error_message
        if failed_path is not None:
            task.failed_waveform_path = failed_path
        if sample_count is not None:
            task.sample_count = sample_count
        if sample_rate is not None:
            task.sample_rate = sample_rate
        await self.db.flush()
        return task

    async def list_tasks(
        self,
        ship_id: int = None,
        point_id: int = None,
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> list:
        query = select(IdentificationTask)
        conditions = []
        if ship_id:
            conditions.append(IdentificationTask.ship_id == ship_id)
        if point_id:
            conditions.append(IdentificationTask.point_id == point_id)
        if start_time:
            conditions.append(IdentificationTask.start_time >= start_time)
        if end_time:
            conditions.append(IdentificationTask.end_time <= end_time)
        if conditions:
            from sqlalchemy import and_
            query = query.where(and_(*conditions))
        query = query.order_by(IdentificationTask.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())


class ModalResultRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_results(self, task_id: int, modal_params: list) -> int:
        count = 0
        for mp in modal_params:
            result = ModalResult(
                task_id=task_id,
                mode_order=mp.get("mode_order"),
                natural_frequency=mp.get("natural_frequency"),
                damping_ratio=mp.get("damping_ratio"),
                amplitude=mp.get("amplitude"),
                phase_angle=mp.get("phase_angle"),
                confidence=mp.get("confidence"),
            )
            self.db.add(result)
            count += 1
        await self.db.flush()
        logger.info(f"Saved {count} modal results for task_id={task_id}")
        return count

    async def get_by_task_id(self, task_id: int) -> list:
        result = await self.db.execute(
            select(ModalResult)
            .where(ModalResult.task_id == task_id)
            .order_by(ModalResult.mode_order)
        )
        return list(result.scalars().all())


class FFTSpectrumRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_spectrum(self, task_id: int, frequencies: list, amplitudes: list) -> int:
        count = 0
        batch_size = 1000
        rows = []
        for freq, amp in zip(frequencies, amplitudes):
            rows.append({
                "task_id": task_id,
                "frequency": freq,
                "amplitude": amp,
            })
            if len(rows) >= batch_size:
                await self._batch_insert(rows)
                count += len(rows)
                rows = []
        if rows:
            await self._batch_insert(rows)
            count += len(rows)
        await self.db.flush()
        logger.info(f"Saved {count} FFT spectrum points for task_id={task_id}")
        return count

    async def _batch_insert(self, rows: list) -> None:
        from sqlalchemy.dialects.mysql import insert
        stmt = insert(FFTSpectrum).values(rows)
        await self.db.execute(stmt)

    async def get_by_task_id(self, task_id: int, limit: int = 5000) -> tuple:
        result = await self.db.execute(
            select(FFTSpectrum)
            .where(FFTSpectrum.task_id == task_id)
            .order_by(FFTSpectrum.frequency)
            .limit(limit)
        )
        rows = list(result.scalars().all())
        frequencies = [float(r.frequency) for r in rows]
        amplitudes = [float(r.amplitude) for r in rows]
        return frequencies, amplitudes


class AlertCallbackRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(
        self,
        task_id: int,
        ship_id: int,
        point_id: int,
        callback_uuid: str,
        webhook_url: str,
        dangerous_modes_json: str,
        max_retries: int = 3,
    ):
        from ..models import AlertCallbackRecord
        record = AlertCallbackRecord(
            task_id=task_id,
            ship_id=ship_id,
            point_id=point_id,
            callback_uuid=callback_uuid,
            webhook_url=webhook_url,
            status=0,
            retry_count=0,
            max_retries=max_retries,
            dangerous_modes=dangerous_modes_json,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def update_record(
        self,
        callback_uuid: str,
        status: int = None,
        retry_count: int = None,
        response_status: int = None,
        response_body: str = None,
        error_message: str = None,
        pushed_at: datetime = None,
    ):
        from ..models import AlertCallbackRecord
        result = await self.db.execute(
            select(AlertCallbackRecord).where(AlertCallbackRecord.callback_uuid == callback_uuid)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        if status is not None:
            record.status = status
        if retry_count is not None:
            record.retry_count = retry_count
        if response_status is not None:
            record.response_status = response_status
        if response_body is not None:
            record.response_body = response_body
        if error_message is not None:
            record.error_message = error_message
        if pushed_at is not None:
            record.pushed_at = pushed_at
        await self.db.flush()
        return record

    async def get_by_uuid(self, callback_uuid: str):
        from ..models import AlertCallbackRecord
        result = await self.db.execute(
            select(AlertCallbackRecord).where(AlertCallbackRecord.callback_uuid == callback_uuid)
        )
        return result.scalar_one_or_none()

    async def list_records(
        self,
        ship_id: int = None,
        point_id: int = None,
        task_id: int = None,
        status: int = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> list:
        from ..models import AlertCallbackRecord
        from sqlalchemy import and_
        query = select(AlertCallbackRecord)
        conditions = []
        if ship_id:
            conditions.append(AlertCallbackRecord.ship_id == ship_id)
        if point_id:
            conditions.append(AlertCallbackRecord.point_id == point_id)
        if task_id:
            conditions.append(AlertCallbackRecord.task_id == task_id)
        if status is not None:
            conditions.append(AlertCallbackRecord.status == status)
        if start_time:
            conditions.append(AlertCallbackRecord.created_at >= start_time)
        if end_time:
            conditions.append(AlertCallbackRecord.created_at <= end_time)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(AlertCallbackRecord.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
