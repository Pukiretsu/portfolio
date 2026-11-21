"""Cognito-authorized Minecraft status and allowlisted GitHub dispatch proxy."""

import base64
from functools import lru_cache
import ipaddress
import json
import os
import time
import urllib.error
import urllib.request
import uuid

from protocol import ping
from activity import deadline, healthy, idle_view
import backups


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


@lru_cache
def client(service):
    import boto3
    from botocore.config import Config
    return boto3.client(service, config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1}, **({"signature_version": "s3v4"} if service == "s3" else {})))


def record(key="server"):
    item = client("dynamodb").get_item(
        TableName=os.environ["TABLE_NAME"], Key={"pk": {"S": key}}, ConsistentRead=True,
    ).get("Item", {})
    return {key: int(value["N"]) if "N" in value else value.get("S", "") for key, value in item.items()}


def instances():
    response = client("ec2").describe_instances(Filters=[
        {"Name": "tag:Project", "Values": ["portfolio-minecraft"]},
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped", "shutting-down"]},
    ])
    return [item for reservation in response["Reservations"] for item in reservation["Instances"]]


def status():
    state = record()
    servers = instances()
    busy = state.get("lease_until", 0) > int(time.time())
    phase = "offline"
    telemetry = None
    idle = None
    message = state.get("error", "")
    if busy:
        phase = state.get("phase") if state.get("phase") in ("destroying", "backing_up", "restoring") else "provisioning"
    elif state.get("phase") == "error":
        phase = "error"
    if servers:
        server = servers[0]
        if server.get("InstanceId"):
            idle = idle_view(record("activity#" + server["InstanceId"]), int(time.time()))
            if idle["shutdownRequested"]:
                phase = "error" if state.get("phase") == "error" or not idle["monitoringHealthy"] else "destroying"
                message = message or "Idle deadline reached. Minecraft stopped gracefully; Terraform cleanup is pending."
        if phase != "destroying" and not (idle and idle["shutdownRequested"]):
            if not busy:
                phase = "provisioning"
            ip = server.get("PublicIpAddress", "")
            if server["State"]["Name"] == "running" and ip and ipaddress.ip_address(ip).is_global:
                try:
                    telemetry = ping(ip, os.environ["SERVER_ADDRESS"])
                    if not busy:
                        phase = "online"
                except (OSError, ValueError, TypeError, KeyError):
                    age = time.time() - server["LaunchTime"].timestamp()
                    if age > 1200 and not busy and time.time() - state.get("updated_at", 0) > 180:
                        phase = "error"
                        message = "EC2 exists but Minecraft is not responding. Review the deploy workflow and bootstrap logs."
            elif server["State"]["Name"] in ("stopped", "stopping"):
                phase = "offline"
                message = "Server resources still exist. Destroy them before launching again."
    return {
        "phase": phase, "busy": busy, "resourcesExist": bool(servers),
        "address": os.environ["SERVER_ADDRESS"], "port": 25565,
        "telemetry": telemetry, "message": message,
        "idle": idle,
        "workflowUrl": state.get("workflow_url", ""),
        "acceptEula": os.environ.get("ACCEPT_EULA") == "true",
        "updatedAt": int(time.time()),
    }


def fail_operation(operation_id, message, release):
    values = {":id": {"S": operation_id}, ":phase": {"S": "error"}, ":error": {"S": message}}
    expression = "SET #phase=:phase, #error=:error"
    if release:
        expression += ", lease_until=:zero"
        values[":zero"] = {"N": "0"}
    client("dynamodb").update_item(
        TableName=os.environ["TABLE_NAME"], Key={"pk": {"S": "server"}},
        UpdateExpression=expression, ConditionExpression="operation_id=:id",
        ExpressionAttributeNames={"#phase": "phase", "#error": "error"}, ExpressionAttributeValues=values,
    )


