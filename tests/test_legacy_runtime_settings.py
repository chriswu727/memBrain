"""Profiles and installation backups that the removed desktop chat left behind still load, back up and restore.

The bundled chat (``membrain desktop chat``) kept its model settings in ``chat.json`` beside the profile and each
unfinished chat turn in ``sessions/<identity digest>/pending.json``. Both are written here in the formats it wrote
(tests/legacy_runtime.py; the runtime at ba70e7cd read and backed up exactly these files). Nothing reads them any
more: a backup carries them as they are, and a restore writes ``chat.json`` back and keeps the sessions only as
recovery evidence, as it already did. The removed commands are refused the way other removed commands are.
"""
import argparse
import json
import os

import pytest
from legacy_runtime import CHAT, load_runtime_brain, old_chat_files

from membrain import desktop, desktop_cli, desktop_restore
from membrain.backup_transport import BackupError
from membrain.build_identity import BUILD_ID, MIGRATIONS, SCHEMA_ID
from membrain.deletion_registry import DeletionRegistry
from membrain.desktop_backup import _configuration, _sessions, file_digest
from membrain.helpers import Principal, digest, uid
from membrain.local_profile import _open_private, ensure_profile, load_profile
from membrain.recovery_profile import BINDING_FILE, write_document


def old_profile(directory):
    profile = ensure_profile(directory)
    pending = old_chat_files(profile)
    return load_profile(profile.directory), pending


def test_an_old_profile_with_chat_settings_and_a_pending_session_loads_and_reports_status(tmp_path):
    profile, _ = old_profile(tmp_path / "profile")
    plain = ensure_profile(tmp_path / "plain")
    assert set(vars(profile.settings())) == set(vars(plain.settings()))
    status = desktop._base_status(profile)
    assert "private-chat-key" not in json.dumps(status) and "chat" not in status
    assert (profile.directory / "chat.json").exists()


def test_a_new_backup_carries_chat_settings_and_pending_sessions_unread(tmp_path):
    profile, pending = old_profile(tmp_path / "profile")
    assert _configuration(profile)["chat"] == CHAT
    _sessions(profile, tmp_path / "sessions.jsonl")
    lines = (tmp_path / "sessions.jsonl").read_text().splitlines()
    assert lines == [json.dumps(pending, sort_keys=True)]
    # The chat settings are not checked any more: a file the removed chat would have refused is still carried.
    write_document(profile.directory / "chat.json", {"version": 9, "anything": "kept"})
    assert _configuration(profile)["chat"] == {"version": 9, "anything": "kept"}


def test_a_pending_session_of_another_installation_is_refused(tmp_path):
    profile, pending = old_profile(tmp_path / "profile")
    directory = next((profile.directory / "sessions").iterdir())
    write_document(directory / "pending.json", {**pending, "identity": {**pending["identity"], "installation_id": uid()}})
    with pytest.raises(BackupError, match="backup_invalid"):
        _sessions(profile, tmp_path / "sessions.jsonl")


