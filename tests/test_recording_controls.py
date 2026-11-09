import json
import time
from uuid import uuid4

import httpx
import pytest
from test_memory_page_browser import account as account
from test_memory_page_browser import browser as browser
from test_memory_page_browser import open_view, sign_in, switch_language, untranslated
from test_memory_page_browser import page as page
from test_memory_page_browser import server as server

from membrain import desktop, host, local_recording
from membrain.client import MemoryActionError
from membrain.desktop_connection import open_client
from membrain.helpers import DomainError
from membrain.local_profile import load_profile


@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    import os

    directory = tmp_path_factory.mktemp("recording-controls")
    previous = os.environ.get("MEMBRAIN_SEMANTIC")
    os.environ["MEMBRAIN_SEMANTIC"] = "0"
    try:
        host.start(directory)
        yield load_profile(directory)
    finally:
        desktop.stop(directory)
        if previous is None:
            os.environ.pop("MEMBRAIN_SEMANTIC", None)
        else:
            os.environ["MEMBRAIN_SEMANTIC"] = previous


@pytest.fixture
def connected(installation):
    host.resume(installation.directory)
    with open_client(installation.directory, start_service=False) as client:
        policy = client.recording_status()
        client.set_recording(paused=False, expected_revision=policy["revision"])
        yield client
    host.resume(installation.directory)


def controls(client):
    return client._http.get("/v1/local/recording").raise_for_status().json()


def change_local(client, paused, revision=None, **fields):
    revision = controls(client)["local"]["revision"] if revision is None else revision
    return client._http.post("/v1/local/recording", json={
        "paused": paused, "expected_revision": revision, **fields})


def observe(client):
    return client.observe("Public recording-control fixture", conversation_id="control-fixture",
                          branch_id="main", source_event_key=str(uuid4()))


def test_remote_pause_is_visible_and_local_resume_cannot_clear_it(connected):
    current = connected.recording_status()
    server = connected.set_recording(paused=True, expected_revision=current["revision"])
    state = controls(connected)
    assert state["recording"] == "paused" and state["server"] == server
    assert not state["local"]["paused"]
    resumed = change_local(connected, False).raise_for_status().json()
    assert resumed["recording"] == "paused" and resumed["server"] == server
    with pytest.raises(MemoryActionError) as denied:
        observe(connected)
    assert denied.value.code == "recording_paused"


def test_server_resume_preserves_local_pause_and_local_scope_is_explicit(connected):
    paused = change_local(connected, True, hours=1).raise_for_status().json()
    assert paused["local"]["paused"] and not paused["server"]["paused"]
    assert observe(connected)["result"]["accepted_event_ids"]
    revision = connected.recording_status()["revision"]
    connected.set_recording(paused=True, expected_revision=revision)
    connected.set_recording(paused=False, expected_revision=revision + 1)
    assert controls(connected)["recording"] == "paused"
    assert change_local(connected, False).raise_for_status().json()["recording"] == "on"


def test_stale_local_resume_cannot_clear_a_new_pause(connected, installation):
    old = change_local(connected, True, hours=1).raise_for_status().json()
    host.pause(installation.directory, hours=24)
    response = change_local(connected, False, old["local"]["revision"])
    assert response.status_code == 409 and response.json()["error"]["code"] == "version_conflict"
    assert host.paused(installation.directory)
    assert controls(connected)["local"]["revision"] != old["local"]["revision"]


def test_expired_device_pause_does_not_resume_the_server(connected, installation):
    revision = connected.recording_status()["revision"]
    connected.set_recording(paused=True, expected_revision=revision)
    path = host._pause_file(installation.directory)
    path.write_text(json.dumps({"since": 0, "until": time.time() - 1}))
    state = controls(connected)
    assert not state["local"]["paused"] and state["server"]["paused"]
    assert state["recording"] == "paused" and not path.exists()


