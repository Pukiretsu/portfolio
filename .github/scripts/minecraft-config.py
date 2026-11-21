"""Resolve immutable launch settings, or select the just-saved stop backup."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend/minecraft_proxy'))
from server_config import DEFAULT, validate


def aws(*args):
    return subprocess.run(['aws', *args], check=True, capture_output=True, text=True).stdout


def main():
    account = json.loads(aws('sts', 'get-caller-identity'))['Account']
    bucket = account + '-portfolio-minecraft-backups'
    key = os.environ.get('INPUT_LAUNCH_CONFIG_KEY') or os.environ.get('TF_VAR_launch_config_key') or 'settings/server.json'
    if key != 'settings/server.json' and not re.fullmatch(r'launches/[0-9a-f-]{36}\.json', key):
        raise RuntimeError('Invalid launch configuration key')
    try:
        value = json.loads(aws('s3', 'cp', 's3://' + bucket + '/' + key, '-'))
    except subprocess.CalledProcessError as error:
        if key != 'settings/server.json' or 'NoSuchKey' not in error.stderr:
            raise
        value = copy.deepcopy(DEFAULT)
    value = validate(value)
    if len(sys.argv) > 1 and sys.argv[1] == 'select-saved-world':
        value['worldKey'] = os.environ['MAP_OBJECT_KEY']
        path = Path(os.environ['RUNNER_TEMP']) / 'server-config.json'
        path.write_text(json.dumps(validate(value)))
        aws('s3', 'cp', str(path), 's3://' + bucket + '/settings/server.json', '--content-type', 'application/json')
        return
    if len(sys.argv) > 1 and sys.argv[1] == 'check-world':
        if value['worldKey']:
            import importlib.util
            import zipfile
            world_path = Path(__file__).resolve().parents[2] / 'scripts/minecraft-world-remote.py'
            spec = importlib.util.spec_from_file_location('world', world_path)
            world = importlib.util.module_from_spec(spec); spec.loader.exec_module(world)
            archive_path = Path(os.environ['RUNNER_TEMP']) / 'preflight-world.zip'
            try:
                aws('s3', 'cp', 's3://' + bucket + '/' + value['worldKey'], str(archive_path), '--only-show-errors')
                with zipfile.ZipFile(archive_path) as archive:
                    if world.validate_archive(archive) > 20 * 1024 ** 3 or archive.testzip() is not None:
                        raise RuntimeError('World ZIP is corrupt or exceeds the 20 GiB expanded limit')
            finally:
                archive_path.unlink(missing_ok=True)
        print('S3 world archive preflight passed.')
        return
    path = Path(os.environ['RUNNER_TEMP']) / 'launch-config.json'
    path.write_text(json.dumps(value))
    # Manual launches also receive a persisted snapshot; no local-world upload path.
    if key == 'settings/server.json':
        import uuid
        key = 'launches/' + str(uuid.uuid4()) + '.json'
        aws('s3', 'cp', str(path), 's3://' + bucket + '/' + key, '--content-type', 'application/json')
    with open(os.environ['GITHUB_ENV'], 'a') as env:
        for variable, name in [('minecraft_version', 'minecraftVersion'), ('fabric_loader_version', 'fabricLoaderVersion'), ('fabric_installer_version', 'fabricInstallerVersion'), ('fabric_api_version', 'fabricApiVersion')]:
            env.write('TF_VAR_' + variable + '=' + value[name] + '\n')
        env.write('TF_VAR_launch_config_key=' + key + '\n')
        env.write('MINECRAFT_CONFIG_FILE=' + str(path) + '\n')


if __name__ == '__main__':
    main()
