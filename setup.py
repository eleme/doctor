# -*- coding: utf-8 -*-

import re

from setuptools import setup


version = ''
with open('doctor/__init__.py', 'r') as f:
        version = re.search(r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                            f.read(), re.M).group(1)


setup(
    name='doctor',
    version=version,
    description="",
    url='',
    author='Eleme Dev',
    author_email='',
    packages=['doctor'],
)
