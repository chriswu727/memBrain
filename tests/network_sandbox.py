"""Run a process tree where every network connection it attempts is recorded and none can leave the computer.

``python -I network_sandbox.py RESULT.json SECONDS -- COMMAND ...`` re-runs itself under
``unshare --map-current-user --net --mount --keep-caps`` (no root: an unprivileged user namespace, the user keeps
its own uid). Inside, the network namespace has only a loopback interface with every IPv4 and IPv6 address routed
to it; /etc/resolv.conf is replaced, in the namespace only, by a resolver on 127.0.0.1 that records each name asked
for and answers it with an address of its own in 198.18.0.0/15; a packet socket on the loopback interface records
every TCP connection attempt and UDP datagram, whatever library or language makes it. Nothing answers those
addresses, so an attempt is refused at once and nothing is sent anywhere. COMMAND runs with that view of the
network; SECONDS bounds it. When it ends, every process left in the namespace (a detached service, its database)
is stopped. RESULT.json gets the names asked for and the attempts, each with the name its address was given for.

Needs Linux with unprivileged user namespaces, ``unshare`` (util-linux 2.39 or later for ``--keep-caps``) and
``ip`` (iproute2). ``available()`` says whether they work here.
"""
from __future__ import annotations

import ipaddress
import json
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

INSIDE = "MEMBRAIN_NETWORK_SANDBOX_INSIDE"
ADDRESSES = ipaddress.ip_network("198.18.0.0/15")
UNSHARE = ["unshare", "--map-current-user", "--net", "--mount", "--keep-caps"]


def available() -> bool:
    if sys.platform != "linux" or not shutil.which("unshare") or not shutil.which("ip"):
        return False
    try:
        return subprocess.run([*UNSHARE, "ip", "link", "set", "lo", "up"], capture_output=True,
                              timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run(result: Path, seconds: float, command: list[str], env: dict[str, str]) -> dict:
    """Run ``command`` in the sandbox and return what it attempted."""
    sandbox = [*UNSHARE, sys.executable, "-I", os.path.abspath(__file__), str(result), str(seconds), "--", *command]
    subprocess.run(sandbox, env={**env, INSIDE: "1"}, check=True, timeout=seconds + 120)
    return json.loads(Path(result).read_text(encoding="utf-8"))


class _Record:
    def __init__(self):
        self.started = time.monotonic()
        self.names: dict[str, str] = {}
        self.lookups: list[dict] = []
        self.attempts: list[dict] = []
        self.lock = threading.Lock()

    def now(self) -> float:
        return round(time.monotonic() - self.started, 2)

    def address(self, name: str) -> str:
        with self.lock:
            for address, known in self.names.items():
                if known == name:
                    return address
            address = str(ADDRESSES.network_address + len(self.names) + 1)
            self.names[address] = name
            return address


def _resolver(record: _Record, server: socket.socket) -> None:
    while True:
        try:
            data, peer = server.recvfrom(4096)
            ident, flags = struct.unpack("!HH", data[:4])
            labels, offset = [], 12
            while data[offset]:
                labels.append(data[offset + 1:offset + 1 + data[offset]].decode("ascii", "replace"))
                offset += 1 + data[offset]
            question = data[12:offset + 5]
            kind = struct.unpack("!H", data[offset + 1:offset + 3])[0]
            name = ".".join(labels).lower()
            record.lookups.append({"t": record.now(), "name": name, "type": kind})
            answer = b""
            if kind == 1:
                answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 5, 4) + socket.inet_aton(record.address(name))
            header = struct.pack("!HHHHHH", ident, 0x8180 | (flags & 0x0100), 1, 1 if answer else 0, 0, 0)
            server.sendto(header + question + answer, peer)
        except Exception:  # noqa: BLE001 - a malformed query must not stop the resolver
            continue


def _capture(record: _Record, stop: threading.Event) -> None:
    packets = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
    packets.bind(("lo", 0))
    packets.settimeout(0.3)
    while not stop.is_set():
        try:
            frame, meta = packets.recvfrom(65535)
        except TimeoutError:
            continue
        if meta[2] != socket.PACKET_OUTGOING:
            continue
        kind, packet = struct.unpack("!H", frame[12:14])[0], frame[14:]
        if kind == 0x0800:
            protocol, header = packet[9], (packet[0] & 0x0F) * 4
            destination, body = socket.inet_ntoa(packet[16:20]), packet[header:]
        elif kind == 0x86DD:
            protocol, destination, body = packet[6], socket.inet_ntop(socket.AF_INET6, packet[24:40]), packet[40:]
        else:
            continue
        if protocol not in (6, 17) or len(body) < 14:
            continue
        port = struct.unpack("!H", body[2:4])[0]
        if protocol == 6 and not (body[13] & 0x02 and not body[13] & 0x10):
            continue  # TCP: only the opening SYN is an attempt
        if ipaddress.ip_address(destination.removeprefix("::ffff:")).is_loopback:
            if protocol == 17 and port == 53:
                continue  # a lookup, recorded by the resolver
            loopback = True
        else:
            loopback = False
        if not loopback:
            record.attempts.append({"t": record.now(), "protocol": "tcp" if protocol == 6 else "udp",
                                    "address": destination, "port": port,
                                    "name": record.names.get(destination.removeprefix("::ffff:"))})


def _stop_namespace() -> None:
    """Stop every process left in this network namespace (a detached service and its database)."""
    mine = os.readlink("/proc/self/ns/net")
    for attempt in (signal.SIGTERM, signal.SIGKILL):
        left = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit() or int(entry.name) == os.getpid():
                continue
            try:
                if os.readlink(entry / "ns" / "net") == mine:
                    os.kill(int(entry.name), attempt)
                    left.append(int(entry.name))
            except OSError:
                continue
        if not left:
            return
        time.sleep(5 if attempt == signal.SIGTERM else 1)


def _inside(arguments: list[str]) -> None:
    result, seconds = Path(arguments[0]), float(arguments[1])
    command = arguments[arguments.index("--") + 1:]
    for step in (["ip", "link", "set", "lo", "up"], ["ip", "route", "add", "local", "0.0.0.0/0", "dev", "lo"],
                 ["ip", "-6", "route", "add", "local", "::/0", "dev", "lo"]):
        subprocess.run(step, check=True)
    resolv = result.with_suffix(".resolv.conf")
    resolv.write_text("nameserver 127.0.0.1\noptions attempts:1 timeout:2\n", encoding="utf-8")
    subprocess.run(["mount", "--bind", str(resolv), "/etc/resolv.conf"], check=True)
    record, stop = _Record(), threading.Event()
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 53))
    threading.Thread(target=_resolver, args=(record, server), daemon=True).start()
    threading.Thread(target=_capture, args=(record, stop), daemon=True).start()
    time.sleep(0.2)
    environment = {key: value for key, value in os.environ.items() if key != INSIDE}
    child = subprocess.Popen(command, env=environment, start_new_session=True)
    try:
        status = child.wait(seconds)
    except subprocess.TimeoutExpired:
        status = None
    _stop_namespace()
    time.sleep(0.5)
    stop.set()
    result.write_text(json.dumps({"exit": status, "lookups": record.lookups, "attempts": record.attempts},
                                 indent=1), encoding="utf-8")


if __name__ == "__main__":
    if os.environ.get(INSIDE) != "1":
        raise SystemExit("Run through network_sandbox.run().")
    _inside(sys.argv[1:])
