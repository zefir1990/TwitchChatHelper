import time


def current_unix_time_ms() -> int:
    return time.time_ns() // 1_000_000
