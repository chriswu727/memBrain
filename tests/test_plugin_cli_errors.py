import argparse

import pytest

from membrain import host, plugin_cli
from membrain.deletion_registry import RegistryError


def test_a_retired_installation_says_how_to_reach_the_restored_one(tmp_path, monkeypatch, capsys):
    def retired(directory):
        raise RegistryError()

    monkeypatch.setattr(host, "installation_status", retired)
    parser = argparse.ArgumentParser()
    plugin_cli.add_commands(parser.add_subparsers(dest="command"))
    with pytest.raises(SystemExit) as stopped:
        plugin_cli.dispatch(parser.parse_args(["plugin", "status", "--directory", str(tmp_path)]))
    assert stopped.value.code == 1
    error = capsys.readouterr().err
    assert "dependency_unavailable" in error and "MEMBRAIN_DIRECTORY" in error and "Traceback" not in error
