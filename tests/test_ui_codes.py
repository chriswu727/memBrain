import json
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

import pytest

from membrain import host


@pytest.mark.parametrize("operation", ["consume", "issue"])
def test_issuing_a_link_does_not_restore_consumed_codes_or_discard_other_links(tmp_path, monkeypatch, operation):
    original = host.issue_ui_code(tmp_path)
    snapshot_read = threading.Event()
    resume = threading.Event()
    read_text = Path.read_text
    issuer = None

    def read(path, *args, **kwargs):
        value = read_text(path, *args, **kwargs)
        if path.name == "ui-codes.json" and threading.current_thread() is issuer:
            snapshot_read.set()
            assert resume.wait(5)
        return value

    def issue():
        nonlocal issuer
        issuer = threading.current_thread()
        return host.issue_ui_code(tmp_path)

    monkeypatch.setattr(Path, "read_text", read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(issue)
        assert snapshot_read.wait(5)
        action = host.consume_ui_code if operation == "consume" else host.issue_ui_code
        args = (tmp_path, original) if operation == "consume" else (tmp_path,)
        concurrent = pool.submit(action, *args)
        try:
            concurrent.result(timeout=0.5)
        except TimeoutError:
            pass
        finally:
            resume.set()
        issued = pending.result(timeout=5)
        result = concurrent.result(timeout=5)

    assert host.consume_ui_code(tmp_path, issued)
    if operation == "consume":
        assert result is True
        assert not host.consume_ui_code(tmp_path, original)
    else:
        assert host.consume_ui_code(tmp_path, result)
        assert host.consume_ui_code(tmp_path, original)


@pytest.mark.parametrize("operation", ["consume", "issue"])
def test_failed_code_update_preserves_existing_links_without_reporting_success(tmp_path, monkeypatch, operation):
    original = host.issue_ui_code(tmp_path)
    path = tmp_path / "plugin" / "ui-codes.json"
    before = path.read_bytes()

    def fail_replace(source, target):
        raise OSError("simulated write failure")

    with monkeypatch.context() as patch:
        patch.setattr(host.os, "replace", fail_replace)
        with pytest.raises(OSError, match="simulated write failure"):
            if operation == "consume":
                host.consume_ui_code(tmp_path, original)
            else:
                host.issue_ui_code(tmp_path)

    assert path.read_bytes() == before
    assert isinstance(json.loads(before), dict)
    assert host.consume_ui_code(tmp_path, original)
    assert not host.consume_ui_code(tmp_path, original)
