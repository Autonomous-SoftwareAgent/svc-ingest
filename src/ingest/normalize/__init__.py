"""Lớp chuẩn hóa: mỗi định dạng của đối tác là một module trong thư mục này, tự đăng ký bằng @register.

Thêm định dạng mới = thêm một tệp; không sửa tệp nào đang có.
"""
from __future__ import annotations

import importlib
import pkgutil

from ingest.normalize.registry import get, names, register  # noqa: F401


def load_all() -> None:
    for mod in pkgutil.iter_modules(__path__):
        if mod.name != "registry":
            importlib.import_module(f"{__name__}.{mod.name}")


load_all()
