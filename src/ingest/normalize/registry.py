from __future__ import annotations

from typing import Callable

from ingest.contract import Limits, NormalizedSubmission

# Mỗi định dạng của đối tác là một hàm: (thân request dạng bytes, giới hạn) -> NormalizedSubmission.
# Nhận bytes để một định dạng có thể là JSON, XML hay thứ khác; ném IngestError khi không đọc được.
ParseFn = Callable[[bytes, Limits], NormalizedSubmission]

_FORMATS: dict[str, ParseFn] = {}


def register(name: str) -> Callable[[ParseFn], ParseFn]:
    def deco(fn: ParseFn) -> ParseFn:
        if name in _FORMATS:
            raise RuntimeError(f"định dạng {name!r} đã đăng ký")
        _FORMATS[name] = fn
        return fn

    return deco


def get(name: str) -> ParseFn | None:
    return _FORMATS.get(name)


def names() -> list[str]:
    return sorted(_FORMATS)
