"""Validate one complete Kids release and stage its exact offline packages."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

NAMES = {'omarchy-kids-base', 'omarchy-kids-settings'} | {
    'omarchy-kids-' + name for name in ('core', 'dns', 'browsing', 'time', 'school', 'grove')}


def stage(source, mirror, share):
    release = json.loads((source / 'release.json').read_text())
    if (set(release['packages']) != NAMES or release.get('dirty') or
            not re.fullmatch('[0-9a-f]{40}', release.get('source', ''))):
        raise ValueError('build the eight Kids packages from a clean, committed checkout first')
    archives = {}
    for name, info in release['packages'].items():
        filename = info['file']
        if Path(filename).name != filename or not filename.endswith('.pkg.tar.zst'):
            raise ValueError('invalid package filename')
        archive = source / filename
        if hashlib.sha256(archive.read_bytes()).hexdigest() != info['sha256']:
            raise ValueError('checksum mismatch: ' + filename)
        metadata = subprocess.check_output(['bsdtar', '-xOf', str(archive), '.PKGINFO'], text=True)
        actual = dict(line.split(' = ', 1) for line in metadata.splitlines()
                      if line.startswith(('pkgname = ', 'pkgver = ', 'arch = ')))
        if actual != {key: info[key] for key in ('pkgname', 'pkgver', 'arch')} or actual['pkgname'] != name:
            raise ValueError('package identity mismatch: ' + filename)
        if actual['arch'] not in ('any', 'x86_64'):
            raise ValueError('the Kids ISO requires x86_64 packages')
        archives[name] = archive
    versions = {name: info['pkgver'] for name, info in release['packages'].items()}
    if (versions['omarchy-kids-base'] != versions['omarchy-kids-settings'] or
            len({version.rsplit('-', 1)[-1] for version in versions.values()}) != 1 or
            len({versions['omarchy-kids-' + name] for name in ('core', 'dns', 'browsing', 'time', 'school', 'grove')}) != 1):
        raise ValueError('mixed Kids package revisions')
    mirror.mkdir(parents=True, exist_ok=True)
    share.mkdir(parents=True, exist_ok=True)
    # Clear only earlier Kids artifacts. Ordinary mirror pruning handles the
    # online dependency closure later in the build.
    for old in mirror.glob('omarchy-kids-*.pkg.tar.*'):
        old.unlink()
    for archive in archives.values():
        shutil.copy2(archive, mirror / archive.name)
    shutil.copy2(source / 'release.json', share / 'kids-release.json')
    # Source the installer lists/form from the package being installed; never
    # combine packages from one revision with a different source checkout.
    tree = share / 'kids-runtime'
    tree.mkdir(exist_ok=True)
    members = ['usr/share/omarchy/install/' + name for name in (
        'omarchy-base.packages', 'omarchy-other.packages', 'omarchy-child.packages', 'provisioning/setup-form.sh')]
    subprocess.run(['bsdtar', '-xf', str(archives['omarchy-kids-base']), '-C', str(tree), *members], check=True)


if __name__ == '__main__':
    stage(*map(Path, sys.argv[1:]))
