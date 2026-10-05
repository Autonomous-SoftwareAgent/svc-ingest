"""Giữ ranh giới ba lớp bằng cách quét import (không chỉ ghi trong tài liệu).

- contract: không import module nào khác của dịch vụ.
- core: chỉ contract và core; không dùng thư viện web hay Kafka.
- normalize: chỉ contract và registry của chính nó; các module định dạng không import nhau.
- io: chỉ contract và io.
- main, config: được nối mọi lớp; không lớp nào import ngược main/config.
Không dùng import tương đối để quét không sót.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "ingest"
EXTERNAL_IO = {"fastapi", "starlette", "uvicorn", "httpx", "aiokafka"}


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, 0
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            yield mod, node.level
            if mod == "ingest":  # from ingest import normalize -> ingest.normalize
                for a in node.names:
                    yield f"ingest.{a.name}", 0


def _violations(rel: str, allowed, forbid_third_party=frozenset()):
    bad = []
    single = SRC / f"{rel}.py"
    files = [single] if single.exists() else list((SRC / rel).rglob("*.py"))
    assert files, f"không thấy mã của {rel}"
    for f in files:
        for mod, level in _imports(f):
            where = f"{f.relative_to(SRC)} -> {mod or '.'}"
            if level:
                bad.append(f"{where} (import tương đối)")
            elif mod.split(".")[0] in forbid_third_party:
                bad.append(where)
            elif mod.split(".")[0] == "ingest" and not allowed(f, mod):
                bad.append(where)
    return bad


def test_contract_imports_nothing_from_service():
    assert _violations("contract", lambda f, m: False) == []


def test_core_only_contract_and_core():
    ok = lambda f, m: m == "ingest.contract" or m.startswith("ingest.core")
    assert _violations("core", ok, EXTERNAL_IO) == []


def test_io_only_contract_and_io():
    ok = lambda f, m: m == "ingest.contract" or m.startswith("ingest.io")
    assert _violations("io", ok) == []


def test_normalize_modules_do_not_import_each_other():
    def ok(f, m):
        if m in {"ingest.contract", "ingest.normalize.registry"}:
            return True
        # chỉ __init__ được nạp các module anh em (load_all dùng importlib)
        return f.name == "__init__.py" and m == "ingest.normalize"

    assert _violations("normalize", ok, EXTERNAL_IO) == []


def test_nothing_imports_main_or_config_except_wiring():
    bad = []
    for f in SRC.rglob("*.py"):
        if f.name in {"main.py", "config.py"} and f.parent == SRC:
            continue
        for mod, _ in _imports(f):
            if mod in {"ingest.main", "ingest.config"}:
                bad.append(f"{f.relative_to(SRC)} -> {mod}")
    assert bad == []
