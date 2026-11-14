"""Connection settings: config db block, environment overrides, and the password never in a file."""
import pytest

from convscan import config
from convscan.runner import connection_settings, password

DB = {"host": "db.example.com", "port": 5432, "dbname": "site", "user": "reader"}


def test_settings_from_config():
    assert connection_settings(DB, env={}) == {"host": "db.example.com", "port": "5432",
                                               "dbname": "site", "user": "reader"}


def test_environment_overrides_config():
    s = connection_settings(DB, env={"DDA_HOST": "other.example.com", "DDA_PORT": "6543"})
    assert s["host"] == "other.example.com" and s["port"] == "6543" and s["user"] == "reader"


def test_environment_alone_still_works():
    env = {"DDA_HOST": "h", "DDA_DBNAME": "d", "DDA_USER": "u"}
    assert connection_settings(None, env=env)["port"] == "5432"


def test_missing_settings_say_how_to_fix():
    with pytest.raises(SystemExit) as e:
        connection_settings({"host": "h"}, env={})
    assert "dbname, user" in str(e.value) and "config" in str(e.value)


def test_password_from_environment_or_prompt():
    assert password(env={"DDA_PASSWORD": "s3cret"}) == "s3cret"
    assert password(env={}, prompt=lambda _: "typed") == "typed"


def test_password_never_accepted_in_config(tmp_path):
    for text in ("db:\n  host: h\n  password: x\n", "password: x\n"):
        p = tmp_path / "config.yaml"
        p.write_text(text, encoding="utf-8")
        with pytest.raises(SystemExit) as e:
            config.load(str(p))
        assert "password" in str(e.value)


def test_config_db_block_loads(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("db:\n  host: h\n  dbname: d\n  user: u\nprepared_for: Sample University\n", encoding="utf-8")
    cfg = config.load(str(p))
    assert cfg["db"] == {"host": "h", "port": 5432, "dbname": "d", "user": "u"}
    assert cfg["prepared_for"] == "Sample University"
    assert config.DEFAULTS["db"]["host"] is None          # defaults not mutated


def test_unknown_db_setting_rejected(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("db:\n  hostname: h\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        config.load(str(p))
    assert "hostname" in str(e.value)