def dispatch(action, body, *, automatic_instance_id=None):
    if action not in ('deploy', 'destroy', 'backup', 'restore'):
        raise ApiError(400, 'Unknown operation')
    object_key = None
    identity = None
    if action in ('backup', 'restore'):
        servers = instances()
        if len(servers) != 1 or servers[0]['State']['Name'] != 'running':
            raise ApiError(409, 'Launch the server and wait for it to be ready before transferring a map')
        identity = servers[0]['InstanceId']
        activity = record('activity#' + identity)
        if activity.get('shutdown_requested'):
            raise ApiError(409, 'Idle destruction has already started')
        if action == 'restore':
            if body.get('confirmRestore') is not True:
                raise ApiError(400, 'Confirm replacement of the running world')
            try:
                object_key = backups.existing(client('s3'), body.get('key'))
            except ValueError as error:
                raise ApiError(400, str(error)) from error
        else:
            object_key = 'backups/' + str(uuid.uuid4()) + '.zip'
    operation_phase = {'deploy': 'provisioning', 'destroy': 'destroying', 'backup': 'backing_up', 'restore': 'restoring'}[action]
    if action == "destroy" and body.get("confirmDestroy") is not True:
        raise ApiError(400, "Confirm that destroying the server permanently deletes its world and disk.")
    if action == "deploy":
        if os.environ.get("ACCEPT_EULA") != "true":
            raise ApiError(409, "The owner must first set MINECRAFT_ACCEPT_EULA=true after accepting the Minecraft EULA.")
        if instances():
            raise ApiError(409, "Server resources already exist. Destroy them before starting a new deployment.")
    try:
        token = client("secretsmanager").get_secret_value(SecretId=os.environ["GITHUB_SECRET"])["SecretString"].strip()
        if not token:
            raise ValueError("Empty credential")
    except Exception as error:
        raise ApiError(503, "The GitHub dispatcher credential is not configured. Set MINECRAFT_GH_TOKEN and run infrastructure deployment.") from error
    operation_id = str(uuid.uuid4())
    now = int(time.time())
    try:
        client("dynamodb").update_item(
            TableName=os.environ["TABLE_NAME"], Key={"pk": {"S": "server"}},
            UpdateExpression="SET operation_id=:id, #phase=:phase, lease_until=:lease, updated_at=:now, #error=:empty REMOVE workflow_url",
            ConditionExpression="attribute_not_exists(lease_until) OR lease_until < :now",
            ExpressionAttributeNames={"#phase": "phase", "#error": "error"},
            ExpressionAttributeValues={":id": {"S": operation_id}, ":phase": {"S": operation_phase}, ":lease": {"N": str(now + 3600)}, ":now": {"N": str(now)}, ":empty": {"S": ""}},
        )
    except Exception as error:
        if getattr(error, "response", {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ApiError(409, "Another operation is already running. Wait for it to finish.") from error
        raise
    inputs = {"operation_id": operation_id}
    if action == "destroy":
        inputs["confirm_destroy"] = "true"
        if automatic_instance_id:
            inputs["automatic"] = "true"
            inputs["expected_instance_id"] = automatic_instance_id
    workflow = action
    if action in ('backup', 'restore'):
        workflow = 'backup'
        inputs.update(action=action, object_key=object_key, expected_instance_id=identity)
    request = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPO']}/actions/workflows/minecraft-{workflow}.yml/dispatches",
        data=json.dumps({"ref": "main", "inputs": inputs}).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "portfolio-minecraft-launcher", "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status not in (200, 204):
                raise urllib.error.URLError("Unexpected dispatch response")
    except urllib.error.HTTPError as error:
        fail_operation(operation_id, "GitHub rejected dispatch. Check the token's repository Actions-write permission and workflow files.", release=True)
        raise ApiError(502, "GitHub rejected the workflow request. Check the dispatcher credential and repository configuration.") from error
    except (OSError, urllib.error.URLError) as error:
        # A timeout may occur after GitHub accepted the request. Keep the lease to avoid duplicates.
        fail_operation(operation_id, "Dispatch outcome is uncertain. Check GitHub Actions before retrying; the safety lease expires in one hour.", release=False)
        raise ApiError(502, "Dispatch could not be confirmed. Check GitHub Actions before retrying.") from error
    return {"operationId": operation_id, "phase": operation_phase}


def idle_check():
    now = int(time.time())
    if record().get("lease_until", 0) > now:
        return {"skipped": "operation_in_progress"}
    for server in instances():
        if server["State"]["Name"] != "running":
            continue
        identity = server["InstanceId"]
        activity = record("activity#" + identity)
        end = deadline(activity)
        # Only the matching instance's fresh, graceful-stop acknowledgement permits deletion.
        if healthy(activity, now) and activity.get("shutdown_requested") and end and now >= end:
            return dispatch("destroy", {"confirmDestroy": True}, automatic_instance_id=identity)
    return {"skipped": "no_confirmed_idle_shutdown"}


def handler(event, context):
    try:
        rule = os.environ.get("IDLE_RULE_ARN")
        if rule and event.get("source") == "aws.events" and event.get("detail-type") == "Scheduled Event" and event.get("resources") == [rule]:
            return {"statusCode": 200, "body": json.dumps(idle_check())}
        # API Gateway verifies signature, issuer, client ID, expiry and scope first.
        # No Function URL is exposed, and the invoke permission is restricted to this API.
        claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
        if claims.get("token_use") != "access" or claims.get("client_id") != os.environ["COGNITO_CLIENT"] or not claims.get("sub"):
            raise ApiError(403, "A valid Tools access token is required.")
        route = event.get("routeKey", "")
        if route == "GET /minecraft/status":
            data, code = status(), 200
        elif route == 'GET /minecraft/backups':
            try:
                data = backups.catalog(client('s3'), (event.get('queryStringParameters') or {}).get('cursor'))
                code = 200
            except ValueError as error:
                raise ApiError(400, str(error)) from error
        elif route in ("POST /minecraft/deploy", "POST /minecraft/destroy", "POST /minecraft/backup", "POST /minecraft/restore", "POST /minecraft/backups/upload", "POST /minecraft/backups/download"):
            raw = event.get("body") or "{}"
            if not isinstance(raw, str) or len(raw) > 2048:
                raise ApiError(400, "Request is too large.")
            try:
                if event.get("isBase64Encoded"):
                    raw = base64.b64decode(raw, validate=True).decode()
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError()
            except (ValueError, UnicodeError) as error:
                raise ApiError(400, "A JSON object is required.") from error
            if route in ('POST /minecraft/backups/upload', 'POST /minecraft/backups/download'):
                try:
                    operation = backups.upload if route.endswith('/upload') else backups.download
                    data, code = operation(client('s3'), body), 200
                except ValueError as error:
                    raise ApiError(400, str(error)) from error
            else:
                data, code = dispatch(route.rsplit("/", 1)[1], body), 202
        else:
            raise ApiError(404, "Unknown endpoint.")
    except ApiError as error:
        data, code = {"message": error.message}, error.status
    except Exception as error:
        print(json.dumps({"event": "proxy_error", "type": type(error).__name__}))
        data, code = {"message": "Control service unavailable. Try again shortly."}, 503
    return {"statusCode": code, "headers": {"content-type": "application/json", "cache-control": "no-store"}, "body": json.dumps(data)}
