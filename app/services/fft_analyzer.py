from typing import Tuple, Optional, Dict, Any
import numpy as np
from scipy import signal

from ..config.yaml_config import yaml_config
from ..middleware.exceptions import AnalysisException
from ..middleware.error_codes import ErrorCode
from ..logging_config.logger import logger


class FFTAnalyzer:
    def __init__(self):
        cfg = yaml_config.get("fft")
        self.window_type = cfg.get("window_type", "hann")
        self.nperseg = cfg.get("nperseg", 1024)
        self.noverlap = cfg.get("noverlap", 512)
        self.detrend = cfg.get("detrend", "constant")
        self.scaling = cfg.get("scaling", "density")

    def _get_window(self, n: int) -> np.ndarray:
        try:
            return signal.get_window(self.window_type, n)
        except ValueError:
            logger.warning(f"Unknown window type: {self.window_type}, using hann")
            return signal.get_window("hann", n)

    def compute_psd(
        self,
        waveform: np.ndarray,
        sample_rate: float,
        nperseg: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        if waveform is None or waveform.size < 16:
            raise AnalysisException(ErrorCode.WAVEFORM_TOO_SHORT)
        if sample_rate <= 0:
            raise AnalysisException(ErrorCode.SAMPLE_RATE_INVALID)

        try:
            actual_nperseg = nperseg or min(self.nperseg, waveform.size // 2)
            actual_noverlap = min(self.noverlap, actual_nperseg // 2)

            frequencies, psd = signal.welch(
                waveform,
                fs=sample_rate,
                window=self._get_window(actual_nperseg),
                nperseg=actual_nperseg,
                noverlap=actual_noverlap,
                detrend=self.detrend,
                scaling=self.scaling,
                axis=0,
            )
            amplitudes = np.sqrt(psd)
            logger.info(
                f"PSD computed: {len(frequencies)} frequency points, "
                f"fs={sample_rate}Hz, nperseg={actual_nperseg}"
            )
            return frequencies, amplitudes
        except AnalysisException:
            raise
        except Exception as e:
            logger.error(f"FFT PSD computation failed: {e}", exc_info=True)
            raise AnalysisException(ErrorCode.FFT_FAILED, str(e))

    def compute_spectrum(
        self,
        waveform: np.ndarray,
        sample_rate: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        if waveform is None or waveform.size < 2:
            raise AnalysisException(ErrorCode.WAVEFORM_TOO_SHORT)
        if sample_rate <= 0:
            raise AnalysisException(ErrorCode.SAMPLE_RATE_INVALID)

        try:
            n = len(waveform)
            window = self._get_window(n)
            windowed = waveform * window

            fft_result = np.fft.rfft(windowed)
            amplitudes = np.abs(fft_result) / n * 2.0
            amplitudes[0] /= 2.0
            frequencies = np.fft.rfftfreq(n, d=1.0 / sample_rate)

            logger.info(
                f"Spectrum computed: {len(frequencies)} points, "
                f"fs={sample_rate}Hz, nfft={n}"
            )
            return frequencies, amplitudes
        except AnalysisException:
            raise
        except Exception as e:
            logger.error(f"FFT spectrum computation failed: {e}", exc_info=True)
            raise AnalysisException(ErrorCode.FFT_FAILED, str(e))

    def get_config(self) -> Dict[str, Any]:
        return {
            "window_type": self.window_type,
            "nperseg": self.nperseg,
            "noverlap": self.noverlap,
            "detrend": self.detrend,
            "scaling": self.scaling,
        }
