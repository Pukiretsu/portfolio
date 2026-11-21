"""Runner orchestration; no SSH secrets or long file transfers through Lambda."""
import base64
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'backend/minecraft_proxy'))
from backups import key


def aws(*arguments):
    result = subprocess.run(['aws', *arguments, '--output', 'json'], check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def command_script(action, object_key, bucket, token):
    remote = base64.b64encode((REPO / 'scripts/minecraft-world-remote.py').read_bytes()).decode()
    worker = base64.b64encode((REPO / 'scripts/minecraft-map-worker.py').read_bytes()).decode()
    return '\n'.join([
        'set -eu', 'install -d -m 700 /opt/minecraft-map',
        'printf %s ' + shlex.quote(remote) + ' | base64 -d > /opt/minecraft-map/world.py',
        'printf %s ' + shlex.quote(worker) + ' | base64 -d > /opt/minecraft-map/worker.py',
        'python3 /opt/minecraft-map/worker.py ' + ' '.join(map(shlex.quote, [action, object_key, bucket, token])),
    ])


def main():
    action = os.environ['MAP_ACTION']
    if action not in ('backup', 'stop'):
        raise RuntimeError('Unsupported map operation')
    object_key = key(os.environ['MAP_OBJECT_KEY'], backups_only=True)
    identity = os.environ['MAP_INSTANCE_ID']
    if not re.fullmatch(r'i-[0-9a-f]+', identity):
        raise RuntimeError('Invalid instance ID')
    response = aws('ec2', 'describe-instances', '--instance-ids', identity)
    instance = response['Reservations'][0]['Instances'][0]
    if instance['State']['Name'] != 'running' or not any(t['Key'] == 'Project' and t['Value'] == 'portfolio-minecraft' for t in instance.get('Tags', [])):
        raise RuntimeError('Requested instance is not the current running Minecraft server')
    account = aws('sts', 'get-caller-identity')['Account']
    bucket = account + '-portfolio-minecraft-backups'
    online = aws('ssm', 'describe-instance-information', '--filters', json.dumps([{'Key': 'InstanceIds', 'Values': [identity]}]))
    if not any(i['PingStatus'] == 'Online' for i in online['InstanceInformationList']):
        raise RuntimeError('SSM Agent is not online; wait for registration before retrying')
    script = command_script(action, object_key, bucket, os.environ['MINECRAFT_OPERATION_ID'])
    with open(os.environ['GITHUB_ENV'], 'a') as environment:
        environment.write('MINECRAFT_MAP_COMMAND_SENT=true\n')
    result = aws('ssm', 'send-command', '--instance-ids', identity, '--document-name', 'AWS-RunShellScript',
                 '--parameters', json.dumps({'commands': [script], 'executionTimeout': ['2400']}), '--timeout-seconds', '60',
                 '--comment', 'Minecraft map ' + action)
    command_id = result['Command']['CommandId']
    with open(os.environ['GITHUB_ENV'], 'a') as environment:
        environment.write('MINECRAFT_MAP_COMMAND_ID=' + command_id + '\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write(f'Map {action} on `{identity}` via SSM command `{command_id}`.\n')
    # The command continues and resumes services if the runner is cancelled/disconnected.
    for _ in range(510):
        time.sleep(5)
        try:
            invocation = aws('ssm', 'get-command-invocation', '--command-id', command_id, '--instance-id', identity)
        except subprocess.CalledProcessError as error:
            if 'InvocationDoesNotExist' in error.stderr:
                continue
            raise
        if invocation['Status'] == 'Success':
            print(invocation.get('StandardOutputContent', ''))
            return
        if invocation['Status'] not in ('Pending', 'InProgress', 'Delayed'):
            print(invocation.get('StandardErrorContent', ''), file=sys.stderr)
            raise RuntimeError('Map operation failed: ' + invocation['Status'])
    raise RuntimeError('SSM command status timed out; inspect the command before retrying')


if __name__ == '__main__':
    main()
