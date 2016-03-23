# -*- coding: utf-8 -*-

import re

from setuptools import setup


with open('doctor/__init__.py', 'rb') as f:
    version = re.search(r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        f.read(), re.M).group(1)

with open('./README.md', 'rb') as f:
    description = f.read()


setup(
    name='doctor',
    version=version,
    description=description,
    url='https://github.com/eleme/doctor',
    author='WangChao',
    author_email='hit9@ele.me, xiangyu.wang@ele.me',
    packages=['doctor'],
)
