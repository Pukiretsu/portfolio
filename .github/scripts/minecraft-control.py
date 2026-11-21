"""Shared state, DNS/readiness checks, and teardown verification for both workflows."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

TABLE = "portfolio-minecraft-control"


def aws(*args, missing_ok=False):
    result = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True)
    if result.returncode:
        if missing_ok and any(code in result.stderr for code in ("InvalidInstanceID.NotFound", "InvalidVolume.NotFound")):
            return {}
        raise RuntimeError("AWS operation failed: " + " ".join(args[:2]))
    return json.loads(result.stdout) if result.stdout.strip() else {}


def begin(action):
    value = os.environ.get("INPUT_OPERATION_ID", "").strip()
    operation = str(uuid.UUID(value)) if value else str(uuid.uuid4())
    now = int(time.time())
    run_url = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    aws("dynamodb", "update-item", "--table-name", TABLE, "--key", '{"pk":{"S":"server"}}',
        "--update-expression", "SET operation_id=:id, #phase=:phase, lease_until=:lease, updated_at=:now, workflow_url=:url, #error=:empty",
        "--condition-expression", "attribute_not_exists(lease_until) OR lease_until < :now OR operation_id=:id",
        "--expression-attribute-names", '{"#phase":"phase","#error":"error"}',
        "--expression-attribute-values", json.dumps({":id": {"S": operation}, ":phase": {"S": {"deploy": "provisioning", "destroy": "destroying", "backup": "backing_up", "restore": "restoring"}[action]}, ":lease": {"N": str(now + 3600)}, ":now": {"N": str(now)}, ":url": {"S": run_url}, ":empty": {"S": ""}}))
    with open(os.environ["GITHUB_ENV"], "a") as output:
        output.write("MINECRAFT_OPERATION_ID=" + operation + "\n")
    print("Minecraft operation claimed; other launcher requests are locked until completion.")


def finish(action):
    operation = os.environ.get("MINECRAFT_OPERATION_ID")
    if not operation:
        return
    if os.environ.get('MINECRAFT_MAP_COMMAND_SENT') and not os.environ.get('MINECRAFT_MAP_COMMAND_ID'):
        print('SSM dispatch outcome is uncertain. Keeping the safety lease.')
        return
    if os.environ.get('MINECRAFT_MAP_COMMAND_ID'):
        try:
            command = aws('ssm', 'get-command-invocation', '--command-id', os.environ['MINECRAFT_MAP_COMMAND_ID'], '--instance-id', os.environ['MAP_INSTANCE_ID'])
            if command['Status'] in ('Pending', 'InProgress', 'Delayed', 'Cancelling'):
                print('SSM map command is still active. Keeping the safety lease until it expires.')
                return
        except Exception:
            print('Cannot confirm map command completion. Keeping the safety lease.')
            return
    success = os.environ.get("JOB_STATUS") == "success"
    phase = ("offline" if action == "destroy" else "online") if success else "error"
    aws("dynamodb", "update-item", "--table-name", TABLE, "--key", '{"pk":{"S":"server"}}',
        "--update-expression", "SET #phase=:phase, lease_until=:zero, #error=:error, updated_at=:now",
        "--condition-expression", "operation_id=:id",
        "--expression-attribute-names", '{"#phase":"phase","#error":"error"}',
        "--expression-attribute-values", json.dumps({":id": {"S": operation}, ":phase": {"S": phase}, ":zero": {"N": "0"}, ":error": {"S": "" if success else "Workflow failed or was cancelled. Review GitHub Actions; server resources may still exist."}, ":now": {"N": str(int(time.time()))}}))


def outputs():
    result = subprocess.run(["terraform", "output", "-json"], capture_output=True, text=True, check=True)
    return {key: value["value"] for key, value in json.loads(result.stdout).items()}


def dns_records():
    query = urllib.parse.urlencode({"name": "mc." + os.environ["TF_VAR_domain_name"], "per_page": 100})
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/zones/{os.environ['TF_VAR_cloudflare_zone_id']}/dns_records?{query}",
        headers={"Authorization": "Bearer " + os.environ["TF_VAR_cloudflare_api_token"]},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = json.load(response)
    if not body.get("success"):
        raise RuntimeError("Cloudflare DNS verification failed")
    return [record for record in body["result"] if record["type"] in ("A", "AAAA")]


def verify_deploy():
    values = outputs()
    host, ipv6, ipv4 = values["connection_address"], values["ipv6_address"], values["ipv4_address"]
    for attempt in range(36):
        records = dns_records()
        correct = {item["type"]: item for item in records}
        try:
            public = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, 25565, socket.AF_INET6)}
        except socket.gaierror:
            public = set()
        if ("AAAA" in correct and "A" in correct and not any(item.get("proxied") for item in records)
                and ipaddress.ip_address(correct["AAAA"]["content"]) == ipaddress.ip_address(ipv6)
                and correct["A"]["content"] == ipv4 and ipaddress.ip_address(ipv6) in public):
            break
        time.sleep(10)
    else:
        raise RuntimeError("Minecraft DNS did not propagate to the allocated IPv6 address")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "minecraft_proxy"))
    from protocol import ping
    for attempt in range(60):
        try:
            ping(ipv4, host)
            print(f"Minecraft is online at {host}:25565 (IPv6: {ipv6}).")
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
                summary.write(f"Minecraft ready: `{host}:25565`\n\nIPv6: `{ipv6}`\n")
            return
        except (OSError, ValueError):
            time.sleep(15)
    raise RuntimeError("EC2 exists, but Minecraft did not become ready. Inspect /var/log/minecraft-bootstrap.log.")


def snapshot():
    Path(os.environ["INVENTORY_FILE"]).write_text(json.dumps(outputs()))


def ensure_offline():
    response = aws("ec2", "describe-instances", "--filters", json.dumps([
        {"Name": "tag:Project", "Values": ["portfolio-minecraft"]},
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped", "shutting-down"]},
    ]))
    if any(reservation.get("Instances") for reservation in response.get("Reservations", [])):
        raise RuntimeError("A Minecraft instance already exists. Use the confirmed destroy workflow before launching again; this prevents AMI updates replacing a live world.")


def verify_auto_shutdown():
    expected = os.environ.get("INPUT_EXPECTED_INSTANCE_ID", "")
    if not expected or outputs().get("instance_id") != expected:
        raise RuntimeError("Automatic cleanup no longer matches the instance in Terraform state")
    item = aws("dynamodb", "get-item", "--table-name", TABLE, "--key", json.dumps({"pk": {"S": "activity#" + expected}}), "--consistent-read").get("Item", {})
    activity = {key: int(value["N"]) for key, value in item.items() if "N" in value}
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "minecraft_proxy"))
    from activity import deadline, healthy
    end = deadline(activity)
    now = int(time.time())
    if not healthy(activity, now) or not activity.get("shutdown_requested") or not end or now < end:
        raise RuntimeError("Fresh idle deadline and graceful-stop acknowledgement are required for automatic cleanup")
    from protocol import ping
    server = outputs()
    try:
        ping(server["ipv4_address"], server["connection_address"])
    except (OSError, ValueError):
        return
    raise RuntimeError("Minecraft is responding again; refusing automatic world deletion")


def verify_destroy():
    values = json.loads(Path(os.environ["INVENTORY_FILE"]).read_text())
    state = subprocess.run(["terraform", "state", "list"], capture_output=True, text=True, check=True)
    if state.stdout.strip():
        raise RuntimeError("Minecraft Terraform state still contains resources")
    for attempt in range(30):
        remaining = False
        if values.get("instance_id"):
            response = aws("ec2", "describe-instances", "--instance-ids", values["instance_id"], missing_ok=True)
            remaining = any(instance["State"]["Name"] != "terminated" for reservation in response.get("Reservations", []) for instance in reservation["Instances"])
        for volume in values.get("volume_ids", []):
            remaining |= bool(aws("ec2", "describe-volumes", "--volume-ids", volume, missing_ok=True).get("Volumes"))
        remaining |= bool(dns_records())
        if not remaining:
            print("Verified: EC2 terminated, world disk deleted, Minecraft A/AAAA records removed, Terraform state empty.")
            return
        time.sleep(10)
    raise RuntimeError("Teardown verification timed out; inspect EC2, EBS, and Cloudflare before relaunching")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["begin", "finish", "verify-deploy", "snapshot", "verify-destroy", "ensure-offline", "verify-auto-shutdown"])
    parser.add_argument("--action", choices=["deploy", "destroy", "backup", "restore"])
    args = parser.parse_args()
    if args.command in ("begin", "finish") and not args.action:
        parser.error("--action is required")
    try:
        {"begin": lambda: begin(args.action), "finish": lambda: finish(args.action), "verify-deploy": verify_deploy, "snapshot": snapshot, "verify-destroy": verify_destroy, "ensure-offline": ensure_offline, "verify-auto-shutdown": verify_auto_shutdown}[args.command]()
    except Exception as error:
        print("Minecraft workflow check failed: " + str(error), file=sys.stderr)
        sys.exit(1)
