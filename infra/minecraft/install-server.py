"""Verified Fabric/mod provisioning; only manifest-owned jars are replaced."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

API = 'https://api.modrinth.com/v2'
ROOT = Path('/srv/minecraft')
PROJECTS = ('fabric-api', 'lithium', 'ferrite-core', 'c2me-fabric',
            'scalablelux', 'noisium', 'vmp-fabric', 'chunky', 'krypton')


def fetch(url):
    if not url.startswith('https://'):
        raise ValueError('Downloads require HTTPS')
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'portfolio-minecraft-bootstrap/1.0'})
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def document(url):
    return json.loads(fetch(url))


def atomic(path, data):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data)
    os.replace(temporary, path)


def verified(path, url, digest, algorithm):
    if path.exists() and hashlib.new(algorithm, path.read_bytes()).hexdigest() == digest:
        return
    content = fetch(url)
    if hashlib.new(algorithm, content).hexdigest() != digest:
        raise RuntimeError('Checksum mismatch: ' + path.name)
    atomic(path, content)


def compatible(version, game):
    return game in version['game_versions'] and 'fabric' in version['loaders']


def choose(project, game, api_version):
    query = urllib.parse.urlencode({'game_versions': json.dumps([game]), 'loaders': '["fabric"]'})
    versions = document(f'{API}/project/{project}/version?{query}')
    versions = [v for v in versions if compatible(v, game)]
    if project == 'fabric-api':
        versions = [v for v in versions if v['version_number'] == api_version]
    if project == 'krypton':
        versions = [v for v in versions if v['version_type'] == 'release']
        if not versions:
            print('[Mods] WARNING: no stable compatible Krypton release; skipping', flush=True)
            return None
    if not versions:
        raise RuntimeError(f'No compatible release for required mod {project} / {game}')
    return max(versions, key=lambda v: v['date_published'])


def resolve_mods(game, api_version):
    selected = {}

    def include(version):
        project = version['project_id']
        if project in selected:
            if selected[project]['id'] != version['id']:
                raise RuntimeError('Conflicting required dependency versions: ' + project)
            return
        if not compatible(version, game):
            raise RuntimeError('Incompatible dependency: ' + version['name'])
        selected[project] = version
        for dependency in version.get('dependencies', []):
            if dependency['dependency_type'] != 'required':
                continue
            if dependency.get('version_id'):
                include(document(f"{API}/version/{dependency['version_id']}"))
            elif dependency.get('project_id'):
                if dependency['project_id'] not in selected:
                    include(choose(dependency['project_id'], game, api_version))
            else:
                raise RuntimeError('Unresolvable required dependency')

    errors = []
    for project in PROJECTS:
        try:
            version = choose(project, game, api_version)
            if version:
                include(version)
                print(f"[Mods] {project}: {version['version_number']}", flush=True)
        except RuntimeError as error:
            errors.append(str(error))
    if errors:
        raise RuntimeError('; '.join(errors))
    return selected


def install_mods(root, game, api_version):
    selected = resolve_mods(game, api_version)
    mods = root / 'mods'
    mods.mkdir(exist_ok=True)
    manifest = mods / '.portfolio-managed.json'
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    staged = mods / '.portfolio-staging'
    staged.mkdir(exist_ok=True)
    managed = {}
    for project, version in selected.items():
        files = [f for f in version['files'] if f.get('primary')]
        if len(files) != 1:
            raise RuntimeError('Expected one primary mod JAR: ' + project)
        artifact = files[0]
        filename = artifact['filename']
        if Path(filename).name != filename or not filename.endswith('.jar'):
            raise RuntimeError('Unsafe mod filename')
        target = mods / filename
        digest = artifact['hashes']['sha512']
        if target.exists():
            current = hashlib.sha512(target.read_bytes()).hexdigest()
            known = previous.get(filename, {}).get('sha512')
            if current != digest and current != known:
                raise RuntimeError('Refusing to overwrite customized mod: ' + filename)
        verified(staged / filename, artifact['url'], digest, 'sha512')
        managed[filename] = {'project': project, 'version': version['id'], 'sha512': digest}
    # Fetch/check every artifact before changing the installed set. Leave custom JARs alone.
    for filename in previous:
        if Path(filename).name != filename or not filename.endswith('.jar'):
            raise RuntimeError('Invalid managed manifest')
        path = mods / filename
        if filename not in managed and path.exists():
            if hashlib.sha512(path.read_bytes()).hexdigest() != previous[filename]['sha512']:
                raise RuntimeError('Previously managed JAR was customized: ' + filename)
            path.unlink()
    for filename in managed:
        os.replace(staged / filename, mods / filename)
    atomic(manifest, (json.dumps(managed, indent=2) + '\n').encode())


def tune_configs(root):
    properties = root / 'server.properties'
    text = properties.read_text() if properties.exists() else ''
    settings = {'server-port': '25565', 'online-mode': 'false', 'enforce-secure-profile': 'false',
                'enable-rcon': 'false', 'enable-query': 'false', 'view-distance': '8',
                'simulation-distance': '6', 'white-list': 'false', 'enforce-whitelist': 'false'}
    for key, value in settings.items():
        pattern = rf'(?m)^{re.escape(key)}\s*[=:].*$'
        if re.search(pattern, text):
            text = re.sub(pattern, f'{key}={value}', text)
        else:
            text = text.rstrip('\n') + f'\n{key}={value}\n'
    for key, value in {'max-players': '10', 'motd': 'Angel - on-demand Minecraft'}.items():
        if not re.search(rf'(?m)^{key}\s*[=:]', text):
            text += f'{key}={value}\n'
    atomic(properties, text.lstrip('\n').encode())
    config = root / 'config'
    config.mkdir(exist_ok=True)
    c2me = config / 'c2me.toml'
    text = c2me.read_text() if c2me.exists() else ''
    # C2ME's global executor option is a root TOML key, ahead of any [tables].
    split = re.search(r'(?m)^\s*\[', text)
    top, rest = (text[:split.start()], text[split.start():]) if split else (text, '')
    pattern = r'(?m)^\s*globalExecutorParallelism\s*=.*$'
    if re.search(pattern, top):
        top = re.sub(pattern, 'globalExecutorParallelism = 1', top)
    else:
        top = 'globalExecutorParallelism = 1\n' + top
    atomic(c2me, (top + rest).encode())
    eula = root / 'eula.txt'
    if not eula.exists():
        eula.write_text('eula=true\n')


def main():
    arguments = sys.argv[1:]
    check_only = bool(arguments and arguments[0] == '--check')
    if check_only:
        arguments.pop(0)
    game, loader, installer, api_version = arguments
    if check_only:
        # Run on the GitHub runner before allocating any EC2 resources.
        manifest = document('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json')
        if not any(v['id'] == game for v in manifest['versions']):
            raise RuntimeError('Requested Minecraft version is unavailable: ' + game)
        fetch(f'https://meta.fabricmc.net/v2/versions/loader/{game}/{loader}/{installer}/server/jar')
        resolve_mods(game, api_version)
        print('[Preflight] Required releases available', flush=True)
        return
    print('[Fabric] Verifying Mojang server and pinned Fabric launcher', flush=True)
    manifest = document('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json')
    entry = next((v for v in manifest['versions'] if v['id'] == game), None)
    if not entry:
        raise RuntimeError('Requested Minecraft version is unavailable: ' + game)
    metadata = document(entry['url'])
    if metadata.get('javaVersion', {}).get('majorVersion', 25) > 25:
        raise RuntimeError('Requested Minecraft version requires Java newer than 25')
    artifact = metadata['downloads']['server']
    verified(ROOT / 'server.jar', artifact['url'], artifact['sha1'], 'sha1')
    url = f'https://meta.fabricmc.net/v2/versions/loader/{game}/{loader}/{installer}/server/jar'
    launcher = fetch(url)
    with zipfile.ZipFile(io.BytesIO(launcher)) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Corrupt Fabric launcher')
    atomic(ROOT / 'fabric-server-launch.jar', launcher)
    print('[Mods] Resolving compatible Modrinth releases and required dependencies', flush=True)
    install_mods(ROOT, game, api_version)
    print('[JVM tuning] Preserving custom settings; limiting C2ME to one worker', flush=True)
    tune_configs(ROOT)


if __name__ == '__main__':
    main()
