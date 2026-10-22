import pytest

from craftbench import usage


@pytest.fixture(autouse=True)
def private_shared_report(monkeypatch, tmp_path):
    """Tests get their own shared usage report, not the machine-wide one real runs write."""
    monkeypatch.setattr(usage, "SHARED", tmp_path / "quota.json")
