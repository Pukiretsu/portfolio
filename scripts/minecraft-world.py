#!/usr/bin/env python3
"""SSH/SCP access and world-only ZIP transfer through AWS Session Manager."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
import uuid
import zipfile

REPO = Path(__file__).resolve().parents[1]
LOCAL = REPO / '.local/minecraft'


def aws(region, *arguments):
    result = subprocess.run(['aws', '--region', region, '--output', 'json', *arguments], check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def remote(options, command):
    script = (REPO / 'scripts/minecraft-world-remote.py').read_text()
    result = subprocess.run([*options, 'sudo python3 - ' + command], input=script, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'Remote map operation failed')
    return result.stdout.strip()


def check_operation(region):
    control = aws(region, 'dynamodb', 'get-item', '--table-name', 'portfolio-minecraft-control', '--key', '{"pk":{"S":"server"}}', '--consistent-read').get('Item', {})
    if int(control.get('lease_until', {}).get('N', '0')) > time.time():
        raise RuntimeError('Wait until the running deployment/destroy operation finishes')


def authorize(region, identity, key):
    public = Path(str(key) + '.pub').read_text().strip()
    if '\n' in public or not public.startswith(('ssh-ed25519 ', 'ssh-rsa ', 'ecdsa-sha2-')):
        raise RuntimeError('Expected a single SSH public key')
    quoted = shlex.quote(public)
    command = ('set -eu; install -d -m 700 -o ec2-user -g ec2-user /home/ec2-user/.ssh; '
               'touch /home/ec2-user/.ssh/authorized_keys; '
               f'grep -qxF -- {quoted} /home/ec2-user/.ssh/authorized_keys || '
               f'printf "%s\\n" {quoted} >> /home/ec2-user/.ssh/authorized_keys; '
               'chown ec2-user:ec2-user /home/ec2-user/.ssh/authorized_keys; '
               'chmod 600 /home/ec2-user/.ssh/authorized_keys; systemctl start sshd')
    result = aws(region, 'ssm', 'send-command', '--instance-ids', identity, '--document-name', 'AWS-RunShellScript', '--parameters', json.dumps({'commands': [command]}), '--timeout-seconds', '60')
    command_id = result['Command']['CommandId']
    for _ in range(60):
        time.sleep(2)
        try:
            invocation = aws(region, 'ssm', 'get-command-invocation', '--command-id', command_id, '--instance-id', identity)
        except subprocess.CalledProcessError as error:
            if 'InvocationDoesNotExist' in error.stderr:
                continue
            raise
        status = invocation['Status']
        if status == 'Success':
            return
        if status not in ('Pending', 'InProgress', 'Delayed'):
            raise RuntimeError(invocation.get('StandardErrorContent') or 'SSH key registration failed: ' + status)
    raise RuntimeError('Timed out registering SSH key')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['ssh', 'download', 'resume'])
    parser.add_argument('archive', nargs='?', help='Local ZIP path for upload or destination for download')
    parser.add_argument('--region', default=os.environ.get('AWS_REGION', 'us-east-1'))
    parser.add_argument('--instance', help='Optional current Minecraft instance ID')
    parser.add_argument('--identity', type=Path, help='Existing private key with a matching .pub file')
    parser.add_argument('--confirm-restore', action='store_true', help='Replace the running instance map with the uploaded map')
    args = parser.parse_args()
    if args.action == 'upload' and (not args.archive or not args.confirm_restore):
        parser.error('upload requires a ZIP path and --confirm-restore')
    plugin = REPO / '.local/session-manager-plugin/bin'
    os.environ['PATH'] = str(plugin) + os.pathsep + os.environ.get('PATH', '')
    os.environ['AWS_PAGER'] = ''
    for tool in ('aws', 'ssh', 'scp', 'ssh-keygen', 'session-manager-plugin'):
        if not shutil.which(tool):
            raise RuntimeError('Install required tool: ' + tool + ' (see docs/minecraft-world.md)')
    if args.action != 'resume':
        check_operation(args.region)
    instances = aws(args.region, 'ec2', 'describe-instances', '--filters', 'Name=tag:Project,Values=portfolio-minecraft', 'Name=instance-state-name,Values=running')
    ids = [i['InstanceId'] for r in instances['Reservations'] for i in r['Instances']]
    if args.instance:
        if args.instance not in ids:
            raise RuntimeError('Instance is not a running portfolio Minecraft server')
        identity = args.instance
    elif len(ids) == 1:
        identity = ids[0]
    else:
        raise RuntimeError('Expected exactly one running Minecraft instance')
    LOCAL.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = args.identity.expanduser().resolve() if args.identity else LOCAL / 'id_ed25519'
    if not key.exists() and not args.identity:
        subprocess.run(['ssh-keygen', '-t', 'ed25519', '-N', '', '-C', 'minecraft-world-transfer', '-f', str(key)], check=True, stdout=subprocess.DEVNULL)
    if not key.exists():
        raise RuntimeError('Private key not found')
    authorize(args.region, identity, key)
    proxy = 'aws ssm start-session --region ' + shlex.quote(args.region) + ' --target %h --document-name AWS-StartSSHSession --parameters portNumber=%p'
    common = ['-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', '-i', str(key), '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' + str(LOCAL / 'known_hosts'), '-o', 'ProxyCommand=' + proxy]
    host = 'ec2-user@' + identity
    ssh = ['ssh', *common, host]
    if args.action == 'ssh':
        subprocess.run(ssh, check=True)
        return
    if args.action == 'resume':
        print(remote(ssh, 'resume'))
        return
    # Fail closed if a Terraform operation has started while preparing the tunnel.
    check_operation(args.region)
    paused = False
    token = uuid.uuid4().hex
    try:
        # Always try resume if pause partially fails after recording the original state.
        paused = True
        remote(ssh, 'pause ' + token)
        if args.action == 'download':
            filename = remote(ssh, 'backup ' + token).splitlines()[-1]
            destination = Path(args.archive).expanduser().resolve() if args.archive else REPO / 'minecraft-backups' / Path(filename).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise RuntimeError('Refusing to overwrite local file: ' + str(destination))
            partial = destination.with_name(destination.name + '.part-' + token)
            try:
                subprocess.run(['scp', *common, host + ':' + filename, str(partial)], check=True)
                with zipfile.ZipFile(partial) as archive:
                    if archive.testzip() is not None:
                        raise RuntimeError('Downloaded world ZIP failed integrity verification')
                partial.replace(destination)
            finally:
                partial.unlink(missing_ok=True)
            print('Map downloaded: ' + str(destination), flush=True)
        else:
            source = Path(args.archive).expanduser().resolve()
            if not source.is_file():
                raise RuntimeError('Local archive does not exist')
            # No shell metacharacters from local filenames reach the remote shell.
            filename = '/home/ec2-user/minecraft-transfers/upload-' + uuid.uuid4().hex + '.zip'
            subprocess.run([*ssh, 'install -d -m 700 /home/ec2-user/minecraft-transfers'], check=True)
            subprocess.run(['scp', *common, str(source), host + ':' + filename], check=True)
            print(remote(ssh, 'restore ' + token + ' ' + shlex.quote(filename)), flush=True)
    finally:
        if paused:
            try:
                remote(ssh, 'resume ' + token)
            except Exception:
                print('Resume failed. Run: python3 scripts/minecraft-world.py resume', flush=True)
                raise


if __name__ == '__main__':
    main()
