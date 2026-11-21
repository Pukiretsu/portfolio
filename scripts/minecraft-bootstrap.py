"""Apply a validated S3 launch snapshot and restore S3 world before Java starts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from server_config import validate


def apply(root, config, bucket, world_module=None):
    config = validate(config)
    props = root / 'server.properties'
    lines = props.read_text().splitlines()
    values = dict(config['properties'])
    values['enforce-whitelist'] = values['white-list']
    values['enforce-secure-profile'] = values['online-mode']
    lines = [line for line in lines if line.split('=', 1)[0] not in values]
    lines += [key + '=' + (str(value).lower() if isinstance(value, bool) else str(value)) for key, value in values.items()]
    props.write_text('\n'.join(lines) + '\n')
    (root / 'config/c2me.toml').write_text('globalExecutorParallelism = ' + str(config['c2meWorkers']) + '\n')
    for name, content in config['modFiles'].items():
        (root / 'config' / name).write_text(content)
    if config['worldKey']:
        if world_module is None:
            spec = importlib.util.spec_from_file_location('world', Path(__file__).with_name('world.py'))
            world_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(world_module)
        world = world_module
        world.TRANSFER.mkdir(parents=True, mode=0o700, exist_ok=True)
        archive = world.TRANSFER / 'initial-world.zip'
        subprocess.run(['aws', 's3', 'cp', 's3://' + bucket + '/' + config['worldKey'], str(archive), '--only-show-errors'], check=True)
        try:
            world.restore(str(archive), 'bootstrap', bootstrap=True)
        finally:
            archive.unlink(missing_ok=True)
    print('S3 configuration and selected world installed before Java startup.', flush=True)


if __name__ == '__main__':
    apply(Path('/srv/minecraft'), json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
