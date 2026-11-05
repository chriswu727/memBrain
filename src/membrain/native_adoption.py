"""Bind ordinary desktop startup to durable native engine admission."""
from __future__ import annotations

import os
import re
import stat
import subprocess
from dataclasses import replace
from pathlib import Path

from . import (
    embedded_database,
    native_bundle,
    native_engine_store,
    native_snapshot,
    native_transition,
)
from .local_profile import (
    LocalProfileError,
    _directory,
    adopt_native_engine,
    load_profile,
    profile_lock,
)
from .recovery_profile import read_document, write_document

_FILE = "native-source.json"


def _error():
    return embedded_database.EmbeddedDatabaseError(
        "native_adoption_blocked",
        "The native engine source or upgrade state could not be verified. API readiness is blocked; existing engines, database data and recovery files were preserved.",
    )


def _identity(profile):
    return {**native_transition._profile_identity(profile), "installation_id": profile.installation_id,
            "brain_id": profile.brain_id}


def _source(profile):
    document = read_document(profile.directory / _FILE)
    if document is None:
        return None
    try:
        if (set(document) != {"version", "profile", "target", "data", "log", "account", "original", "fresh", "system_identifier"}
                or type(document["version"]) is not int or document["version"] != 1
                or document["profile"] != _identity(profile) or type(document["fresh"]) is not bool):
            raise _error()
        account = document["account"]
        if account is not None and (not isinstance(account, list) or len(account) != 2
                or any(type(value) is not int or value < 0 for value in account)):
            raise _error()
        layout = embedded_database._Layout(
            _directory(Path(document["target"]["prefix"]) / "bin"),
            _directory(Path(document["data"])), _directory(Path(document["log"])),
            tuple(account) if account else None)
        if (document["target"] != {"prefix": str(layout.binaries.parent), "manifest": native_transition._target(layout)}
                or str(layout.data) != document["data"] or str(layout.log) != document["log"]):
            raise _error()
        original = document["original"]
        if (set(original) != {"directory", "commitment", "version"}
                or type(original["version"]) is not int or original["version"] not in (160002, 160015)
                or document["fresh"] and original["version"] != 160015):
            raise _error()
        identifier = document["system_identifier"]
        if identifier is None:
            if not document["fresh"]:
                raise _error()
        elif (not isinstance(identifier, str) or not identifier.isdecimal()
              or not 0 < int(identifier) < 2**64):
            raise _error()
        engine = native_engine_store.verify(Path(original["directory"]), original["commitment"])
        if _version(replace(layout, binaries=engine.prefix / "bin")) != original["version"]:
            raise _error()
        return document, layout, engine
    except (KeyError, TypeError, ValueError, OSError, LocalProfileError,
            native_transition.NativeTransitionError, native_engine_store.NativeEngineStoreError):
        raise _error() from None


def recorded_layout(profile):
    layout = native_transition.recorded_layout(profile)
    if layout is not None:
        return layout
    source = _source(profile)
    return source[1] if source else None


def require_admitted(profile):
    if profile.database_engine != "embedded":
        return
    document = read_document(profile.directory / "native-transition.json")
    if document is None or document.get("phase") != "admitted":
        raise _error()
    if native_transition.recorded_layout(profile) is None:
        raise _error()


def _version(layout):
    result = embedded_database._run(layout, "postgres", "--version", capture=True, timeout=30)
    match = re.fullmatch(r"postgres \(PostgreSQL\) (16\.(?:2|15))\s*", result.stdout.decode("utf-8"))
    if result.returncode or match is None:
        raise _error()
    return 160002 if match[1] == "16.2" else 160015


def _cold_source(profile, layout, version):
    control = native_snapshot._control(layout)
    descriptor = os.open(layout.log, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise _error()
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 1024 * 1024))
        text = stream.read().decode("utf-8", "replace")
    starts = re.findall(r"starting PostgreSQL ([0-9]+\.[0-9]+)(?:\s|\.|,)", text)
    if not starts or starts[-1] != f"{version // 10000}.{version % 10000}":
        raise _error()
    return control["system_identifier"]


