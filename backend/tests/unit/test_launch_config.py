import json

from app.services import launch_config


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = launch_config.load(tmp_path / "nope.json")
    assert cfg.distro == launch_config.DEFAULT_DISTRO
    assert cfg.launch == launch_config.DEFAULT_LAUNCH


def test_load_valid_file_overrides(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"distro": "Debian", "launch": ["echo", "{claude}"]}))
    cfg = launch_config.load(p)
    assert cfg.distro == "Debian"
    assert cfg.launch == ["echo", "{claude}"]


def test_load_malformed_file_returns_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{ this is not json")
    cfg = launch_config.load(p)
    assert cfg.distro == launch_config.DEFAULT_DISTRO
    assert cfg.launch == launch_config.DEFAULT_LAUNCH


def test_load_partial_file_fills_missing_keys(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"distro": "OnlyDistro"}))
    cfg = launch_config.load(p)
    assert cfg.distro == "OnlyDistro"
    assert cfg.launch == launch_config.DEFAULT_LAUNCH
