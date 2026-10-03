import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Tests never touch the real sample_cache/ nor call the live model, even if a key is in the environment."""
    import app as appmod
    monkeypatch.setattr(appmod, "CACHE", tmp_path / "cache")
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_BASE_URL", "http://127.0.0.1:1/v1")
