"""Portable desired-configuration schema, shared with bootstrap and workflows."""
import copy
import json
import re

DEFAULT = {
    'minecraftVersion': '26.3', 'fabricLoaderVersion': '0.19.5',
    'fabricInstallerVersion': '1.1.1', 'fabricApiVersion': '0.166.2+26.3',
    'worldKey': None, 'c2meWorkers': 1,
    'mods': {name: True for name in ('lithium', 'ferrite-core', 'c2me-fabric', 'scalablelux', 'vmp-fabric', 'chunky', 'krypton')},
    'properties': {'motd': 'Angel - on-demand Minecraft', 'max-players': 10, 'view-distance': 8,
                   'simulation-distance': 6, 'difficulty': 'normal', 'gamemode': 'survival',
                   'pvp': True, 'online-mode': False, 'white-list': False, 'spawn-protection': 16},
    'modFiles': {},
}
WORLD = re.compile(r'^backups/[0-9a-f-]{36}\.zip$')


def validate(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('Configuration must contain exactly the supported settings')
    result = copy.deepcopy(value)
    for name in ('minecraftVersion', 'fabricLoaderVersion', 'fabricInstallerVersion'):
        if not isinstance(value[name], str) or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', value[name]):
            raise ValueError('Invalid release version: ' + name)
    if not isinstance(value['fabricApiVersion'], str) or not re.fullmatch(r'\d+\.\d+\.\d+\+[0-9.]+', value['fabricApiVersion']):
        raise ValueError('Use a Fabric API release such as 0.166.2+26.3')
    if value['worldKey'] is not None and (not isinstance(value['worldKey'], str) or not WORLD.fullmatch(value['worldKey'])):
        raise ValueError('Select a world stored in S3')
    if type(value['c2meWorkers']) is not int or value['c2meWorkers'] not in (1, 2):
        raise ValueError('C2ME workers must be 1 or 2')
    if not isinstance(value['mods'], dict) or set(value['mods']) != set(DEFAULT['mods']) or any(type(v) is not bool for v in value['mods'].values()):
        raise ValueError('Invalid mod selection')
    props = value['properties']
    if not isinstance(props, dict) or set(props) != set(DEFAULT['properties']):
        raise ValueError('Unsupported server.properties setting')
    for name, low, high in [('max-players', 1, 20), ('view-distance', 2, 8), ('simulation-distance', 2, 6), ('spawn-protection', 0, 64)]:
        if type(props[name]) is not int or not low <= props[name] <= high:
            raise ValueError(f'{name} must be between {low} and {high}')
    for name in ('pvp', 'online-mode', 'white-list'):
        if type(props[name]) is not bool:
            raise ValueError(name + ' must be a boolean')
    if props['difficulty'] not in ('peaceful', 'easy', 'normal', 'hard') or props['gamemode'] not in ('survival', 'creative', 'adventure', 'spectator'):
        raise ValueError('Invalid difficulty or game mode')
    if not isinstance(props['motd'], str) or not 1 <= len(props['motd']) <= 100 or any(c in props['motd'] for c in '\n\r\\'):
        raise ValueError('MOTD must be 1–100 characters without newlines or backslashes')
    files = value['modFiles']
    if not isinstance(files, dict) or len(files) > 10:
        raise ValueError('Use at most 10 custom mod configuration files')
    for name, content in files.items():
        if not re.fullmatch(r'[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,70}\.(json|toml|properties)', name) or name == 'c2me.toml':
            raise ValueError('Use a simple .json, .toml or .properties filename; c2me.toml is managed')
        if not isinstance(content, str) or len(content.encode()) > 4096 or '\x00' in content:
            raise ValueError('Each mod config must be text up to 4 KiB')
        if name.endswith('.json'):
            json.loads(content)
        if name.endswith('.toml'):
            try:
                import tomllib
            except ImportError:
                pass  # Python 3.9 on AL2023 consumes the already-validated snapshot.
            else:
                tomllib.loads(content)
    if len(json.dumps(result).encode()) > 32768:
        raise ValueError('Configuration exceeds 32 KiB')
    return result
