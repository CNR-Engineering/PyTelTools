#!/usr/bin/env python

from setuptools import setup


with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='PyTelTools',
    version='0.2',
    author='Luc Duron',
    author_email='l.duron@cnr.tm.fr',
    py_modules=['PyTelTools'],
    install_requires=requirements,
    description='Python library for Telemac post-processing tasks',
    url='https://github.com/CNR-Engineering/PyTelTools',
)
