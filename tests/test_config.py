import json
from app import config


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = config.load(tmp_path / "nope.json")
    assert cfg.distro == config.DEFAULT_DISTRO
    assert cfg.launch == config.DEFAULT_LAUNCH


def test_load_valid_file_overrides(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"distro": "Debian", "launch": ["echo", "{claude}"]}))
    cfg = config.load(p)
    assert cfg.distro == "Debian"
    assert cfg.launch == ["echo", "{claude}"]


def test_load_malformed_file_returns_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{ this is not json")
    cfg = config.load(p)
    assert cfg.distro == config.DEFAULT_DISTRO
    assert cfg.launch == config.DEFAULT_LAUNCH


def test_load_partial_file_fills_missing_keys(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"distro": "OnlyDistro"}))
    cfg = config.load(p)
    assert cfg.distro == "OnlyDistro"
    assert cfg.launch == config.DEFAULT_LAUNCH
