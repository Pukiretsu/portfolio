import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "minecraft_proxy"))
from activity import deadline, healthy, idle_view, observe
from activity_monitor import EVENT
import activity_monitor
import app


class IdlePolicyTests(unittest.TestCase):
    def test_first_empty_server_gets_thirty_minutes(self):
        state = observe({}, 100, 0)
        self.assertEqual(deadline(state), 1900)
        self.assertEqual(deadline(observe(state, 500, 0)), 1900)

    def test_players_pause_timer_and_leaving_starts_ten_minutes(self):
        state = observe({}, 100, 0)
        state = observe(state, 300, 2)
        self.assertEqual(state["ever_joined"], 1)
        self.assertIsNone(deadline(state))
        state = observe(state, 400, 0)
        self.assertEqual(deadline(state), 1000)
        self.assertEqual(deadline(observe(state, 800, 0)), 1000)

    def test_rejoining_resets_empty_time(self):
        state = observe({}, 100, 1)
        state = observe(state, 200, 0)
        state = observe(state, 700, 1)
        self.assertIsNone(deadline(state))
        state = observe(state, 800, 0)
        self.assertEqual(deadline(state), 1400)

    def test_brief_join_between_pings_still_counts(self):
        state = observe({}, 100, 0)
        state = observe(state, 500, 0, joined=True, left=True)
        self.assertEqual(state["ever_joined"], 1)
        self.assertEqual(deadline(state), 1100)

    def test_unready_or_stale_data_has_no_countdown(self):
        self.assertIsNone(deadline({}))
        state = observe({}, 100, 0)
        self.assertFalse(healthy(state, 221))
        self.assertIsNone(idle_view(state, 221)["deleteAt"])
        self.assertEqual(idle_view(state, 100)["remainingSeconds"], 1800)

    def test_server_log_events_ignore_player_chat(self):
        self.assertEqual(EVENT.findall('[01:00:00] [Server thread/INFO]: Player joined the game\n'), ['joined'])
        self.assertEqual(EVENT.findall('[01:00:00] [Server thread/INFO]: Player left the game\n'), ['left'])
        self.assertEqual(EVENT.findall('[01:00:00] [Server thread/INFO]: <Player> Player joined the game\n'), [])


class AutomaticCleanupTests(unittest.TestCase):
    def test_only_stopped_fresh_matching_instance_dispatches_terraform_workflow(self):
        state = {"ready_at": 100, "empty_since": 200, "ever_joined": 1, "players_online": 0, "heartbeat_at": 800, "shutdown_requested": 1}
        records = {"server": {}, "activity#i-123": state}
        server = {"InstanceId": "i-123", "State": {"Name": "running"}}
        with patch.object(app, "record", side_effect=lambda key="server": records[key]), patch.object(app, "instances", return_value=[server]), patch("app.time.time", return_value=800), patch.object(app, "dispatch", return_value={"accepted": True}) as dispatch:
            self.assertEqual(app.idle_check(), {"accepted": True})
            dispatch.assert_called_once_with('destroy', {'confirmDestroy': True}, automatic_instance_id='i-123')

    def test_deadline_alone_does_not_delete_without_graceful_stop(self):
        state = {"ready_at": 100, "empty_since": 100, "heartbeat_at": 1900, "players_online": 0}
        with patch.object(app, "record", side_effect=lambda key="server": {} if key == "server" else state), patch.object(app, "instances", return_value=[{"InstanceId": "i-123", "State": {"Name": "running"}}]), patch("app.time.time", return_value=1900), patch.object(app, "dispatch") as dispatch:
            app.idle_check()
            dispatch.assert_not_called()

    def test_stale_heartbeat_or_active_workflow_prevents_cleanup(self):
        with patch.object(app, "record", return_value={"lease_until": 2000}), patch("app.time.time", return_value=1900), patch.object(app, "dispatch") as dispatch:
            self.assertEqual(app.idle_check()['skipped'], 'operation_in_progress')
            dispatch.assert_not_called()
        state = {"ready_at": 100, "empty_since": 100, "heartbeat_at": 100, "players_online": 0, "shutdown_requested": 1}
        with patch.object(app, "record", side_effect=lambda key="server": {} if key == "server" else state), patch.object(app, "instances", return_value=[{"InstanceId": "i-new", "State": {"Name": "running"}}]), patch("app.time.time", return_value=1900), patch.object(app, "dispatch") as dispatch:
            app.idle_check()
            dispatch.assert_not_called()

    def test_wrong_schedule_cannot_bypass_cognito_authentication(self):
        with patch.dict(os.environ, {"IDLE_RULE_ARN": "expected-rule", "COGNITO_CLIENT": "client"}), patch.object(app, "idle_check") as check:
            response = app.handler({"source": "aws.events", "detail-type": "Scheduled Event", "resources": ["wrong-rule"]}, None)
            self.assertEqual(response['statusCode'], 403)
            check.assert_not_called()

    def test_destroy_workflow_refuses_stale_instance_id(self):
        script = Path(__file__).resolve().parents[2] / '.github/scripts/minecraft-control.py'
        check = runpy.run_path(str(script))['verify_auto_shutdown']
        with patch.dict(os.environ, {"INPUT_EXPECTED_INSTANCE_ID": "i-old"}), patch.dict(check.__globals__, {"outputs": lambda: {"instance_id": "i-new"}}), self.assertRaises(RuntimeError):
            check()