def _create_source(profile):
    prefix = embedded_database._installation()
    if prefix is None:
        raise _error()
    target = embedded_database._layout_from_source(profile, prefix)
    target = replace(target, data=_directory(target.data), log=_directory(target.log),
                     binaries=_directory(target.binaries))
    native_transition._target(target)
    exists = target.data.exists() or target.data.is_symlink()
    if exists and not (target.data / "PG_VERSION").is_file():
        raise _error()
    if profile.native_engine is not None:
        raise _error()
    fresh = not exists
    source = prefix if fresh else embedded_database._legacy_installation()
    if source is None:
        raise _error()
    store = (embedded_database.SHARED_ROOT / "upgrade-engines" if target.account else
             profile.directory / "native-engines")
    engine = native_engine_store.preserve(source, store, shared=target.account is not None)
    original = replace(target, binaries=engine.prefix / "bin")
    version = _version(original)
    if (fresh and version != 160015) or (not fresh and version != 160002):
        raise _error()
    identifier = None
    if native_transition._open_port(profile.database_port):
        if fresh:
            raise _error()
        _, identifier = native_transition._identity(profile, original, (version,))
    elif not fresh:
        identifier = _cold_source(profile, original, version)
    document = {"version": 1, "profile": _identity(profile),
                "target": {"prefix": str(target.binaries.parent), "manifest": native_transition._target(target)},
                "data": str(target.data), "log": str(target.log),
                "account": list(target.account) if target.account else None,
                "original": {"directory": str(engine.directory), "commitment": engine.commitment, "version": version},
                "fresh": fresh, "system_identifier": identifier}
    write_document(profile.directory / _FILE, document)
    return document, target, engine


def _start_source(profile):
    if native_transition._open_port(profile.api_port):
        raise _error()
    source = _source(profile)
    if source is None:
        source = _create_source(profile)
    document, target, engine = source
    profile = adopt_native_engine(profile)
    original = replace(target, binaries=engine.prefix / "bin")
    exists = target.data.exists() or target.data.is_symlink()
    identifier = document["system_identifier"]
    initialize = document["fresh"] and identifier is None and not exists
    if not initialize and not (target.data / "PG_VERSION").is_file():
        raise _error()
    version = document["original"]["version"]
    if native_transition._open_port(profile.database_port):
        _, observed = native_transition._identity(profile, original, (version,), identifier)
    else:
        if not initialize:
            control = (native_snapshot._control(original)["system_identifier"] if identifier is None else
                       _cold_source(profile, original, version))
            if identifier is not None and control != identifier:
                raise _error()
        embedded_database._start_layout(profile, original, initialize=initialize)
        _, observed = native_transition._identity(profile, original, (version,), identifier)
    if identifier is None:
        write_document(profile.directory / _FILE, {**document, "system_identifier": observed})
    return profile, target, engine


def start_source(profile):
    try:
        with (profile_lock(profile.directory / "lifecycle", timeout=360), profile_lock(profile.directory),
              profile_lock(profile.directory / "supervisor", timeout=0)):
            profile = load_profile(profile.directory)
            layout = native_transition.recorded_layout(profile)
            if layout is not None:
                require_admitted(profile)
                embedded_database._start_layout(profile, layout)
                return
            _start_source(profile)
    except (native_transition.NativeTransitionError, native_engine_store.NativeEngineStoreError,
            native_snapshot.NativeSnapshotError, native_bundle.NativeBundleError) as error:
        raise embedded_database.EmbeddedDatabaseError(error.code, str(error)) from None
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        raise _error() from None


def prepare(profile, bootstrap, *, preflight=None):
    try:
        with (profile_lock(profile.directory / "lifecycle", timeout=360), profile_lock(profile.directory),
              profile_lock(profile.directory / "supervisor", timeout=0)):
            profile = load_profile(profile.directory)
            layout = native_transition.recorded_layout(profile)
            original = None
            if layout is None:
                profile, layout, original = _start_source(profile)
            else:
                profile = adopt_native_engine(profile)
            if preflight is not None and original is not None:
                preflight(profile)
            with native_transition.session(profile, layout, original=original) as transition:
                if preflight is not None and original is None:
                    transition.prepare()
                    preflight(profile)
                transition.admit(lambda: bootstrap(profile))
    except (native_transition.NativeTransitionError, native_engine_store.NativeEngineStoreError,
            native_snapshot.NativeSnapshotError, native_bundle.NativeBundleError) as error:
        raise embedded_database.EmbeddedDatabaseError(error.code, str(error)) from None
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        raise _error() from None
