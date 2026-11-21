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
    try:
        world.pause(token)
        if action == 'backup':
            # world.backup prints the path; it also returns it for non-SSH callers.
            local = world.backup(token)
            if local.stat().st_size > 1024 ** 3:
                raise RuntimeError('Backup exceeds the dashboard limit of 1 GiB')
            copy(str(local), 's3://' + bucket + '/' + key)
            print('World safely stored in private S3.', flush=True)
        elif action == 'restore':
            world.TRANSFER.mkdir(mode=0o700, exist_ok=True)
            local = world.TRANSFER / ('s3-import-' + token + '.zip')
            copy('s3://' + bucket + '/' + key, str(local))
            if local.stat().st_size > 1024 ** 3:
                raise RuntimeError('Upload exceeds 1 GiB')
            # Preserve the current map in S3 before replacing it, even for bad ZIPs.
            previous = world.backup(token)
            try:
                import uuid
                copy(str(previous), 's3://' + bucket + '/backups/' + str(uuid.uuid4()) + '.zip')
            finally:
                previous.unlink(missing_ok=True)
            world.restore(str(local), token)
            print('World restored. The previous map is also saved in S3.', flush=True)
        else:
            raise RuntimeError('Unsupported operation')
    finally:
        try:
            world.resume(token)
        finally:
            if local:
                local.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
