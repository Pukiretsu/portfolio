import datetime
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'minecraft_proxy'))
import app
import backups
from test_minecraft import ENV, event

KEY = 'backups/550e8400-e29b-41d4-a716-446655440000.zip'
UPLOAD = KEY.replace('backups/', 'uploads/')
INSTANCE = {'InstanceId': 'i-1234567890abcdef0', 'State': {'Name': 'running'}}


class BackupApiTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {**ENV, 'BACKUP_BUCKET': 'private-maps'})
        environment.start()
        self.addCleanup(environment.stop)

    def test_all_backup_routes_require_cognito(self):
        for route in ('GET /minecraft/backups', 'POST /minecraft/backups/upload', 'POST /minecraft/backups/download', 'POST /minecraft/backup', 'POST /minecraft/restore'):
            with patch.object(app, 'client') as client:
                self.assertEqual(app.handler({'routeKey': route}, None)['statusCode'], 403)
                client.assert_not_called()

    def test_legacy_presigned_post_upload_is_not_exposed(self):
        self.assertFalse(hasattr(backups, 'upload'))

    def test_download_rejects_arbitrary_keys_and_temporary_uploads(self):
        s3 = MagicMock()
        for value in ('../../secret', 'server.jar', 'backups/nope.zip', UPLOAD, None):
            with self.assertRaises(ValueError): backups.download(s3, {'key': value})
        s3.head_object.assert_not_called()
        s3.head_object.return_value = {'ContentLength': 1024}
        s3.generate_presigned_url.return_value = 'https://private-signed-link'
        self.assertEqual(backups.download(s3, {'key': KEY})['expiresIn'], 300)
        self.assertEqual(s3.generate_presigned_url.call_args.kwargs['Params']['Key'], KEY)

    def test_catalog_is_scoped_and_paginates_without_public_urls(self):
        s3 = MagicMock()
        s3.list_objects_v2.return_value = {'Contents': [{'Key': KEY, 'Size': 100, 'LastModified': datetime.datetime.now(datetime.timezone.utc)}], 'NextContinuationToken': 'next'}
        result = backups.catalog(s3, 'cursor')
        self.assertEqual(result['nextCursor'], 'next')
        self.assertNotIn('url', result['items'][0])
        self.assertEqual(s3.list_objects_v2.call_args.kwargs['Prefix'], 'backups/')
        self.assertEqual(s3.list_objects_v2.call_args.kwargs['ContinuationToken'], 'cursor')

    def test_world_selection_and_upload_require_no_server_resources(self):
        for route in ('POST /minecraft/restore', 'POST /minecraft/backups/upload', 'POST /minecraft/config'):
            with patch.object(app, 'instances', return_value=[INSTANCE]), patch.object(app, 'client', return_value=MagicMock()):
                self.assertEqual(app.handler(event(route, {'key': KEY}), None)['statusCode'], 409)
        with patch.object(app, 'instances', return_value=[]):
            self.assertEqual(app.handler(event('POST /minecraft/backup'), None)['statusCode'], 409)

    def test_idle_shutdown_blocks_map_operations(self):
        with patch.object(app, 'instances', return_value=[INSTANCE]), patch.object(app, 'record', return_value={'shutdown_requested': 1}):
            self.assertEqual(app.handler(event('POST /minecraft/backup'), None)['statusCode'], 409)

    def test_map_dispatch_is_allowlisted_and_pins_current_instance(self):
        clients = {name: MagicMock() for name in ('dynamodb', 'secretsmanager', 's3')}
        clients['secretsmanager'].get_secret_value.return_value = {'SecretString': 'secret-token'}
        clients['s3'].head_object.return_value = {'ContentLength': 123}
        response = MagicMock()
        response.__enter__.return_value.status = 204
        with patch.object(app, 'instances', return_value=[INSTANCE]), patch.object(app, 'record', return_value={}), patch.object(app, 'client', side_effect=clients.__getitem__), patch('urllib.request.urlopen', return_value=response) as send:
            result = app.handler(event('POST /minecraft/backup', {'workflow': 'evil.yml', 'expected_instance_id': 'evil'}), None)
        self.assertEqual(result['statusCode'], 202)
        self.assertEqual(json.loads(result['body'])['phase'], 'backing_up')
        request = send.call_args.args[0]
        self.assertTrue(request.full_url.endswith('/minecraft-backup.yml/dispatches'))
        inputs = json.loads(request.data)['inputs']
        self.assertEqual(inputs['expected_instance_id'], INSTANCE['InstanceId'])
        self.assertTrue(inputs['object_key'].startswith('backups/'))
        self.assertEqual(inputs['action'], 'backup')
        self.assertNotIn('secret-token', result['body'])

    def test_busy_backup_status_does_not_revert_to_provisioning(self):
        server = {**INSTANCE, 'PublicIpAddress': '8.8.8.8'}
        control = {'lease_until': 9999999999, 'phase': 'backing_up'}
        with patch.object(app, 'record', side_effect=[control, {}]), patch.object(app, 'instances', return_value=[server]), patch.object(app, 'ping', return_value={'playersOnline': 0}):
            self.assertEqual(app.status()['phase'], 'backing_up')


