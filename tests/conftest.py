import pytest

from matchlens.config import Settings
from matchlens.domain import MatchCreate
from matchlens.storage import Store


@pytest.fixture
def store(tmp_path):
    return Store(Settings.load(tmp_path / "local-data"))


@pytest.fixture
def match(store):
    info = store.create(MatchCreate(title="Test match", home="A", away="B"))
    store.update(info["id"], duration=20)
    return info["id"]
