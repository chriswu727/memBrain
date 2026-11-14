"""Settings that an older runtime kept for its own cognition model load and are ignored.

Background learning with a cognition model was removed. A profile that configured one, the limits file it saved
beside the profile, and an installation backup that holds both must keep loading and restoring; none of them may
start a model, change what the service runs with, or appear in a status. No database is used here.
"""
import argparse
import json
import os
from dataclasses import replace

import pytest

from membrain import desktop, desktop_cli, desktop_restore
from membrain.build_identity import BUILD_ID, MIGRATIONS, SCHEMA_ID
from membrain.config import Settings
from membrain.deletion_registry import DeletionRegistry
from membrain.desktop_backup import _configuration, file_digest
from membrain.helpers import digest, uid
from membrain.local_profile import _cognition, _open_private, _save, ensure_profile, load_profile
from membrain.recovery_profile import BINDING_FILE, write_document

COGNITION = {"base_url": "https://cognition.example/v1", "model": "configured-model",
             "api_key": "private-cognition-key", "thinking": "enabled"}
# The two formats cognition-policy.json had, and one an older runtime would itself have refused.
POLICIES = [
    {"version": 1, "max_wall_time_ms": 240000, "max_output_tokens": 16384, "max_response_bytes": 65536},
    {"version": 2, "max_wall_time_ms": 240000, "max_output_tokens": 16384, "max_response_bytes": 65536,
     "reasoning_effort": "high", "max_envelope_bytes": 131072},
    {"version": 9, "unexpected": "private value"},
]


def with_cognition(profile, base_url, model, api_key, thinking=None):
    """Write the cognition section that an older runtime's ``desktop setup --base-url ...`` saved in a profile."""
    _save(replace(load_profile(profile.directory), cognition=_cognition(
        {"base_url": base_url, "model": model, "api_key": api_key, "thinking": thinking})))
    return load_profile(profile.directory)


def configured_profile(directory, policy=None):
    """A profile as an older runtime's ``desktop setup --base-url ... --cognition-preset`` left it."""
    profile = with_cognition(ensure_profile(directory), **COGNITION)
    if policy is not None:
        write_document(profile.directory / "cognition-policy.json", policy)
    return load_profile(profile.directory)


@pytest.mark.parametrize("policy", [None, *POLICIES])
def test_an_old_profile_with_a_cognition_model_loads_and_starts_no_model(tmp_path, policy):
    profile = configured_profile(tmp_path / "profile", policy)
    assert profile.cognition == COGNITION
    settings = profile.settings()
    assert isinstance(settings, Settings)
    assert not any(name.startswith("cognition") or name == "semantic_policy" for name in dir(settings))
    assert "private-cognition-key" not in repr(settings)
    assert set(vars(settings)) == set(vars(ensure_profile(tmp_path / "plain").settings()))


def test_status_and_configuration_fingerprint_ignore_the_old_cognition_section(tmp_path):
    profile = configured_profile(tmp_path / "profile", POLICIES[1])
    status = desktop._base_status(profile)
    assert "cognition" not in json.dumps(status)
    without = replace(profile, cognition=None)
    assert desktop._fingerprint(profile) == desktop._fingerprint(without)


def test_a_new_backup_keeps_the_profile_section_and_no_cognition_limits(tmp_path):
    profile = configured_profile(tmp_path / "profile", POLICIES[1])
    value = _configuration(profile)
    assert value["cognition"] == COGNITION
    assert value["cognition_policy"] is None
    assert set(value) - {"database_engine"} == {"installation_id", "brain_id", "tenant_id", "principal_id", "name",
                                                "cognition", "chat", "cognition_policy"}


def old_backup(tmp_path, policy):
    """A registered installation backup whose configuration an older runtime wrote with its cognition settings."""
    profile = configured_profile(tmp_path / "source", policy)
    registry = DeletionRegistry.create(tmp_path / "authority", profile.installation_id)
    write_document(profile.directory / BINDING_FILE, {
        "version": 1, "registry_path": str(registry.directory), "registry_id": registry.registry_id,
        "installation_id": profile.installation_id, "state": "active", "recovery_epoch": None,
    })
    output = tmp_path / "backup"
    output.mkdir(mode=0o700)
    for name, content in (("database.dump", b"bounded dump fixture"), ("sessions.jsonl", b"")):
        descriptor = _open_private(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    configuration = {key: getattr(profile, key) for key in (
        "installation_id", "brain_id", "tenant_id", "principal_id", "name", "cognition")}
    write_document(output / "configuration.json", {**configuration, "database_engine": "embedded", "chat": None,
                                                   "cognition_policy": policy})
    manifest = {
        "version": 1, "backup_id": uid(),
        "request_hash": digest(["backup-request", str(output), profile.installation_id, 64 * 1024**3, 3600]),
        "source_installation_id": profile.installation_id, "registry": registry.head(),
        "checkpoint": {"migration_names": [name for name, _ in MIGRATIONS], "schema_id": SCHEMA_ID,
                       "build_id": BUILD_ID, "checkpoint_at": "2026-10-25T00:00:00+00:00"},
        "members": {name: file_digest(output / name, max_bytes=100_000)
                    for name in ("database.dump", "configuration.json", "sessions.jsonl")},
    }
    write_document(output / "manifest.json", manifest)
    registry.register_backup(manifest["backup_id"], digest(manifest), manifest["registry"])
    return registry, output


class DatabaseStart(Exception):
    pass


@pytest.mark.parametrize("policy", POLICIES)
def test_an_old_backup_with_cognition_limits_restores_with_them_ignored(tmp_path, monkeypatch, policy):
    """The configuration is restored up to the point where the database starts; this test stops there."""
    registry, output = old_backup(tmp_path, policy)

    def database_up(profile):
        raise DatabaseStart

    monkeypatch.setattr(desktop, "_database_up", database_up)
    target = tmp_path / "restored"
    target.mkdir(mode=0o700)
    with pytest.raises(DatabaseStart):
        desktop_restore.restore(backup_path=output, directory=target, registry_path=registry.directory,
                                request_id="restore-request")
    restored = load_profile(target)
    assert restored.cognition == COGNITION
    assert not (target / "cognition-policy.json").exists()
    assert not any(name.startswith("cognition") for name in dir(restored.settings()))
    # The same request again (a restore interrupted at this point is retried) does not conflict either.
    with pytest.raises(DatabaseStart):
        desktop_restore.restore(backup_path=output, directory=target, registry_path=registry.directory,
                                request_id="restore-request")


def parse(*values):
    parser = argparse.ArgumentParser()
    desktop_cli.add_commands(parser.add_subparsers(dest="command"))
    return parser.parse_args(["desktop", *values])


@pytest.mark.parametrize("values", [
    ("setup", "--base-url", "https://cognition.example/v1", "--model", "m", "--api-key-env", "KEY"),
    ("setup", "--cognition-preset", "reasoning"),
    ("setup", "--thinking", "enabled"),
    ("learning-status",), ("retry-learning", "--job", "job", "--request-id", "r", "--expected-fence", "1"),
    ("budget",), ("configure-budget",), ("cognition-policy",), ("configure-cognition-policy",),
])
def test_desktop_offers_no_cognition_options_or_learning_commands(values, capsys):
    with pytest.raises(SystemExit):
        parse(*values)
    error = capsys.readouterr().err
    assert "invalid choice" in error or "unrecognized arguments" in error


def test_desktop_setup_still_parses_without_any_model(tmp_path):
    args = parse("setup", "--directory", str(tmp_path), "--no-start", "--non-interactive")
    assert args.desktop_command == "setup" and args.no_start
