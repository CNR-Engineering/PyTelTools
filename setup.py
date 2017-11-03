#!/usr/bin/env python

from glob import glob
from setuptools import find_packages, setup

from pyteltools import VERSION


EXCLUDE_FROM_PACKAGES = ['cli', 'tests']


with open('requirements.txt') as f:
    requirements = f.read().splitlines()

cli_files = []
for file in glob('cli/*.py'):
    if not file.endswith('__init__.py'):
        cli_files.append(file)

setup(
    name='PyTelTools',
    version=VERSION,
    author='Luc Duron',
    author_email='l.duron@cnr.tm.fr',
    packages=find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    include_package_data=True,  # see data files in `MANIFEST.in`
    scripts=cli_files,
    install_requires=requirements,
    description='Python library for Telemac post-processing tasks',
    url='https://github.com/CNR-Engineering/PyTelTools',
)
