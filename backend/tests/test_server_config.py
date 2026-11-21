import copy
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'minecraft_proxy'))
import app
import uploads
import settings
from server_config import DEFAULT, validate
from test_minecraft import ENV, event

KEY = 'backups/550e8400-e29b-41d4-a716-446655440000.zip'
OP = '550e8400-e29b-41d4-a716-446655440001'

class ConfigurationTests(unittest.TestCase):
    def test_missing_settings_returns_an_independent_default(self):
        s3 = MagicMock(); error = RuntimeError('missing')
        error.response = {'Error': {'Code': 'NoSuchKey'}}
        s3.get_object.side_effect = error
        value = settings.read(s3, 'private')
        self.assertEqual(value, DEFAULT)
        value['mods']['lithium'] = False
        self.assertTrue(DEFAULT['mods']['lithium'])

    def test_defaults_and_mod_files_validate(self):
        self.assertEqual(validate(DEFAULT), DEFAULT)
        value = copy.deepcopy(DEFAULT); value['modFiles'] = {'lithium.properties': 'mixin.ai=true\n', 'example.json': '{}'}
        validate(value)

    def test_rejects_unsafe_paths_worker_counts_and_heap_overrides(self):
        for values in ({'c2meWorkers': 8}, {'minecraftVersion': '26.3; whoami'}, {'modFiles': {'../../server.properties': 'bad'}}, {'modFiles': {'c2me.toml': 'bad'}}, {'worldKey': '../../secret'}):
            with self.assertRaises(ValueError): validate({**copy.deepcopy(DEFAULT), **values})
        value = copy.deepcopy(DEFAULT); value['properties']['server-port'] = 22
        with self.assertRaises(ValueError): validate(value)

    def test_save_configuration_and_select_s3_world_only_offline(self):
        clients = {name: MagicMock() for name in ('s3', 'dynamodb')}
        clients['s3'].get_object.return_value = {'Body': io.BytesIO(json.dumps(DEFAULT).encode())}
        clients['s3'].head_object.return_value = {'ContentLength': 100}
        with patch.dict(os.environ, {**ENV, 'BACKUP_BUCKET': 'private'}), patch.object(app, 'instances', return_value=[]), patch.object(app, 'client', side_effect=clients.__getitem__):
            result = app.handler(event('POST /minecraft/restore', {'key': KEY}), None)
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(json.loads(result['body'])['desired']['worldKey'], KEY)
        self.assertEqual(clients['s3'].put_object.call_args.kwargs['Key'], 'settings/server.json')
        self.assertEqual(clients['dynamodb'].update_item.call_count, 2)

    def test_launch_snapshots_selected_settings_to_s3(self):
        clients = {name: MagicMock() for name in ('s3', 'dynamodb', 'secretsmanager')}
        clients['secretsmanager'].get_secret_value.return_value = {'SecretString': 'secret'}
        clients['s3'].get_object.return_value = {'Body': io.BytesIO(json.dumps(DEFAULT).encode())}
        response = MagicMock(); response.__enter__.return_value.status = 204
        with patch.dict(os.environ, {**ENV, 'BACKUP_BUCKET': 'private'}), patch.object(app, 'instances', return_value=[]), patch.object(app, 'client', side_effect=clients.__getitem__), patch('urllib.request.urlopen', return_value=response) as send:
            result = app.dispatch('deploy', {})
        self.assertEqual(result['phase'], 'provisioning')
        inputs = json.loads(send.call_args.args[0].data)['inputs']
        self.assertTrue(inputs['launch_config_key'].startswith('launches/'))
        self.assertEqual(clients['s3'].put_object.call_args.kwargs['Key'], inputs['launch_config_key'])

