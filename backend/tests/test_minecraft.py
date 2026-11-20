import datetime
import io
import json
import os
import runpy
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "minecraft_proxy"))
import app
import protocol


ENV = {"COGNITO_CLIENT": "expected-client", "TABLE_NAME": "control", "GITHUB_SECRET": "secret-arn", "GITHUB_REPO": "Pukiretsu/portfolio", "SERVER_ADDRESS": "mc.example.com", "ACCEPT_EULA": "true"}


def event(route, body=None, **claims):
    return {"routeKey": route, "body": json.dumps(body or {}), "requestContext": {"authorizer": {"jwt": {"claims": {"token_use": "access", "client_id": "expected-client", "sub": "user", **claims}}}}}


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_missing_authorizer_and_id_tokens_fail_closed(self):
        with patch.object(app, "client") as client:
            self.assertEqual(app.handler({}, None)["statusCode"], 403)
            self.assertEqual(app.handler(event("GET /minecraft/status", token_use="id"), None)["statusCode"], 403)
            self.assertEqual(app.handler(event("GET /minecraft/status", client_id="other-client"), None)["statusCode"], 403)
            client.assert_not_called()

    def test_destroy_requires_explicit_boolean_confirmation(self):
        with patch.object(app, "client") as client:
            self.assertEqual(app.handler(event("POST /minecraft/destroy", {"confirmDestroy": "true"}), None)["statusCode"], 400)
            client.assert_not_called()

    def test_eula_must_be_accepted_before_launch(self):
        with patch.dict(os.environ, {"ACCEPT_EULA": "false"}), patch.object(app, "client") as client:
            self.assertEqual(app.handler(event("POST /minecraft/deploy"), None)["statusCode"], 409)
            client.assert_not_called()

    def test_unknown_route_and_invalid_json_are_rejected(self):
        self.assertEqual(app.handler(event("POST /minecraft/anything"), None)["statusCode"], 404)
        request = event("POST /minecraft/deploy")
        request["body"] = "not JSON"
        self.assertEqual(app.handler(request, None)["statusCode"], 400)
        request["isBase64Encoded"] = True
        self.assertEqual(app.handler(request, None)["statusCode"], 400)

    def test_existing_instance_prevents_duplicate_deploy(self):
        with patch.object(app, "instances", return_value=[{"id": "existing"}]):
            self.assertEqual(app.handler(event("POST /minecraft/deploy"), None)["statusCode"], 409)

    def test_workflow_dispatch_is_allowlisted_and_has_no_client_credentials(self):
        clients = {service: MagicMock() for service in ("dynamodb", "secretsmanager")}
        clients["secretsmanager"].get_secret_value.return_value = {"SecretString": "private-token"}
        response = MagicMock()
        response.__enter__.return_value.status = 204
        with patch.object(app, "client", side_effect=clients.__getitem__), patch("urllib.request.urlopen", return_value=response) as send:
            result = app.handler(event("POST /minecraft/destroy", {"confirmDestroy": True, "workflow": "evil.yml", "ref": "evil"}), None)
        self.assertEqual(result["statusCode"], 202)
        request = send.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/minecraft-destroy.yml/dispatches"))
        data = json.loads(request.data)
        self.assertEqual(data["ref"], "main")
        self.assertEqual(data["inputs"]["confirm_destroy"], "true")
        self.assertNotIn("private-token", result["body"])
        lock = clients["dynamodb"].update_item.call_args.kwargs
        self.assertIn("lease_until < :now", lock["ConditionExpression"])

    def test_conflicting_operation_does_not_dispatch(self):
        error = RuntimeError("lock conflict")
        error.response = {"Error": {"Code": "ConditionalCheckFailedException"}}
        client = MagicMock()
        client.get_secret_value.return_value = {"SecretString": "private-token"}
        client.update_item.side_effect = error
        with patch.object(app, "client", return_value=client), patch("urllib.request.urlopen") as send:
            self.assertEqual(app.handler(event("POST /minecraft/destroy", {"confirmDestroy": True}), None)["statusCode"], 409)
            send.assert_not_called()

    def test_ambiguous_github_timeout_keeps_safety_lease(self):
        client = MagicMock()
        client.get_secret_value.return_value = {"SecretString": "private-token"}
        with patch.object(app, "client", return_value=client), patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")), patch.object(app, "fail_operation") as fail:
            self.assertEqual(app.handler(event("POST /minecraft/destroy", {"confirmDestroy": True}), None)["statusCode"], 502)
            self.assertFalse(fail.call_args.kwargs["release"])

    def test_status_probes_only_ec2_address_not_user_input(self):
        instance = {"State": {"Name": "running"}, "PublicIpAddress": "8.8.8.8", "LaunchTime": datetime.datetime.now(datetime.timezone.utc)}
        with patch.object(app, "record", return_value={}), patch.object(app, "instances", return_value=[instance]), patch.object(app, "ping", return_value={"playersOnline": 2}) as ping:
            result = app.handler(event("GET /minecraft/status", {"host": "169.254.169.254"}), None)
            ping.assert_called_once_with("8.8.8.8", "mc.example.com")
            self.assertEqual(json.loads(result["body"])["phase"], "online")

    def test_private_probe_addresses_are_not_contacted(self):
        instance = {"State": {"Name": "running"}, "PublicIpAddress": "169.254.169.254"}
        with patch.object(app, "record", return_value={}), patch.object(app, "instances", return_value=[instance]), patch.object(app, "ping") as ping:
            app.status()
            ping.assert_not_called()


