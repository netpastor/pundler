import sys
import os.path as op
from os import makedirs, listdir
from importlib.machinery import ModuleSpec, SourceFileLoader
from itertools import groupby
from operator import itemgetter
import subprocess
import tempfile
import shutil
import yaml
from distlib import locators
from distlib.util import parse_requirement

default_locator = locators.AggregatingLocator(
                    locators.JSONLocator(),
                    locators.SimpleScrapingLocator('https://pypi.python.org/simple/',
                                          timeout=3.0),
                    scheme='legacy')
locate = default_locator.locate


# import logging
# import sys
# root = logging.getLogger()
# root.setLevel(logging.DEBUG)
# ch = logging.StreamHandler(sys.stdout)
# ch.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# ch.setFormatter(formatter)
# root.addHandler(ch)

def group(itr, key):
    return dict((x, [i[1] for i in y]) for x, y in groupby(sorted(itr, key=key), key=key))


class PundlerFinder(object):
    def __init__(self, basepath):
        self.basepath = basepath
        self.pundles = {}
        for line in open('freezed.txt').readlines():
            pundle = dict(zip(
                ['version', 'name', 'path'],
                [item.strip() for item in line.split('###')]
            ))
            self.pundles[pundle['name']] = pundle

    def find_spec(self, fullname, path, target_module):
        if path is not None:
            return None
        if fullname not in pundles:
            return None
        pundle = self.pundles[fullname]
        if pundle['path'].endswith('.py'):
            path = pundle['path']
            is_package = False
        else:
            path = op.join(pundle['path'], '__init__.py')
            is_package = True
        spec = ModuleSpec(fullname, SourceFileLoader(fullname, path), origin=path, is_package=is_package)
        if is_package:
            spec.submodule_search_locations = [pundle['path']]
        return spec


def install_finder():
    sys.meta_path.insert(0, PundlerFinder('.'))


def parse_requirements(requirements):
    def inner_parse(reqs):
        for req in reqs:
            parsed = parse_requirement(req)
            yield (parsed.name.lower(), parsed.constraints or [])
            dist = locate(req)
            if not dist:
                dist = locate(req, prereleases=True)
                if not dist:
                    raise Exception('Distribution for %s was not found' % req)
            yield from inner_parse(dist.run_requires)
    reqs = [(name, ','.join(''.join(x) for vers in versions for x in vers)) 
        for name, versions in group(inner_parse(requirements), itemgetter(0)).items()]
    return [locate(' '.join(req), prereleases=True) for req in reqs]


def get_installed():
    return group([item.split('-', 1) for item in listdir('Pundledir')], itemgetter(0))


def install(dist):
    name = dist.name
    tmpdir = tempfile.mkdtemp()
    print(name)
    res = subprocess.call([
        've/bin/pip', 'install',
        '--no-deps',
        '--install-option=%s' % ('--install-scripts=%s' % op.join(tmpdir, '.scripts')),
        '-t', tmpdir,
        '%s==%s'%(name, dist.version)
    ])
    if res != 0:
        raise Exception('%s was not installed due error' % name)
    print(tmpdir)
    target_dir = op.join('Pundledir', '{}-{}'.format(name.lower(), dist.version))
    try:
        makedirs(target_dir)
    except FileExistsError:
        pass
    for item in listdir(tmpdir):
        shutil.move(op.join(tmpdir, item), op.join(target_dir, item))
    shutil.rmtree(tmpdir)


def install_requirements():
    installed = get_installed()
    if not op.isfile('requirements.txt'):
        raise Exception('File requirements.txt not found')
    requirements = [line.strip() for line in open('requirements.txt').readlines() if line.strip() and not line.startswith('#')]
    dists = parse_requirements(requirements)
    with open('freezed.txt', 'w') as f:
        f.write('\n'.join('%s==%s' % (dist.name.lower(), dist.version) for dist in dists))
        f.write('\n')
    for dist in dists:
        if dist.version in installed.get(dist.name.lower(), []):
            continue
        install(dist)


def test():
    install_finder()
    import opster
    import trafaret
    from trafaret import extras
    import jinja2 as j
    print(repr(j))

if __name__ == '__main__':
    install_requirements()