def test_local_state_is_authenticated_and_selected_brain_is_authorized(connected, installation):
    with httpx.Client(base_url=installation.base_url, trust_env=False) as anonymous:
        assert anonymous.get("/v1/local/recording").status_code == 401
        assert anonymous.post("/v1/local/recording", json={"paused": True}).status_code == 401
    home = connected.brain_id
    other = "control-" + uuid4().hex
    connected.ensure_brain(other, "Other public fixture")
    connected.brain_id = other
    try:
        connected.set_recording(paused=True, expected_revision=0)
        selected = connected._http.get("/v1/local/recording", params={"brain_id": other}).raise_for_status().json()
        assert selected["brain_id"] == other and selected["server"]["paused"]
        assert controls(connected)["brain_id"] == home and not controls(connected)["server"]["paused"]
        assert connected._http.get("/v1/local/recording", params={"brain_id": "unknown-brain"}).status_code == 404
    finally:
        connected.brain_id = home


@pytest.mark.parametrize("fields", [{"hours": True}, {"hours": "1"}, {"hours": -1},
                                    {"expected_revision": 5}, {"unknown": True}])
def test_invalid_local_controls_do_not_change_either_state(connected, fields):
    previous = controls(connected)
    response = connected._http.post("/v1/local/recording", json={"paused": True, **fields})
    assert response.status_code == 422
    assert controls(connected) == previous


def test_each_pause_has_a_new_revision_even_with_a_frozen_clock(tmp_path, monkeypatch):
    monkeypatch.setattr(host.time, "time", lambda: 12345)
    host.pause(tmp_path)
    first = local_recording.local_status(tmp_path)
    host.pause(tmp_path)
    with pytest.raises(DomainError) as conflict:
        local_recording.change(tmp_path, paused=False, expected_revision=first["revision"])
    assert conflict.value.code == "version_conflict" and host.paused(tmp_path)


@pytest.mark.parametrize("owner", [None, "alice"])
def test_unreadable_pause_does_not_enable_host_capture(tmp_path, monkeypatch, owner):
    from pathlib import Path

    path = host._pause_file(tmp_path, owner)
    original = Path.read_text

    def unreadable(target, *args, **kwargs):
        if target == path:
            raise PermissionError("Synthetic read failure")
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)
    assert host.paused(tmp_path, owner)


