"""Chạy test không cần pytest (dự phòng). Khuyến nghị: `pytest -q`."""
import importlib
import sys
import traceback
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root / "tests")]

try:
    import pytest  # noqa: F401
except ImportError:  # shim tối thiểu cho approx/raises khi máy chưa cài pytest
    import math
    import types
    from contextlib import contextmanager

    class _Approx:
        def __init__(self, v, rel=1e-6, abs_=1e-12):
            self.v, self.rel, self.abs = v, rel, abs_

        def __eq__(self, o):
            return math.isclose(o, self.v, rel_tol=self.rel, abs_tol=self.abs)

    @contextmanager
    def _raises(exc):
        try:
            yield
        except exc:
            return
        raise AssertionError(f"Không có {exc.__name__}")

    m = types.ModuleType("pytest")
    m.approx, m.raises = _Approx, _raises
    sys.modules["pytest"] = m
fails = total = 0
for f in sorted((root / "tests").glob("test_*.py")):
    mod = importlib.import_module(f.stem)
    for name in dir(mod):
        if name.startswith("test_"):
            total += 1
            try:
                getattr(mod, name)()
            except Exception:
                fails += 1
                print("FAIL", f.stem, name)
                traceback.print_exc()
print(f"{total - fails}/{total} test đạt")
sys.exit(1 if fails else 0)
