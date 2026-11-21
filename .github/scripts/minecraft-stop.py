"""Save and select the quiescent world before Terraform removes the server."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

values = json.loads(subprocess.check_output(['terraform', 'output', '-json'], text=True))
if 'instance_id' not in values:
    print('No server exists in Terraform state; no world to save.')
    sys.exit(0)
env = dict(os.environ, MAP_ACTION='stop', MAP_OBJECT_KEY='backups/' + str(uuid.uuid4()) + '.zip', MAP_INSTANCE_ID=values['instance_id']['value'])
with open(os.environ['GITHUB_ENV'], 'a') as output:
    output.write('MAP_INSTANCE_ID=' + env['MAP_INSTANCE_ID'] + '\n')
directory = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(directory / 'minecraft-map.py')], env=env, check=True)
subprocess.run([sys.executable, str(directory / 'minecraft-config.py'), 'select-saved-world'], env=env, check=True)
