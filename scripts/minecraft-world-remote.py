"""Root helper invoked over SSH; archives only the configured world directory."""
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path('/srv/minecraft')
TRANSFER = Path('/home/ec2-user/minecraft-transfers')
HOLD = Path('/run/minecraft-world-transfer.json')


def service(action, name):
    return subprocess.run(['systemctl', action, name], check=True)


def active(name):
    return subprocess.run(['systemctl', 'is-active', '--quiet', name]).returncode == 0


def world():
    name = 'world'
    for line in (ROOT / 'server.properties').read_text().splitlines():
        if line.startswith('level-name='):
            name = line.split('=', 1)[1].strip()
    # Map paths may never escape the server directory or select the server root.
    path = ROOT / name
    if path.is_symlink() or path.resolve().parent != ROOT.resolve():
        raise RuntimeError('Expected a single world directory under /srv/minecraft')
    return path


def pause(token):
    if HOLD.exists():
        raise RuntimeError('Another map transfer is active; resume it first')
    monitor_state = Path('/var/lib/minecraft-monitor/state.json')
    if monitor_state.exists() and json.loads(monitor_state.read_text()).get('shutdown_requested'):
        raise RuntimeError('Idle destruction is already requested; cannot safely begin a transfer')
    state = {'game': active('minecraft.service'), 'monitor': active('minecraft-activity.service'), 'token': token}
    HOLD.write_text(json.dumps(state))
    HOLD.chmod(0o600)
    # A stopped monitor stops fresh acknowledgements; resource deletion stays in Terraform.
    service('stop', 'minecraft-activity.service')
    if monitor_state.exists() and json.loads(monitor_state.read_text()).get('shutdown_requested'):
        raise RuntimeError('Idle shutdown was requested before maintenance acquired the monitor')
    service('stop', 'minecraft.service')
    if active('minecraft.service'):
        raise RuntimeError('Minecraft did not stop')


def resume(token=None):
    if not HOLD.exists():
        return
    state = json.loads(HOLD.read_text())
    if token is not None and state.get('token') != token:
        raise RuntimeError('Another map transfer owns the maintenance hold')
    # Resume idle countdown from now, so a long transfer does not cause immediate deletion.
    monitor_state = Path('/var/lib/minecraft-monitor/state.json')
    if monitor_state.exists():
        activity = json.loads(monitor_state.read_text())
        if activity.get('shutdown_requested'):
            raise RuntimeError('Shutdown acknowledged; refusing to reopen the server')
        activity['empty_since'] = int(time.time())
        temporary = monitor_state.with_suffix('.tmp')
        temporary.write_text(json.dumps(activity))
        temporary.replace(monitor_state)
    if state['game']:
        service('start', 'minecraft.service')
    if state['monitor']:
        service('start', 'minecraft-activity.service')
    HOLD.unlink()


def require_paused(token):
    if not HOLD.exists() or active('minecraft.service') or active('minecraft-activity.service'):
        raise RuntimeError('Pause the game and idle monitor before transferring maps')
    if json.loads(HOLD.read_text()).get('token') != token:
        raise RuntimeError('Another map transfer owns the maintenance hold')


def backup(token):
    require_paused(token)
    directory = world()
    if not (directory / 'level.dat').is_file():
        raise RuntimeError('World has no level.dat')
    TRANSFER.mkdir(mode=0o700, exist_ok=True)
    account = pwd.getpwnam('ec2-user')
    os.chown(TRANSFER, account.pw_uid, account.pw_gid)
    destination = TRANSFER / ('world-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex[:8] + '.zip')
    try:
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for path in directory.rglob('*'):
                if path.is_symlink():
                    raise RuntimeError('Refusing to follow symlinks in world data')
                if path.is_file():
                    archive.write(path, Path('world') / path.relative_to(directory))
        destination.chmod(0o600)
        os.chown(destination, account.pw_uid, account.pw_gid)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    print(destination, flush=True)
    return destination


def restore(filename, token):
    require_paused(token)
    source = Path(filename)
    if source.is_symlink() or source.parent != TRANSFER or not source.is_file():
        raise RuntimeError('Upload the ZIP into minecraft-transfers first')
    # An upload contains only world/..., never server binaries, properties or mods.
    target = world()
    staging = ROOT / ('.world-import-' + uuid.uuid4().hex)
    staging.mkdir(mode=0o700)
    old = ROOT / ('.world-before-import-' + uuid.uuid4().hex)
    try:
        with zipfile.ZipFile(source) as archive:
            names = set()
            for item in archive.infolist():
                path = Path(item.filename)
                mode = item.external_attr >> 16
                if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                        or not path.parts or path.parts[0] != 'world'
                        or stat.S_ISLNK(mode) or item.filename in names):
                    raise RuntimeError('Unsafe or duplicate ZIP entry: ' + item.filename)
                names.add(item.filename)
            if 'world/level.dat' not in names:
                raise RuntimeError('ZIP must contain world/level.dat; use a downloaded map backup')
            required = sum(item.file_size for item in archive.infolist())
            if required + 512 * 1024 * 1024 > shutil.disk_usage(ROOT).free:
                raise RuntimeError('Insufficient free disk space for safe restore')
            archive.extractall(staging)
        incoming = staging / 'world'
        account = pwd.getpwnam('minecraft')
        for path in [incoming, *incoming.rglob('*')]:
            os.chown(path, account.pw_uid, account.pw_gid)
            path.chmod(0o750 if path.is_dir() else 0o640)
        had_world = target.exists()
        if had_world:
            target.rename(old)
        try:
            incoming.rename(target)
        except BaseException:
            if had_world:
                old.rename(target)
            raise
        print('Map restored. Previous world retained at ' + str(old) if had_world else 'Map restored.', flush=True)
    finally:
        shutil.rmtree(staging)


if __name__ == '__main__':
    operation = sys.argv[1]
    token = sys.argv[2] if len(sys.argv) > 2 else None
    if operation == 'restore':
        restore(sys.argv[3], token)
    else:
        {'pause': pause, 'resume': resume, 'backup': backup}[operation](token)
