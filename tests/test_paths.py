"""Where runs go: data and reports folders, the shared-folder warning, config discovery, init."""
import pathlib

import yaml

import sample_data
from convscan import config, paths, report
from convscan.runner import load_run


def _cfg(tmp_path, **over):
    p = tmp_path / "convscan.yaml"
    p.write_text(yaml.safe_dump(over), encoding="utf-8")
    return config.load(str(p))


def test_name_goes_under_data_and_reports_dirs(tmp_path):
    cfg = _cfg(tmp_path, data_dir="d", reports_dir="r")          # relative to the config file
    run_dir, reports_dir = paths.resolve("batch01_pre", cfg)
    assert run_dir == tmp_path / "d" / "batch01_pre"
    assert reports_dir == tmp_path / "r" / "batch01_pre"


def test_path_keeps_the_single_folder_layout(tmp_path):
    cfg = _cfg(tmp_path)
    run_dir, reports_dir = paths.resolve(str(tmp_path / "runs" / "b1"), cfg)
    assert reports_dir == run_dir / "reports"
    assert paths.resolve("runs/b1", cfg)[1] == pathlib.Path("runs/b1/reports")


def test_default_dirs_are_in_the_home_folder():
    cfg = config.load(None)
    assert cfg["data_dir"] == pathlib.Path("~/convscan/data").expanduser()
    assert cfg["reports_dir"] == pathlib.Path("~/convscan/reports").expanduser()


def test_shared_location_warnings(tmp_path):
    assert "synced" in paths.shared_location(pathlib.Path("C:/Users/x/OneDrive - Example Inc/runs"))
    assert "synced" in paths.shared_location(pathlib.Path("/Users/x/Library/Mobile Documents/runs"))
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    assert "Git" in paths.shared_location(repo / "runs" / "b1")
    assert paths.shared_location(tmp_path / "local" / "runs") is None or "OneDrive" in str(tmp_path)


def test_reports_written_to_their_own_folder(tmp_path):
    pre_dir, _ = sample_data.write_runs(tmp_path / "data")
    cfg = config.load(None)
    pre_run, pre = load_run(pre_dir)
    shared = tmp_path / "shared" / "batch01_pre"
    report.render_pre(pre_dir, pre_run, pre, cfg, shared)
    assert (shared / "DEMO101_preflight.md").exists() and (shared / "batch_summary.md").exists()
    assert not (pre_dir / "reports").exists()


def test_find_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CONVSCAN_CONFIG", raising=False)
    monkeypatch.setattr(config, "USER_CONFIG", tmp_path / "home" / "config.yaml")
    assert config.find() is None
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "config.yaml").write_text("{}", encoding="utf-8")
    assert config.find() == str(tmp_path / "home" / "config.yaml")
    (tmp_path / "convscan.yaml").write_text("{}", encoding="utf-8")
    assert config.find() == "convscan.yaml"                       # the current folder wins
    monkeypatch.setenv("CONVSCAN_CONFIG", str(tmp_path / "home" / "config.yaml"))
    assert config.find() == str(tmp_path / "home" / "config.yaml")  # the variable wins over both


def test_starter_config_loads_and_has_no_password(tmp_path):
    text = config.starter({"host": "db.example.com", "port": "5432", "dbname": "site", "user": "",
                           "prepared_for": "Sample University"})
    assert "password:" not in text
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    cfg = config.load(str(p))
    assert cfg["db"] == {"host": "db.example.com", "port": 5432, "dbname": "site", "user": "TODO"}
    assert cfg["prepared_for"] == "Sample University"
    assert cfg["data_dir"] == pathlib.Path("~/convscan/data").expanduser()
