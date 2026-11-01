import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def remove_test_clusters(tmp_path_factory):
    """Remove embedded database clusters that this run's installations left outside their temporary directory.

    As root, an installation whose directory the database account cannot reach (pytest's 0700 temporary
    directories) keeps its cluster under /var/lib/membrain/clusters, where it would outlive the test run.
    Only clusters of installations created under this run's temporary directory, and not in use, are removed.
    """
    yield
    from membrain.embedded_database import SHARED_ROOT

    clusters = SHARED_ROOT / "clusters"
    if not clusters.is_dir():
        return
    ids = set()
    for profile in Path(tmp_path_factory.getbasetemp()).rglob("profile.json"):
        try:
            value = json.loads(profile.read_text(encoding="utf-8")).get("installation_id")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(value, str) and value:
            ids.add(value)
    try:
        running = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, check=False).stdout
    except OSError:
        return
    for installation in ids:
        cluster = clusters / installation
        if cluster.is_dir() and str(cluster) not in running:
            shutil.rmtree(cluster, ignore_errors=True)