def test_expiry_cannot_delete_a_concurrently_replaced_pause(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from pathlib import Path
    from threading import Event

    path = host._pause_file(tmp_path)
    path.write_text(json.dumps({"since": 0, "until": 1}))
    read, release = Event(), Event()
    original = Path.read_text

    def delayed(target, *args, **kwargs):
        content = original(target, *args, **kwargs)
        if target == path and not read.is_set():
            read.set()
            assert release.wait(5)
        return content

    monkeypatch.setattr(Path, "read_text", delayed)
    with ThreadPoolExecutor(max_workers=2) as workers:
        expired = workers.submit(host.paused, tmp_path)
        assert read.wait(5)
        replacement = workers.submit(host.pause, tmp_path)
        try:
            with pytest.raises(TimeoutError):
                replacement.result(timeout=0.1)
        finally:
            release.set()
        assert expired.result(timeout=5) is False
        replacement.result(timeout=5)
    assert host.paused(tmp_path)


@pytest.mark.parametrize("content", ["{broken", "", "[]", '{"until":true}', '{"until":1e999}'])
def test_damaged_local_state_is_unknown_instead_of_recording_on(connected, installation, content):
    path = host._pause_file(installation.directory)
    path.write_text(content)
    try:
        assert host.paused(installation.directory)
        response = connected._http.get("/v1/local/recording")
        assert response.status_code == 503 and response.json()["error"]["code"] == "dependency_unavailable"
    finally:
        path.unlink(missing_ok=True)


def test_page_changes_real_server_policy_and_preserves_device_pause(connected, installation, page):
    from playwright.sync_api import expect

    sign_in(page, installation.base_url, installation.api_key)
    open_view(page, "privacy")
    page.locator("#pause-local").click()
    expect(page.locator("#recording")).to_have_text("Device capture paused")
    page.locator("#pause").click()
    expect(page.locator("#recording")).to_have_text("Recording paused")
    with pytest.raises(MemoryActionError) as denied:
        observe(connected)
    assert denied.value.code == "recording_paused"
    page.locator("#resume").click()
    expect(page.locator("#recording")).to_have_text("Device capture paused")
    assert host.paused(installation.directory) and not connected.recording_status()["paused"]
    page.locator("#resume-local").click()
    expect(page.locator("#recording")).to_have_text("Recording on")
    assert observe(connected)["result"]["accepted_event_ids"]


def test_page_rejects_stale_resume_and_refreshes_the_actual_policy(connected, installation, page):
    from playwright.sync_api import expect

    revision = connected.recording_status()["revision"]
    connected.set_recording(paused=True, expected_revision=revision)
    sign_in(page, installation.base_url, installation.api_key)
    open_view(page, "privacy")
    expect(page.locator("#resume")).to_be_visible()
    connected.set_recording(paused=False, expected_revision=revision + 1)
    connected.set_recording(paused=True, expected_revision=revision + 2)
    page.locator("#resume").click()
    expect(page.locator("#message")).to_contain_text("Recording policy changed")
    expect(page.locator("#recording")).to_have_text("Recording paused")
    assert connected.recording_status() == {"paused": True, "revision": revision + 3}


def test_page_disables_controls_when_status_cannot_be_read(connected, installation, page):
    from playwright.sync_api import expect

    sign_in(page, installation.base_url, installation.api_key)
    open_view(page, "privacy")
    page.route("**/v1/local/recording?*", lambda route: route.fulfill(status=503, json={"error": {"message": "Unavailable"}}))
    page.locator("#refresh-recording").click()
    expect(page.locator("#recording")).to_have_text("Recording status unavailable")
    expect(page.locator("#recording-actions")).to_be_hidden()
    expect(page.locator("#local-recording")).to_be_hidden()
    assert not connected.recording_status()["paused"]
    page.unroute("**/v1/local/recording?*")
    page.locator("#refresh-recording").click()
    expect(page.locator("#recording")).to_have_text("Recording on")


def test_local_controls_are_translated_and_work_in_chinese(connected, installation, page):
    from playwright.sync_api import expect

    sign_in(page, installation.base_url, installation.api_key)
    open_view(page, "privacy")
    switch_language(page, "zh")
    expect(page.locator("#pause-local")).to_have_text("暂停本机捕获")
    assert untranslated(page, "#view-privacy > .card:nth-child(2)") == []
    page.locator("#pause-local").click()
    expect(page.locator("#recording")).to_have_text("本机捕获已暂停")
    page.locator("#pause").click()
    expect(page.locator("#recording")).to_have_text("记录已暂停")
    assert connected.recording_status()["paused"]


def test_remote_memory_page_has_server_controls_without_local_capture(server, account, page):
    from playwright.sync_api import expect

    key, client = account
    sign_in(page, server.base_url, key)
    open_view(page, "privacy")
    expect(page.locator("#pause")).to_be_visible()
    expect(page.locator("#local-recording")).to_be_hidden()
    page.locator("#pause").click()
    expect(page.locator("#recording")).to_have_text("Recording paused")
    assert client.recording_status()["paused"]
    page.locator("#resume").click()
    expect(page.locator("#recording")).to_have_text("Recording on")
    assert not client.recording_status()["paused"]


def test_late_status_response_cannot_replace_a_newer_pause(connected, installation, page):
    from playwright.sync_api import expect

    sign_in(page, installation.base_url, installation.api_key)
    open_view(page, "privacy")
    expect(page.locator("#recording")).to_have_text("Recording on")
    old = controls(connected)
    held = []

    def delay_first(route):
        if not held:
            held.append(route)
        else:
            route.continue_()

    page.route("**/v1/local/recording?*", delay_first)
    with page.expect_request("**/v1/local/recording?*"):
        page.evaluate("window.pendingRecordingRead = loadRecording(); void 0")
    connected.set_recording(paused=True, expected_revision=old["server"]["revision"])
    page.evaluate("void loadRecording()")
    expect(page.locator("#recording")).to_have_text("Recording paused")
    with page.expect_response("**/v1/local/recording?*"):
        held[0].fulfill(json=old)
    page.evaluate("window.pendingRecordingRead")
    expect(page.locator("#recording")).to_have_text("Recording paused")
