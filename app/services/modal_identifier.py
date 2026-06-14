from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from scipy import signal
from scipy.optimize import curve_fit

from ..config.yaml_config import yaml_config
from ..middleware.exceptions import AnalysisException
from ..middleware.error_codes import ErrorCode
from ..logging_config.logger import logger


class ModalIdentifier:
    def __init__(self):
        cfg = yaml_config.get("modal_identification")
        self.peak_prominence = cfg.get("peak_prominence", 0.05)
        self.peak_distance = cfg.get("peak_distance", 5)
        self.min_frequency = cfg.get("min_frequency", 0.5)
        self.max_frequency = cfg.get("max_frequency", 500.0)
        self.damping_fit_points = cfg.get("damping_fit_points", 10)
        self.max_modes = cfg.get("max_modes", 20)
        self.curve_fit_method = cfg.get("curve_fit_method", "lm")
        self.half_power_bandwidth = cfg.get("half_power_bandwidth", True)

    @staticmethod
    def _single_mode_lorentzian(f, f0, damping, amplitude):
        x = f / f0
        denom = (1 - x ** 2) ** 2 + (2 * damping * x) ** 2
        return amplitude * (2 * damping * x) / np.sqrt(denom)

    def _detect_peaks(
        self,
        frequencies: np.ndarray,
        amplitudes: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        valid_mask = (frequencies >= self.min_frequency) & (frequencies <= self.max_frequency)
        freq_valid = frequencies[valid_mask]
        amp_valid = amplitudes[valid_mask]

        if len(amp_valid) == 0:
            raise AnalysisException(ErrorCode.NO_PEAKS_DETECTED, "频率范围内无有效数据")

        max_amp = np.max(amp_valid)
        if max_amp <= 0:
            raise AnalysisException(ErrorCode.NO_PEAKS_DETECTED, "有效幅值均为零")

        prominence = self.peak_prominence * max_amp

        peak_indices, peak_properties = signal.find_peaks(
            amp_valid,
            prominence=prominence,
            distance=max(1, self.peak_distance),
            height=0.1 * max_amp,
        )

        if len(peak_indices) == 0:
            raise AnalysisException(ErrorCode.NO_PEAKS_DETECTED)

        peak_indices = peak_indices[: self.max_modes]
        peak_freqs = freq_valid[peak_indices]
        peak_amps = amp_valid[peak_indices]

        order = np.argsort(peak_amps)[::-1]
        peak_freqs = peak_freqs[order]
        peak_amps = peak_amps[order]

        logger.info(
            f"Detected {len(peak_freqs)} resonance peaks: "
            f"freqs={[f'{f:.3f}' for f in peak_freqs]} Hz"
        )
        return peak_freqs, peak_amps

    def _estimate_damping_half_power(
        self,
        frequencies: np.ndarray,
        amplitudes: np.ndarray,
        peak_freq: float,
        peak_amp: float,
    ) -> float:
        try:
            half_power = peak_amp / np.sqrt(2.0)
            valid_mask = amplitudes >= half_power * 0.5

            around_peak = np.abs(frequencies - peak_freq) < (peak_freq * 0.5)
            mask = valid_mask & around_peak

            if not np.any(mask):
                return 0.01

            freqs_sub = frequencies[mask]
            amps_sub = amplitudes[mask]

            if len(freqs_sub) < 3:
                return 0.01

            lower_indices = np.where(freqs_sub < peak_freq)[0]
            upper_indices = np.where(freqs_sub > peak_freq)[0]

            if len(lower_indices) == 0 or len(upper_indices) == 0:
                return 0.01

            f1 = freqs_sub[lower_indices[-1]]
            f2 = freqs_sub[upper_indices[0]]

            if f2 > f1 and peak_freq > 0:
                bandwidth = f2 - f1
                damping_ratio = bandwidth / (2.0 * peak_freq)
                return float(np.clip(damping_ratio, 1e-6, 0.5))
            return 0.01
        except Exception as e:
            logger.warning(f"Half-power damping estimation failed for {peak_freq:.2f}Hz: {e}")
            return 0.01

    def _estimate_damping_curve_fit(
        self,
        frequencies: np.ndarray,
        amplitudes: np.ndarray,
        peak_freq: float,
        peak_amp: float,
    ) -> float:
        try:
            bandwidth_est = peak_freq * 0.05
            mask = np.abs(frequencies - peak_freq) < bandwidth_est
            freqs_fit = frequencies[mask]
            amps_fit = amplitudes[mask]

            if len(freqs_fit) < self.damping_fit_points:
                return self._estimate_damping_half_power(
                    frequencies, amplitudes, peak_freq, peak_amp
                )

            initial_damping = 0.01
            p0 = [peak_freq, initial_damping, peak_amp]
            bounds = (
                [peak_freq * 0.9, 1e-6, peak_amp * 0.5],
                [peak_freq * 1.1, 0.5, peak_amp * 2.0],
            )

            try:
                popt, _ = curve_fit(
                    self._single_mode_lorentzian,
                    freqs_fit,
                    amps_fit,
                    p0=p0,
                    bounds=bounds,
                    method="trf",
                    maxfev=1000,
                )
                damping = float(np.clip(popt[1], 1e-6, 0.5))
                return damping
            except Exception:
                return self._estimate_damping_half_power(
                    frequencies, amplitudes, peak_freq, peak_amp
                )
        except Exception as e:
            logger.warning(f"Curve-fit damping estimation failed: {e}")
            return 0.01

    def _compute_confidence(
        self,
        amplitudes: np.ndarray,
        peak_amp: float,
    ) -> float:
        try:
            mean_amp = np.mean(amplitudes)
            std_amp = np.std(amplitudes)
            if std_amp == 0:
                return 0.5
            snr = (peak_amp - mean_amp) / std_amp
            confidence = 1.0 - np.exp(-snr / 5.0)
            return float(np.clip(confidence, 0.0, 1.0))
        except Exception:
            return 0.5

    def identify(
        self,
        frequencies: np.ndarray,
        amplitudes: np.ndarray,
    ) -> List[Dict[str, Any]]:
        if frequencies is None or amplitudes is None or len(frequencies) == 0:
            raise AnalysisException(ErrorCode.MODAL_IDENTIFICATION_FAILED, "FFT数据为空")

        try:
            frequencies = np.asarray(frequencies, dtype=np.float64)
            amplitudes = np.asarray(amplitudes, dtype=np.float64)

            peak_freqs, peak_amps = self._detect_peaks(frequencies, amplitudes)

            results = []
            for idx, (peak_freq, peak_amp) in enumerate(zip(peak_freqs, peak_amps)):
                if self.half_power_bandwidth:
                    damping = self._estimate_damping_half_power(
                        frequencies, amplitudes, peak_freq, peak_amp
                    )
                else:
                    damping = self._estimate_damping_curve_fit(
                        frequencies, amplitudes, peak_freq, peak_amp
                    )

                confidence = self._compute_confidence(amplitudes, peak_amp)

                results.append({
                    "mode_order": idx + 1,
                    "natural_frequency": float(peak_freq),
                    "damping_ratio": float(damping),
                    "amplitude": float(peak_amp),
                    "phase_angle": None,
                    "confidence": confidence,
                })

            results.sort(key=lambda x: x["natural_frequency"])
            for i, r in enumerate(results):
                r["mode_order"] = i + 1

            logger.info(f"Modal identification complete: {len(results)} modes identified")
            return results
        except AnalysisException:
            raise
        except Exception as e:
            logger.error(f"Modal identification failed: {e}", exc_info=True)
            raise AnalysisException(ErrorCode.MODAL_IDENTIFICATION_FAILED, str(e))

    def get_config(self) -> Dict[str, Any]:
        return {
            "peak_prominence": self.peak_prominence,
            "peak_distance": self.peak_distance,
            "min_frequency": self.min_frequency,
            "max_frequency": self.max_frequency,
            "damping_fit_points": self.damping_fit_points,
            "max_modes": self.max_modes,
            "curve_fit_method": self.curve_fit_method,
            "half_power_bandwidth": self.half_power_bandwidth,
        }