worker_path = Path(__file__).resolve().parents[2] / 'scripts/minecraft-map-worker.py'
spec = importlib.util.spec_from_file_location('map_worker', worker_path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class MapWorkerTests(unittest.TestCase):
    def test_failed_s3_backup_always_resumes_without_deleting_world(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'map.zip'
            archive.write_bytes(b'map')
            fake = MagicMock()
            fake.backup.return_value = archive
            with patch.object(worker, 'world', fake), patch.object(worker, 'copy', side_effect=RuntimeError('S3 unavailable')), patch.object(sys, 'argv', ['worker', 'backup', KEY, 'private-maps', 'token']):
                with self.assertRaises(RuntimeError): worker.main()
            fake.pause.assert_called_once_with('token', allow_shutdown=False)
            fake.resume.assert_called_once_with('token')
            fake.restore.assert_not_called()

    def test_live_restores_are_rejected_before_touching_world(self):
        fake = MagicMock()
        with patch.object(worker, 'world', fake), patch.object(sys, 'argv', ['worker', 'restore', KEY, 'private-maps', 'token']):
            with self.assertRaises(RuntimeError): worker.main()
        fake.pause.assert_not_called()
        fake.restore.assert_not_called()

    def test_successful_stop_snapshot_leaves_java_and_monitor_down(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'map.zip'
            archive.write_bytes(b'map')
            fake = MagicMock(); fake.backup.return_value = archive
            with patch.object(worker, 'world', fake), patch.object(worker, 'copy'), patch.object(sys, 'argv', ['worker', 'stop', KEY, 'private-maps', 'token']):
                worker.main()
            fake.pause.assert_called_once_with('token', allow_shutdown=True)
            fake.resume.assert_not_called()

    def test_successful_backup_uploads_only_selected_key_and_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'map.zip'
            archive.write_bytes(b'map')
            fake = MagicMock()
            fake.backup.return_value = archive
            with patch.object(worker, 'world', fake), patch.object(worker, 'copy') as copy, patch.object(sys, 'argv', ['worker', 'backup', KEY, 'private-maps', 'token']):
                worker.main()
            copy.assert_called_once_with(str(archive), 's3://private-maps/' + KEY)
            fake.resume.assert_called_once_with('token')


control_path = Path(__file__).resolve().parents[2] / '.github/scripts/minecraft-control.py'
control_spec = importlib.util.spec_from_file_location('map_control', control_path)
control = importlib.util.module_from_spec(control_spec)
control_spec.loader.exec_module(control)


class MapCancellationTests(unittest.TestCase):
    def test_runner_cancellation_cannot_release_active_ssm_lease(self):
        with patch.dict(os.environ, {'MINECRAFT_OPERATION_ID': 'operation', 'MINECRAFT_MAP_COMMAND_SENT': 'true', 'MINECRAFT_MAP_COMMAND_ID': 'command', 'MAP_INSTANCE_ID': 'i-current', 'JOB_STATUS': 'cancelled'}), patch.object(control, 'aws', return_value={'Status': 'InProgress'}) as aws:
            control.finish('backup')
            self.assertEqual(aws.call_count, 1)
            self.assertEqual(aws.call_args.args[:2], ('ssm', 'get-command-invocation'))

    def test_uncertain_command_dispatch_keeps_the_lock(self):
        with patch.dict(os.environ, {'MINECRAFT_OPERATION_ID': 'operation', 'MINECRAFT_MAP_COMMAND_SENT': 'true', 'MINECRAFT_MAP_COMMAND_ID': ''}), patch.object(control, 'aws') as aws:
            control.finish('restore')
            aws.assert_not_called()
