from core.storage import JsonStorage


def test_json_and_jsonl_roundtrip(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "data")
    path = storage.data_dir / "custom.json"
    storage.write_json(path, {"ok": True})
    assert storage.read_json(path, {}) == {"ok": True}
    log = storage.data_dir / "log.jsonl"
    storage.append_jsonl(log, {"n": 1})
    storage.append_jsonl(log, {"n": 2})
    assert storage.read_jsonl(log, limit=1) == [{"n": 2}]