class MultipartTests(unittest.TestCase):
    def test_upload_uses_bounded_parts_not_a_reusable_public_form(self):
        s3, db = MagicMock(), MagicMock()
        s3.create_multipart_upload.return_value = {'UploadId': 'multipart'}
        result = uploads.begin(s3, db, 'table', 'private', {'filename': 'map.zip', 'size': uploads.PART + 10}, 'owner', OP)
        self.assertEqual(len(result['parts']), 2)
        self.assertTrue(result['key'].startswith('backups/'))
        self.assertEqual(s3.generate_presigned_url.call_args.kwargs['Params']['ContentLength'], 10)
        self.assertNotIn('upload', result)

    def test_upload_receipts_are_verified(self):
        s3 = MagicMock(); session = {'size': 10, 'key': KEY, 'uploadId': 'upload'}
        for parts in ([], [{'PartNumber': 2, 'ETag': 'a' * 32}], [{'PartNumber': 1, 'ETag': 'injected'}]):
            with self.assertRaises(ValueError): uploads.complete(s3, 'private', session, parts)
        s3.complete_multipart_upload.assert_not_called()
        s3.head_object.return_value = {'ContentLength': 10}
        self.assertEqual(uploads.complete(s3, 'private', session, [{'PartNumber': 1, 'ETag': 'a' * 32}])['key'], KEY)

    def test_completion_is_rejected_if_server_exists_or_lock_expired(self):
        session = {'owner': 'owner', 'operationId': OP, 'size': 10, 'key': KEY, 'uploadId': 'upload'}
        for servers, state in (([{'InstanceId': 'i-server'}], {'operation_id': OP, 'lease_until': 9999999999}), ([], {'operation_id': OP, 'lease_until': 1})):
            with patch.dict(os.environ, {**ENV, 'BACKUP_BUCKET': 'private'}), patch.object(app, 'client', return_value=MagicMock()), patch.object(uploads, 'load', return_value=session), patch.object(app, 'instances', return_value=servers), patch.object(app, 'record', return_value=state):
                with self.assertRaises(app.ApiError): app.upload_operation('/complete', {'operationId': OP, 'parts': []}, 'owner')

    def test_upload_owner_cannot_be_forged(self):
        db = MagicMock(); db.get_item.return_value = {'Item': {'payload': {'S': json.dumps({'owner': 'actual'})}}}
        with self.assertRaises(ValueError): uploads.load(db, 'table', OP, 'other')


class BootstrapTests(unittest.TestCase):
    def test_s3_map_and_settings_are_applied_before_java_start(self):
        import importlib.util
        import tempfile
        path = Path(__file__).resolve().parents[2] / 'scripts/minecraft-bootstrap.py'
        spec = importlib.util.spec_from_file_location('bootstrap', path)
        bootstrap = importlib.util.module_from_spec(spec); spec.loader.exec_module(bootstrap)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'server'; root.mkdir(); (root / 'config').mkdir()
            (root / 'server.properties').write_text('server-port=25565\nmotd=old\n')
            world = MagicMock(); world.TRANSFER = Path(directory) / 'transfers'
            value = copy.deepcopy(DEFAULT); value['worldKey'] = KEY; value['properties']['motd'] = 'S3 snapshot'; value['c2meWorkers'] = 2
            def transfer(arguments, **kwargs):
                self.assertEqual(arguments[:3], ['aws', 's3', 'cp'])
                self.assertEqual(arguments[3], 's3://private/' + KEY)
                Path(arguments[4]).write_bytes(b'zip')
            def restore(*args, **kwargs):
                self.assertTrue(kwargs['bootstrap'])
                self.assertIn('motd=S3 snapshot', (root / 'server.properties').read_text())
            world.restore.side_effect = restore
            with patch.object(bootstrap.subprocess, 'run', side_effect=transfer): bootstrap.apply(root, value, 'private', world)
            world.restore.assert_called_once()
            self.assertIn('server-port=25565', (root / 'server.properties').read_text())
            self.assertEqual((root / 'config/c2me.toml').read_text(), 'globalExecutorParallelism = 2\n')
            self.assertFalse((world.TRANSFER / 'initial-world.zip').exists())