class ServerMonitorTests(unittest.TestCase):
    def run_tick(self, stored, ping_result):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            import json
            path.write_text(json.dumps({'instance_id': 'i-test', **stored}))
            reports = []
            with patch.object(activity_monitor, 'STATE', path), patch.object(activity_monitor, 'LOG', Path(directory) / 'missing.log'), patch.object(activity_monitor, 'instance_id', return_value='i-test'), patch.object(activity_monitor, 'ping', return_value=ping_result) as ping, patch.object(activity_monitor, 'publish', side_effect=lambda identity, state: reports.append(dict(state))), patch('activity_monitor.time.time', return_value=1900), patch('activity_monitor.time.sleep', side_effect=StopIteration), patch('activity_monitor.subprocess.run') as command:
                with self.assertRaises(StopIteration):
                    activity_monitor.main()
                result = json.loads(path.read_text())
                return result, reports, command.call_args_list, ping.call_count

    def test_due_server_stops_java_and_persists_acknowledgement(self):
        result, reports, commands, _ = self.run_tick({'ready_at': 100, 'empty_since': 100, 'players_online': 0}, {'playersOnline': 0})
        self.assertEqual(result['shutdown_requested'], 1)
        self.assertFalse(reports[0].get('shutdown_requested'))
        self.assertEqual(reports[-1]['shutdown_requested'], 1)
        self.assertEqual(commands[0].args[0], ['systemctl', 'stop', 'minecraft.service'])
        self.assertEqual(len(commands), 1)  # No EC2 termination or AWS resource deletion.

    def test_active_player_prevents_graceful_stop(self):
        result, _, commands, _ = self.run_tick({'ready_at': 100, 'empty_since': 100, 'players_online': 0}, {'playersOnline': 1})
        self.assertEqual(result['empty_since'], 0)
        self.assertEqual(commands, [])

    def test_restart_after_stop_keeps_publishing_without_reopening_game(self):
        result, reports, commands, probes = self.run_tick({'ready_at': 100, 'empty_since': 100, 'players_online': 0, 'shutdown_requested': 1}, {'playersOnline': 0})
        self.assertEqual(result['shutdown_requested'], 1)
        self.assertEqual(reports[0]['heartbeat_at'], 1900)
        self.assertEqual(commands, [])
        self.assertEqual(probes, 0)


if __name__ == '__main__':
    unittest.main()
