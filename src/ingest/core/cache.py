from __future__ import annotations

import threading
import time
from typing import Any, Callable


class TtlCache:
    """Cache tra cứu danh mục theo (đối tác, khách sạn), hết hạn sau ttl giây (mặc định cấu hình 24 giờ).

    Chỉ có hiệu lực trong một tiến trình: sửa danh mục ở tiến trình khác thì tiến trình này thấy muộn tới hết hạn.
    """

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._data: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                return None
            if self._clock() - hit[0] >= self._ttl:
                del self._data[key]
                return None
            return hit[1]

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._data[key] = (self._clock(), value)

    def invalidate_partner(self, partner_id: int) -> None:
        with self._lock:
            for k in [k for k in self._data if k[0] == partner_id]:
                del self._data[k]
