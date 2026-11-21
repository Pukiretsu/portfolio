"""Runs on EC2 via SSM; private S3 map transfers survive a runner disconnect."""
import importlib.util
import os
from pathlib import Path
import subprocess
import signal
import sys

world_path = Path(__file__).with_name('world.py')
if not world_path.exists():
    world_path = Path(__file__).with_name('minecraft-world-remote.py')
spec = importlib.util.spec_from_file_location('world', world_path)
world = importlib.util.module_from_spec(spec)
spec.loader.exec_module(world)


def copy(source, destination):
    subprocess.run(['aws', 's3', 'cp', source, destination, '--only-show-errors'], check=True, timeout=1800)


def interrupted(signum, frame):
    raise InterruptedError('Map transfer interrupted')


def main():
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    action, key, bucket, token = sys.argv[1:]
    local = None
    saved = False
    if action not in ('backup', 'stop'):
        raise RuntimeError('Worlds can only be restored from S3 during startup')
    try:
        world.pause(token, allow_shutdown=action == 'stop')
        local = world.backup(token)
        if local.stat().st_size > 1024 ** 3:
            raise RuntimeError('Backup exceeds the dashboard limit of 1 GiB')
        copy(str(local), 's3://' + bucket + '/' + key)
        saved = True
        print('World safely stored in private S3.', flush=True)
    finally:
        try:
            # Stop snapshots remain quiescent until Terraform destroys the disk.
            if action != 'stop' or not saved:
                world.resume(token)
        finally:
            if local:
                local.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
