"""Runs on EC2. Stops Java only; AWS resource deletion always uses Terraform."""

import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

from activity import deadline, observe
from protocol import ping

STATE = Path("/var/lib/minecraft-monitor/state.json")
LOG = Path("/srv/minecraft/logs/latest.log")
EVENT = re.compile(r"\[Server thread/INFO\](?: \[[^\]]+\])?: [A-Za-z0-9_]{1,16} (joined|left) the game(?:\s|$)")


def instance_id():
    request = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT", headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
    with urllib.request.urlopen(request, timeout=3) as response:
        token = response.read().decode()
    request = urllib.request.Request("http://169.254.169.254/latest/meta-data/instance-id", headers={"X-aws-ec2-metadata-token": token})
    with urllib.request.urlopen(request, timeout=3) as response:
        value = response.read().decode()
    if not re.fullmatch(r"i-[0-9a-f]+", value):
        raise ValueError("Invalid instance identity")
    return value


def publish(identity, state):
    fields = {key: {"N": str(int(value))} for key, value in state.items() if key in ("ready_at", "players_online", "ever_joined", "empty_since", "heartbeat_at", "shutdown_requested")}
    fields["expires_at"] = {"N": str(int(time.time()) + 86400)}
    names = {"#" + key: key for key in fields}
    values = {":" + key: value for key, value in fields.items()}
    expression = "SET " + ", ".join("#" + key + "=:" + key for key in fields)
    result = subprocess.run([
        "aws", "dynamodb", "update-item", "--region", os.environ["AWS_DEFAULT_REGION"],
        "--table-name", "portfolio-minecraft-control", "--key", json.dumps({"pk": {"S": "activity#" + identity}}),
        "--update-expression", expression, "--expression-attribute-names", json.dumps(names),
        "--expression-attribute-values", json.dumps(values),
    ], capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError("Activity heartbeat could not be published")


def save(state):
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    temporary.replace(STATE)


def main():
    identity = instance_id()
    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        state = {}
    if state.get("instance_id") != identity:
        state = {"instance_id": identity}
    while True:
        try:
            now = int(time.time())
            joined, left = False, False
            if LOG.exists():
                stat = LOG.stat()
                offset = state.get("log_offset", 0)
                if state.get("log_inode") != stat.st_ino or stat.st_size < offset:
                    offset = 0
                with LOG.open() as logfile:
                    logfile.seek(offset)
                    lines = logfile.read(1024 * 1024)
                    # Keep incomplete lines for the next iteration.
                    complete = lines.rsplit("\n", 1)[0] if "\n" in lines else ""
                    if complete:
                        state["log_offset"] = offset + len((complete + "\n").encode())
                    state["log_inode"] = stat.st_ino
                    events = EVENT.findall(complete)
                    joined, left = "joined" in events, "left" in events
            if joined:
                state["pending_joined"] = 1
                state["ever_joined"] = 1
            if left:
                state["pending_left"] = 1
            if state.get("shutdown_requested"):
                state["heartbeat_at"] = now
            else:
                try:
                    players = ping("127.0.0.1", "localhost")["playersOnline"]
                except (OSError, ValueError):
                    # A failed probe is never interpreted as an empty server.
                    if joined:
                        state["ever_joined"] = 1
                    time.sleep(10)
                    continue
                state = observe(state, now, players, bool(state.get("pending_joined")), bool(state.get("pending_left")))
                state.pop("pending_joined", None)
                state.pop("pending_left", None)
            publish(identity, state)
            end = deadline(state)
            if not state.get("shutdown_requested") and end and now >= end:
                # Stop accepting connections and save the world before queueing deletion.
                subprocess.run(["systemctl", "stop", "minecraft.service"], check=True, timeout=135)
                state["shutdown_requested"] = 1
                state["heartbeat_at"] = int(time.time())
                save(state)
                publish(identity, state)
                print("Idle deadline reached; Minecraft stopped gracefully. Awaiting Terraform destroy.", flush=True)
            save(state)
        except Exception as error:
            print("Activity monitor check failed: " + type(error).__name__, flush=True)
        time.sleep(10)


if __name__ == "__main__":
    main()
