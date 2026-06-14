from datetime import datetime
from typing import Optional, Tuple, List
import uuid
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ModalIdentificationResponse,
    ModalParameter,
    FFTResult,
)
from ..repository import (
    WaveformRepository,
    TaskRepository,
    ModalResultRepository,
    FFTSpectrumRepository,
    resolve_ship_and_point,
)
from .fft_analyzer import FFTAnalyzer
from .modal_identifier import ModalIdentifier
from ..middleware.exceptions import BusinessException, AnalysisException
from ..middleware.error_codes import ErrorCode
from ..logging_config.logger import logger, save_failed_waveform


class ModalIdentificationService:
    def __init__(self, mysql_db: AsyncSession, timescale_db: AsyncSession):
        self.mysql_db = mysql_db
        self.timescale_db = timescale_db
        self.waveform_repo = WaveformRepository(timescale_db)
        self.task_repo = TaskRepository(mysql_db)
        self.modal_repo = ModalResultRepository(mysql_db)
        self.fft_repo = FFTSpectrumRepository(mysql_db)
        self.fft_analyzer = FFTAnalyzer()
        self.modal_identifier = ModalIdentifier()

    @staticmethod
    def _align_waveform_by_sample_index(
        sample_indices: List[int],
        amplitudes: List[float],
        min_segment_length: int = 16,
    ) -> np.ndarray:
        if not sample_indices or not amplitudes:
            return np.array([], dtype=np.float64)

        indices = np.array(sample_indices, dtype=np.int64)
        amps = np.array(amplitudes, dtype=np.float64)

        sort_order = np.argsort(indices)
        indices = indices[sort_order]
        amps = amps[sort_order]

        _, unique_idx = np.unique(indices, return_index=True)
        indices = indices[unique_idx]
        amps = amps[unique_idx]

        n = len(indices)
        if n < min_segment_length:
            return amps

        diffs = np.diff(indices)
        breaks = np.where(diffs != 1)[0]

        if len(breaks) == 0:
            base_idx = indices[0]
            seg_size = indices[-1] - base_idx + 1
            aligned = np.zeros(seg_size, dtype=np.float64)
            aligned[indices - base_idx] = amps
            return aligned

        seg_starts = np.concatenate([[0], breaks + 1])
        seg_ends = np.concatenate([breaks + 1, [n]])
        seg_lengths = seg_ends - seg_starts

        best_seg_idx = np.argmax(seg_lengths)
        best_len = seg_lengths[best_seg_idx]
        best_start = seg_starts[best_seg_idx]
        best_end = seg_ends[best_seg_idx]

        if best_len < min_segment_length:
            best_start = 0
            best_end = n

        seg_indices = indices[best_start:best_end]
        seg_amps = amps[best_start:best_end]
        base_idx = seg_indices[0]
        seg_size = seg_indices[-1] - base_idx + 1
        aligned = np.zeros(seg_size, dtype=np.float64)
        aligned[seg_indices - base_idx] = seg_amps

        return aligned

    async def identify_modal(
        self,
        ship_code: str,
        point_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> ModalIdentificationResponse:
        ship, point = await resolve_ship_and_point(self.mysql_db, ship_code, point_code)

        if start_time >= end_time:
            raise BusinessException(ErrorCode.QUERY_TIME_RANGE_INVALID)

        sample_rate = float(point.sample_rate) if point.sample_rate else 1024.0

        task_uuid = str(uuid.uuid4())
        task = await self.task_repo.create_task(
            ship_id=ship.id,
            point_id=point.id,
            task_uuid=task_uuid,
            start_time=start_time,
            end_time=end_time,
            sample_rate=sample_rate,
        )
        await self.mysql_db.commit()
        task_id = task.id

        try:
            timestamps, amplitudes, sample_indices = await self.waveform_repo.query_waveforms(
                ship_id=ship.id,
                point_id=point.id,
                start_time=start_time,
                end_time=end_time,
            )

            if not amplitudes or len(amplitudes) < 16:
                raise AnalysisException(ErrorCode.WAVEFORM_TOO_SHORT, "可用波形数据不足")

            waveform = self._align_waveform_by_sample_index(sample_indices, amplitudes)

            if waveform is None or waveform.size < 16:
                raise AnalysisException(ErrorCode.WAVEFORM_TOO_SHORT, "可用波形数据不足")

            sample_count = waveform.size
            await self.task_repo.update_status(
                task_uuid, status=1, sample_count=sample_count, sample_rate=sample_rate
            )
            await self.mysql_db.commit()

            frequencies, amplitudes = self.fft_analyzer.compute_psd(
                waveform, sample_rate
            )

            modal_params = self.modal_identifier.identify(frequencies, amplitudes)

            await self.modal_repo.save_results(task_id, modal_params)

            max_spectrum_points = 5000
            if len(frequencies) > max_spectrum_points:
                step = len(frequencies) // max_spectrum_points
                freq_saved = frequencies[::step].tolist()
                amp_saved = amplitudes[::step].tolist()
            else:
                freq_saved = frequencies.tolist()
                amp_saved = amplitudes.tolist()
            await self.fft_repo.save_spectrum(task_id, freq_saved, amp_saved)

            await self.task_repo.update_status(task_uuid, status=2)
            await self.mysql_db.commit()

            modal_params_objs = [
                ModalParameter(**mp) for mp in modal_params
            ]
            fft_result = FFTResult(
                frequencies=frequencies.tolist(),
                amplitudes=amplitudes.tolist(),
                sample_rate=sample_rate,
                nfft=len(frequencies),
            )

            logger.info(
                f"Modal identification success: task_uuid={task_uuid}, "
                f"modes={len(modal_params)}"
            )

            return ModalIdentificationResponse(
                task_uuid=task_uuid,
                ship_code=ship_code,
                point_code=point_code,
                start_time=start_time,
                end_time=end_time,
                sample_count=sample_count,
                sample_rate=sample_rate,
                modal_parameters=modal_params_objs,
                fft=fft_result,
            )

        except AnalysisException as ae:
            raw_bytes = waveform.tobytes() if waveform is not None else b""
            failed_path = save_failed_waveform(
                task_uuid,
                raw_bytes,
                metadata={
                    "ship_code": ship_code,
                    "point_code": point_code,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "sample_rate": sample_rate,
                    "sample_count": sample_count if 'sample_count' in dir() else 0,
                    "error": str(ae),
                },
            )
            await self.task_repo.update_status(
                task_uuid, status=3, error_message=str(ae), failed_path=failed_path
            )
            await self.mysql_db.commit()
            raise
        except Exception as e:
            logger.error(f"Modal identification unexpected error: {e}", exc_info=True)
            raw_bytes = waveform.tobytes() if waveform is not None else b""
            failed_path = save_failed_waveform(
                task_uuid,
                raw_bytes,
                metadata={
                    "ship_code": ship_code,
                    "point_code": point_code,
                    "error": str(e),
                },
            )
            await self.task_repo.update_status(
                task_uuid, status=3, error_message=str(e), failed_path=failed_path
            )
            await self.mysql_db.commit()
            raise AnalysisException(ErrorCode.MODAL_IDENTIFICATION_FAILED, str(e))

    async def get_task_result(
        self,
        task_uuid: str,
    ) -> Optional[ModalIdentificationResponse]:
        task = await self.task_repo.get_by_uuid(task_uuid)
        if not task:
            raise BusinessException(ErrorCode.TASK_NOT_FOUND)

        if task.status != 2:
            return None

        ship_repo = __import__(
            "app.repository.ship_repository", fromlist=["ShipRepository", "MeasuringPointRepository"]
        )
        ship = await ship_repo.ShipRepository(self.mysql_db).get_by_id(task.ship_id)
        point = await ship_repo.MeasuringPointRepository(self.mysql_db).get_by_id(task.point_id)

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
