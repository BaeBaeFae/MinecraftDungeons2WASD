"""Optional GitHub release updates. Never sends game state or diagnostics."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, build_opener

REPO = 'BaeBaeFae/MinecraftDungeons2WASD'
API = f'https://api.github.com/repos/{REPO}/releases?per_page=100'
MAX_DOWNLOAD = 128 * 1024 * 1024
HOSTS = {'api.github.com', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}


def version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-beta(?:\.(\d+))?)?', value)
    if not match:
        raise ValueError('Unrecognized release version.')
    return (*map(int, match.group(1, 2, 3)), int('-beta' not in value), int(match.group(4) or 0))


def safe_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Update URL is outside the trusted HTTPS hosts.')
    return url


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit, destination=None):
    request = Request(safe_url(url), headers={'User-Agent': 'DungeonsInputStudio-Updater',
                                             'Accept': 'application/vnd.github+json' if url.startswith('https://api.github.com/') else 'application/octet-stream'})
    opener = build_opener(HTTPSHandler(), Redirects())
    data = bytearray()
    count = 0
    with opener.open(request, timeout=15) as response:
        safe_url(response.url)
        while True:
            block = response.read(256 * 1024)
            if not block:
                break
            count += len(block)
            if count > limit:
                raise ValueError('Update response exceeds its size limit.')
            if destination is None:
                data.extend(block)
            else:
                destination.write(block)
    return bytes(data) if destination is None else count


def choose_release(releases, current):
    candidates = []
    for release in releases:
        try:
            tag = release['tag_name']
            v = version(tag)
            if release.get('draft') or v <= version(current):
                continue
            if release.get('prerelease') and '-beta' not in current:
                continue
            name = f'MinecraftDungeons2WASD-{tag.removeprefix("v")}-Windows-x64.zip'
            assets = [a for a in release.get('assets', []) if a.get('name') == name and a.get('state') == 'uploaded']
            if len(assets) != 1:
                continue
            asset = assets[0]
            digest = asset.get('digest', '')
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest) or not 0 < asset['size'] <= MAX_DOWNLOAD:
                continue
            url = asset['browser_download_url']
            if url != f'https://github.com/{REPO}/releases/download/{tag}/{name}':
                continue
            candidates.append((v, {'version': tag.removeprefix('v'), 'url': url,
                                   'sha256': digest[7:], 'size': asset['size']}))
        except (KeyError, TypeError, ValueError):
            continue
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def check(current):
    releases = json.loads(fetch(API, 4 * 1024 * 1024))
    if not isinstance(releases, list):
        raise ValueError('Unexpected GitHub release response.')
    return choose_release(releases, current)


def enabled(data_dir):
    path = Path(data_dir)/'updates'/'preferences.json'
    if not path.exists():
        return True
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('check_on_launch') is True
    except (OSError, ValueError, AttributeError):
        return False


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def set_enabled(data_dir, value):
    save_json(Path(data_dir)/'updates'/'preferences.json', {'check_on_launch': bool(value)})


def archive_paths(archive):
    paths, seen, total = [], set(), 0
    if len(archive.infolist()) > 6000:
        raise ValueError('Too many update files.')
    for entry in archive.infolist():
        path = PurePosixPath(entry.filename)
        if (path.is_absolute() or '\\' in entry.filename or ':' in entry.filename or
            any(part in ('..', '.') or part.endswith((' ', '.')) or
                re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)
                for part in path.parts) or not path.parts or path.parts[0] != 'DungeonsInputStudio'):
            raise ValueError('Unsafe update archive path.')
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError('Update archives cannot contain links.')
        key = entry.filename.casefold().rstrip('/')
        if key in seen:
            raise ValueError('Duplicate update archive path.')
        seen.add(key)
        total += entry.file_size
        if total > 512 * 1024 * 1024:
            raise ValueError('Unpacked update exceeds its size limit.')
        paths.append((entry, path))
    required = {'dungeonsinputstudio/dungeonsinputstudio.exe', 'dungeonsinputstudio/_internal/python312.dll'}
    if not required <= seen:
        raise ValueError('Update is missing required application files.')
    return paths


def stage_update(release, data_dir):
    import zipfile
    version(release['version'])
    root = (Path(data_dir)/'updates').resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='download-', dir=root) as temporary:
        folder = Path(temporary)
        download = folder/'download.zip'
        with download.open('wb') as target:
            size = fetch(release['url'], MAX_DOWNLOAD, target)
        with download.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if size != release['size'] or digest != release['sha256']:
            raise ValueError('Update download failed SHA-256 or size verification.')
        unpack = folder/'unpacked'
        with zipfile.ZipFile(download) as archive:
            paths = archive_paths(archive)
            for entry, relative in paths:
                destination = unpack.joinpath(*relative.parts)
                if entry.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as src, destination.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
        # Publish a complete side-by-side copy, never overwrite the running app.
        installed = Path(tempfile.mkdtemp(prefix=release['version']+'-', dir=root))
        unpack.rename(installed/'app')
        exe = installed/'app/DungeonsInputStudio/DungeonsInputStudio.exe'
        return {'version': release['version'], 'executable': str(exe.relative_to(root)),
                'files': {p.relative_to(exe.parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in exe.parent.rglob('*') if p.is_file()}}


def installed_executable(record, data_dir, current):
    try:
        if version(record['version']) <= version(current):
            return None
        root = (Path(data_dir)/'updates').resolve()
        exe = (root/record['executable']).resolve()
        if not exe.is_relative_to(root) or exe.name != 'DungeonsInputStudio.exe':
            return None
        files = record['files']
        if not isinstance(files, dict) or not 1 <= len(files) <= 6000 or 'DungeonsInputStudio.exe' not in files:
            return None
        for relative, digest in files.items():
            path = (exe.parent/relative).resolve()
            if not path.is_relative_to(exe.parent) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return None
        return exe
    except (OSError, ValueError, KeyError, TypeError):
        return None


def preferred_update(data_dir, current):
    try:
        record = json.loads((Path(data_dir)/'updates/active.json').read_text(encoding='utf-8'))
        return installed_executable(record, data_dir, current)
    except (OSError, ValueError):
        return None


def launch(exe):
    subprocess.Popen([str(exe)], cwd=str(Path(exe).parent), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def activate(record, data_dir, current):
    exe = installed_executable(record, data_dir, current)
    if exe is None:
        raise ValueError('Staged update is no longer valid.')
    launch(exe)
    save_json(Path(data_dir)/'updates/active.json', record)
