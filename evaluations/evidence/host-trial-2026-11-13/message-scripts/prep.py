"""Create a trial memory with its own free ports and the local embedding model (no service started)."""
import shutil
import socket
import sys
from pathlib import Path

from membrain import host
from membrain.local_embeddings import installed, model_directory
from membrain.local_profile import ensure_profile

T = Path("$TRIAL")
CACHE = Path("$PREVIOUS_TRIAL/brain2")


def free_port(taken):
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in taken and 20000 < port < 60000:
            return port


taken = set()
for name in sys.argv[1:]:
    directory = T / name
    directory.mkdir(mode=0o700, exist_ok=True)
    api = free_port(taken)
    taken.add(api)
    db = free_port(taken)
    taken.add(db)
    profile = ensure_profile(directory, database_engine="embedded", api_port=api, database_port=db)
    host.ensure_installation(directory)
    if not installed(directory):
        shutil.copytree(model_directory(CACHE), model_directory(directory), dirs_exist_ok=True)
    print(name, "api", profile.api_port, "db", profile.database_port, "model", bool(installed(directory)))
