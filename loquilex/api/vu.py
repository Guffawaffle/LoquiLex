from __future__ import annotations

import numpy as np


def rms_peak(x: np.ndarray) -> tuple[float, float]:
    """Compute RMS and peak of a mono float32 array clipped to [0,1] domain for display.

    Input samples are expected in [-1, 1]. We return positive scalars in [0, 1].
    """
    if x.size == 0:
        return 0.0, 0.0
    # Clip to avoid NaNs from over/underflow
    x = np.clip(x.astype(np.float32, copy=False), -1.0, 1.0)
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x * x)))
    # Bound to [0,1]
    return min(1.0, max(0.0, rms)), min(1.0, max(0.0, peak))


class EmaVu:
    """Simple EMA smoother for VU meters.

    alpha: smoothing factor in (0,1]. Higher is snappier.
    """

    def __init__(self, alpha: float = 0.5) -> None:
        self.alpha = float(alpha)
        self._rms = 0.0
        self._peak = 0.0

    def update(self, rms: float, peak: float) -> tuple[float, float]:
        a = self.alpha
        self._rms = (1 - a) * self._rms + a * rms
        self._peak = (1 - a) * self._peak + a * peak
        return self._rms, self._peak
