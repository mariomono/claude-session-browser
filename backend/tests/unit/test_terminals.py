from app.services import launch_config, launcher, terminals
from app.services.launch_config import LaunchConfig


def _which(*present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


def test_is_wsl_from_distro_env(tmp_path):
    assert terminals.is_wsl({"WSL_DISTRO_NAME": "Ubuntu"}, tmp_path / "missing") is True


def test_is_wsl_from_proc_version(tmp_path):
    proc = tmp_path / "version"
    proc.write_text("Linux version 6.6.0-microsoft-standard-WSL2 (gcc)")
    assert terminals.is_wsl({}, proc) is True


def test_is_wsl_false_on_plain_linux(tmp_path):
    proc = tmp_path / "version"
    proc.write_text("Linux version 6.8.0-generic (buildd@ubuntu)")
    assert terminals.is_wsl({}, proc) is False


def test_is_wsl_unreadable_proc_version(tmp_path):
    assert terminals.is_wsl({}, tmp_path / "missing") is False


def test_is_wsl_reads_process_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Debian")
    assert terminals.is_wsl(proc_version=tmp_path / "missing") is True


def test_detect_platform(tmp_path):
    missing = tmp_path / "missing"
    assert terminals.detect_platform("win32") == "windows"
    assert terminals.detect_platform("darwin") == "macos"
    assert terminals.detect_platform("linux", {"WSL_DISTRO_NAME": "U"}, missing) == "wsl"
    assert terminals.detect_platform("linux", {}, missing) == "linux"


def test_wsl_prefers_windows_terminal_tab_then_plain_window():
    first, second = terminals.candidate_templates("wsl")
    assert first[:6] == ["wt.exe", "-w", "0", "nt", "-p", "{distro}"]
    assert first[6:] == launch_config.WSL_SHELL
    assert second == launch_config.DEFAULT_LAUNCH


def test_linux_order_puts_terminal_env_first():
    names = [t[0] for t in terminals.candidate_templates("linux", {"TERMINAL": "kitty --single-instance"})]
    assert names == ["kitty", "x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"]
    kitty = terminals.candidate_templates("linux", {"TERMINAL": "kitty --single-instance"})[0]
    assert kitty[:3] == ["kitty", "--single-instance", "-e"]


def test_linux_without_terminal_env():
    names = [t[0] for t in terminals.candidate_templates("linux", {})]
    assert names[0] == "x-terminal-emulator"


def test_available_filters_by_which(monkeypatch):
    monkeypatch.setattr(terminals.shutil, "which", _which("konsole", "xterm"))
    names = [t[0] for t in terminals.available_templates("linux", {})]
    assert names == ["konsole", "xterm"]


def test_select_first_available_on_wsl():
    cfg = LaunchConfig()
    assert terminals.select_template(cfg, "wsl", which=_which("cmd.exe")) == launch_config.DEFAULT_LAUNCH
    chosen = terminals.select_template(cfg, "wsl", which=_which("cmd.exe", "wt.exe"))
    assert chosen and chosen[0] == "wt.exe"


def test_select_config_override_wins_even_if_unavailable():
    cfg = LaunchConfig(launch=["my-term", "{claude}"], launch_overridden=True)
    assert terminals.select_template(cfg, "wsl", which=_which("wt.exe")) == ["my-term", "{claude}"]


def test_select_none_available():
    assert terminals.select_template(LaunchConfig(), "linux", {}, which=_which()) is None


def test_macos_and_windows_templates_pass_cwd_as_its_own_token():
    for platform in ("macos", "windows"):
        for template in terminals.candidate_templates(platform):
            cmd = launcher.build_command(template, "D", "/my dir; rm -rf ~", "abc", "continue")
            assert "/my dir; rm -rf ~" in cmd
            assert "claude --resume abc" in cmd


def test_linux_template_substitution():
    template = next(t for t in terminals.candidate_templates("linux", {}) if t[0] == "gnome-terminal")
    cmd = launcher.build_command(template, "D", "/home/m/my proj", "abc", "fork")
    assert cmd == [
        "gnome-terminal",
        "--working-directory",
        "/home/m/my proj",
        "--",
        "bash",
        "-lic",
        "claude --resume abc --fork-session",
    ]
