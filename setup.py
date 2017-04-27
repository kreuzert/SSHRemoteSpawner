import os
import sys

from distutils.core import setup

pjoin = os.path.join
here = os.path.abspath(os.path.dirname(__file__))

# Get the current package version.
version_ns = {}
with open(pjoin(here, 'version.py')) as f:
    exec(f.read(), {}, version_ns)

setup_args = dict(
    name                = 'sshremotespawner',
    packages            = ['sshremotespawner'],
    version             = version_ns['__version__'],
    description         = """SSHRemotespawner: A custom spawner for Jupyterhub.""",
    long_description    = "",
    author              = "Tim Kreuzer",
    author_email        = "t.kreuzer@fz-juelich.de",
    platforms           = "Linux",
    keywords            = ['Interactive', 'Interpreter', 'Shell', 'Web'],
)

# setuptools requirements
if 'setuptools' in sys.modules:
    setup_args['install_requires'] = install_requires = []
    with open('requirements.txt') as f:
        for line in f.readlines():
            req = line.strip()
            if not req or req.startswith(('-e', '#')):
                continue
            install_requires.append(req)


def main():
    setup(**setup_args)

if __name__ == '__main__':
    main()
