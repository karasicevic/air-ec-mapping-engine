from __future__ import annotations

from pathlib import Path
import shutil
import uuid

import pytest


@pytest.fixture
def tmp_path() -> Path:
    base = Path(__file__).resolve().parents[1] / "tmp_local"
    base.mkdir(exist_ok=True)
    path = base / f"tmp-{uuid.uuid4().hex}"
    path.mkdir()
    yield path
    shutil.rmtree(path, ignore_errors=True)
