#!/usr/bin/env python

from glob import glob
from setuptools import setup


with open('requirements.txt') as f:
    requirements = f.read().splitlines()

cli_files = []
for file in glob('cli/*.py'):
    if not file.endswith('__init__.py'):
        cli_files.append(file)

setup(
    name='PyTelTools',
    version='0.21',
    author='Luc Duron',
    author_email='l.duron@cnr.tm.fr',
    py_modules=['PyTelTools'],
    install_requires=requirements,
    description='Python library for Telemac post-processing tasks',
    url='https://github.com/CNR-Engineering/PyTelTools',
    scripts=cli_files,
)
