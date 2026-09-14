"""Resolution accompanies duration observations; sub-tick is not exact zero."""
import math
import time


def monotonic_resolution_ns() -> int:
    return max(1, math.ceil(time.get_clock_info('monotonic').resolution * 1_000_000_000))


def duration_precision(duration_ns: int, resolution_ns: int) -> dict:
    if resolution_ns <= 0 or duration_ns < 0:
        raise ValueError('duration must be nonnegative and clock resolution positive')
    return {'clockResolutionNs': resolution_ns,
            'belowResolution': duration_ns < resolution_ns,
            'uncertainty': str(resolution_ns / 1_000_000)}