def old_backup(tmp_path):
    """A registered installation backup whose configuration and sessions an older runtime's chat wrote."""
    profile, pending = old_profile(tmp_path / "source")
    registry = DeletionRegistry.create(tmp_path / "authority", profile.installation_id)
    write_document(profile.directory / BINDING_FILE, {
        "version": 1, "registry_path": str(registry.directory), "registry_id": registry.registry_id,
        "installation_id": profile.installation_id, "state": "active", "recovery_epoch": None,
    })
    output = tmp_path / "backup"
    output.mkdir(mode=0o700)
    for name, content in (("database.dump", b"bounded dump fixture"),
                          ("sessions.jsonl", (json.dumps(pending, sort_keys=True) + "\n").encode())):
        descriptor = _open_private(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    configuration = {key: getattr(profile, key) for key in (
        "installation_id", "brain_id", "tenant_id", "principal_id", "name", "cognition")}
    write_document(output / "configuration.json", {**configuration, "database_engine": "embedded", "chat": CHAT,
                                                   "cognition_policy": None})
    manifest = {
        "version": 1, "backup_id": uid(),
        "request_hash": digest(["backup-request", str(output), profile.installation_id, 64 * 1024**3, 3600]),
        "source_installation_id": profile.installation_id, "registry": registry.head(),
        "checkpoint": {"migration_names": [name for name, _ in MIGRATIONS], "schema_id": SCHEMA_ID,
                       "build_id": BUILD_ID, "checkpoint_at": "2026-11-01T00:00:00+00:00"},
        "members": {name: file_digest(output / name, max_bytes=100_000)
                    for name in ("database.dump", "configuration.json", "sessions.jsonl")},
    }
    write_document(output / "manifest.json", manifest)
    registry.register_backup(manifest["backup_id"], digest(manifest), manifest["registry"])
    return registry, output


class DatabaseStart(Exception):
    pass


def test_an_old_backup_with_chat_settings_restores_them_unchanged(tmp_path, monkeypatch):
    """The configuration is restored up to the point where the database starts; this test stops there."""
    registry, output = old_backup(tmp_path)

    def database_up(profile):
        raise DatabaseStart

    monkeypatch.setattr(desktop, "_database_up", database_up)
    target = tmp_path / "restored"
    target.mkdir(mode=0o700)
    for _ in range(2):  # A restore interrupted at this point is retried with the same request.
        with pytest.raises(DatabaseStart):
            desktop_restore.restore(backup_path=output, directory=target, registry_path=registry.directory,
                                    request_id="restore-request")
    assert json.loads((target / "chat.json").read_text()) == CHAT
    assert set(vars(load_profile(target).settings())) == set(vars(ensure_profile(tmp_path / "plain").settings()))


def parse(*values):
    parser = argparse.ArgumentParser()
    desktop_cli.add_commands(parser.add_subparsers(dest="command"))
    return parser.parse_args(["desktop", *values])


@pytest.mark.parametrize("values", [
    ("chat",), ("chat", "--conversation", "c"), ("configure-chat", "--base-url", "https://chat.example/v1"),
    ("turn-status",), ("turn-status", "--conversation", "c"),
])
def test_desktop_offers_no_chat_or_turn_commands(values, capsys):
    with pytest.raises(SystemExit):
        parse(*values)
    error = capsys.readouterr().err
    assert "invalid choice" in error


@pytest.mark.integration
def test_a_real_backup_of_an_old_installation_restores_its_turns_chat_files_and_sessions(tmp_path):
    from test_desktop_recovery_e2e import connection
    from test_legacy_runtime_data import digests, holding, text_events, turn_texts

    from membrain.desktop_backup import backup
    from membrain.desktop_restore import activate, restore
    from membrain.recovery_profile import authority_for
    from membrain.service import MemoryService
    from membrain.storage import Database

    source = ensure_profile(tmp_path / "source", database_engine="embedded")
    pending = old_chat_files(source)
    target = tmp_path / "restored"
    restored = None
    try:
        desktop._prepare_database(source)
        principal = Principal(source.tenant_id, source.principal_id)
        old = load_runtime_brain(Database(source.database_url, source.migration_database_url), principal=principal)
        archive = tmp_path / "backup"
        saved = backup(source.directory, output=archive, request_id="old-runtime-backup")
        assert json.loads((archive / "configuration.json").read_text())["chat"] == CHAT
        assert (archive / "sessions.jsonl").read_text().splitlines() == [json.dumps(pending, sort_keys=True)]
        # Erased after the backup was taken: the restore must apply this erasure to the old turns too.
        erased = turn_texts(old, "draft")
        with connection(source) as (_, database, _):
            old.database, old.service = database, MemoryService(database)
            old.forget("events", text_events(old, erased))
        authority = authority_for(source)
        result = restore(backup_path=archive, directory=target, registry_path=authority.registry.directory,
                         request_id="old-runtime-restore")
        restored = load_profile(target)
        assert json.loads((target / "chat.json").read_text()) == CHAT
        assert (target / "recovery-sessions.jsonl").read_bytes() == (archive / "sessions.jsonl").read_bytes()
        head = authority.registry.head()
        activate(target, recovery_epoch=result["recovery_epoch"], backup_id=saved["backup_id"],
                 checkpoint_at=result["checkpoint"]["checkpoint_at"], retire_installation_id=source.installation_id,
                 expected_sequence=head["sequence"], expected_head_hash=head["head_hash"],
                 acknowledge_host_reconciliation=True)
        with connection(restored, recovery_epoch=result["recovery_epoch"]) as (client, database, _):
            old.database, old.service = database, MemoryService(database)
            assert holding(old, erased | digests(*erased)) == {}
            stages = {row["turn_id"]: row["stage"] for row in old.rows("memory_runtime_turns")}
            # The restore quarantined every turn an older runtime left unfinished; finished ones are unchanged.
            assert {stages[old.turns[name]] for name in ("remembered", "confirmation", "reviewed")} == {"completed"}
            assert set(stages.values()) <= {"completed", "failed"}
            texts = turn_texts(old, "reviewed")
            old.forget("events", text_events(old, texts))
            assert holding(old, texts | digests(*texts)) == {}
    finally:
        if restored is None and (target / "profile.json").exists():
            restored = load_profile(target)
        for profile in (restored, source):
            if profile is not None:
                desktop.stop(profile.directory)