class ProtocolTests(unittest.TestCase):
    def test_fragmented_varints_and_truncation(self):
        class Reader:
            def __init__(self, data): self.data = io.BytesIO(data)
            def recv(self, size): return self.data.read(min(size, 1))
        self.assertEqual(protocol.read_varint(Reader(protocol.varint(300))), 300)
        with self.assertRaises(ValueError): protocol.read_varint(Reader(b"\xff" * 6))
        with self.assertRaises(ValueError): protocol.read_exact(Reader(b""), 2)

    def test_real_status_packet_parsing(self):
        data = json.dumps({"players": {"online": 2, "max": 10}, "version": {"name": "1.21.11"}, "description": {"text": "§aHello", "extra": [{"text": " world"}]}}).encode()
        packet = b"\x00" + protocol.varint(len(data)) + data
        stream = MagicMock()
        reader = io.BytesIO(protocol.varint(len(packet)) + packet)
        stream.recv.side_effect = lambda count: reader.read(min(count, 3))
        context = MagicMock()
        context.__enter__.return_value = stream
        with patch("socket.create_connection", return_value=context):
            result = protocol.ping("8.8.8.8", "mc.example.com")
        self.assertEqual(result["playersOnline"], 2)
        self.assertEqual(result["motd"], "Hello world")
        stream.sendall.assert_called_once()

    def test_oversized_status_packet_is_rejected(self):
        stream = MagicMock()
        reader = io.BytesIO(protocol.varint(999999))
        stream.recv.side_effect = reader.read
        context = MagicMock()
        context.__enter__.return_value = stream
        with patch("socket.create_connection", return_value=context), self.assertRaises(ValueError):
            protocol.ping("8.8.8.8", "mc.example.com")


class WorkflowSafetyTests(unittest.TestCase):
    def test_manual_launch_refuses_existing_instance(self):
        script = Path(__file__).resolve().parents[2] / ".github/scripts/minecraft-control.py"
        check = runpy.run_path(str(script))["ensure_offline"]
        with patch.dict(check.__globals__, {"aws": lambda *args: {"Reservations": [{"Instances": [{"InstanceId": "existing"}]}]}}):
            with self.assertRaises(RuntimeError):
                check()
        with patch.dict(check.__globals__, {"aws": lambda *args: {"Reservations": []}}):
            check()


if __name__ == "__main__":
    unittest.main()
