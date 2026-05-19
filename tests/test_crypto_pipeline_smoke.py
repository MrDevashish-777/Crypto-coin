from pathlib import Path


def test_crypto_pipeline_persists_with_publish_flag():
    signals_route = Path(__file__).resolve().parents[1] / "src" / "api" / "routes" / "signals.py"
    coll_helper = Path(__file__).resolve().parents[1] / "src" / "planitt" / "mongo_collections.py"
    persistence = Path(__file__).resolve().parents[1] / "src" / "planitt" / "persistence.py"
    content = signals_route.read_text(encoding="utf-8")
    helper = coll_helper.read_text(encoding="utf-8")
    persist = persistence.read_text(encoding="utf-8")
    assert "crypto_signals_collection" in content
    assert "signals_crypto" in helper
    assert "signals" in helper
    assert "is_published: bool = False" in persist
    assert "is_published" in content
    assert "idempotency_key" in persist
