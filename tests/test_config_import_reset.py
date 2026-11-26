import json
import threading

import pytest

import plexpy
import plexpy.config as config_module
from plexpy import webserve
from plexpy.api2 import API2


@pytest.fixture
def import_file(app_config, tmp_path, monkeypatch):
    imported = tmp_path / "imported.ini"
    imported.write_text("[General]\nhttp_port = 8282\n")
    monkeypatch.setattr(plexpy, "SIGNAL", None)
    monkeypatch.setattr(config_module, "IS_IMPORTING", False)
    thread = threading.Thread(target=lambda: None)
    monkeypatch.setattr(config_module, "IMPORT_THREAD", thread)
    return str(imported), thread


def test_success_clears_state_and_restarts(import_file, app_config, monkeypatch):
    path, _ = import_file
    seen = []
    monkeypatch.setattr(app_config, "write", lambda: seen.append(config_module.IS_IMPORTING))

    config_module.import_tautulli_config(path)

    assert seen == [True]
    assert config_module.IS_IMPORTING is False
    assert config_module.IMPORT_THREAD is None
    assert plexpy.SIGNAL == "restart"
    assert app_config.HTTP_PORT != 8282


@pytest.mark.parametrize("target", ["merge", "write"])
def test_exception_clears_state(import_file, app_config, monkeypatch, target):
    path, _ = import_file

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    if target == "merge":
        monkeypatch.setattr(app_config._config, "merge", boom)
    else:
        monkeypatch.setattr(app_config, "write", boom)

    with pytest.raises(RuntimeError):
        config_module.import_tautulli_config(path)

    assert config_module.IS_IMPORTING is False
    assert config_module.IMPORT_THREAD is None
    assert plexpy.SIGNAL is None


def test_backup_failure_clears_thread(import_file, monkeypatch):
    path, _ = import_file
    monkeypatch.setattr(config_module, "make_backup", lambda *args, **kwargs: False)

    assert config_module.import_tautulli_config(path, backup=True) is False

    assert config_module.IS_IMPORTING is False
    assert config_module.IMPORT_THREAD is None
    assert plexpy.SIGNAL is None


def test_unreadable_config_clears_thread(import_file, tmp_path):
    bad = tmp_path / "bad.ini"
    bad.write_text("[General\nbroken")

    assert config_module.import_tautulli_config(str(bad)) is False

    assert config_module.IS_IMPORTING is False
    assert config_module.IMPORT_THREAD is None
    assert plexpy.SIGNAL is None


def test_refused_call_keeps_running_import_state(import_file, monkeypatch):
    path, thread = import_file
    monkeypatch.setattr(config_module, "IS_IMPORTING", True)

    assert config_module.import_tautulli_config(path) is False

    assert config_module.IS_IMPORTING is True
    assert config_module.IMPORT_THREAD is thread
    assert plexpy.SIGNAL is None


@pytest.fixture
def no_import(app_config, monkeypatch):
    monkeypatch.setattr(plexpy, "SIGNAL", None)
    monkeypatch.setattr(config_module, "IS_IMPORTING", False)
    monkeypatch.setattr(config_module, "IMPORT_THREAD", None)
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32


def config_file(tmp_path, name):
    path = tmp_path / ("%s.ini" % name)
    path.write_text("[PMS]\npms_name = %s\n" % name)
    return str(path)


def wait_for_import():
    thread = config_module.IMPORT_THREAD
    if thread and thread.ident:
        thread.join(5)


def test_api_import_runs_the_import(no_import, app_config, tmp_path):
    out = API2()._api_run(apikey=app_config.API_KEY, cmd="import_config", config_path=config_file(tmp_path, "Api"))
    wait_for_import()

    assert json.loads(out)["response"]["result"] == "success"
    assert app_config.PMS_NAME == "Api"
    assert plexpy.SIGNAL == "restart"
    assert config_module.IMPORT_THREAD is None


def test_web_import_after_an_api_import_imports_its_own_file(no_import, app_config, tmp_path, monkeypatch):
    monkeypatch.setattr(webserve.WebInterface, "do_state_change", lambda self, *args, **kwargs: "state changed")
    API2()._api_run(apikey=app_config.API_KEY, cmd="import_config", config_path=config_file(tmp_path, "Api"))
    wait_for_import()

    web = webserve.WebInterface()
    assert web.import_config(config_path=config_file(tmp_path, "Web"))["result"] == "success"
    assert web.restart_import_config() == "state changed"
    wait_for_import()

    assert app_config.PMS_NAME == "Web"
    assert config_module.IMPORT_THREAD is None


def test_web_import_leaves_the_start_to_restart_import_config(no_import, tmp_path):
    assert webserve.WebInterface().import_config(config_path=config_file(tmp_path, "Web"))["result"] == "success"

    assert config_module.IMPORT_THREAD.ident is None


def test_api_import_leaves_a_running_import_alone(no_import, tmp_path, monkeypatch):
    gate = threading.Event()
    running = threading.Thread(target=gate.wait)
    running.start()
    monkeypatch.setattr(config_module, "IMPORT_THREAD", running)
    try:
        API2().import_config(config_path=config_file(tmp_path, "Api"))
    finally:
        gate.set()
        running.join(5)

    assert config_module.IMPORT_THREAD is running
