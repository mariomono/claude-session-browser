from app import launcher
from app.config import Config


def test_build_claude_cmd_continue():
    assert launcher.build_claude_cmd("abc123", "continue") == "claude --resume abc123"


def test_build_claude_cmd_fork():
    assert launcher.build_claude_cmd("abc123", "fork") == "claude --resume abc123 --fork-session"


def test_build_command_substitutes_tokens():
    template = ["wsl.exe", "-d", "{distro}", "--cd", "{cwd}", "--", "bash", "-lic", "{claude}"]
    cmd = launcher.build_command(template, "Ubuntu-24.04", "/home/m/proj", "abc123", "continue")
    assert cmd == ["wsl.exe", "-d", "Ubuntu-24.04", "--cd", "/home/m/proj",
                   "--", "bash", "-lic", "claude --resume abc123"]


def test_build_command_cwd_with_spaces_stays_one_token():
    template = ["wsl.exe", "--cd", "{cwd}"]
    cmd = launcher.build_command(template, "D", "/home/m/my proj/x", "id1", "continue")
    assert cmd == ["wsl.exe", "--cd", "/home/m/my proj/x"]
    assert len(cmd) == 3  # the space did not create an extra argument


def test_resume_session_ok_records_command():
    calls = []
    cfg = Config(distro="Ubuntu-24.04", launch=["wsl.exe", "--cd", "{cwd}", "--", "bash", "-lic", "{claude}"])
    result = launcher.resume_session("abc123", "/home/m/proj", "continue", cfg,
                                     spawn=lambda c: calls.append(c))
    assert result["ok"] is True
    assert calls == [result["command"]]
    assert "claude --resume abc123" in result["command"]


def test_resume_session_fork_includes_flag():
    cfg = Config(distro="D", launch=["bash", "-lic", "{claude}"])
    result = launcher.resume_session("abc123", "/cwd", "fork", cfg, spawn=lambda c: None)
    assert "claude --resume abc123 --fork-session" in result["command"]


def test_resume_session_spawn_failure_returns_error():
    def boom(cmd):
        raise FileNotFoundError("cmd.exe not found")
    cfg = Config(distro="D", launch=["cmd.exe", "{claude}"])
    result = launcher.resume_session("abc123", "/cwd", "continue", cfg, spawn=boom)
    assert result["ok"] is False
    assert "cmd.exe not found" in result["error"]
    assert result["command"][0] == "cmd.exe"
