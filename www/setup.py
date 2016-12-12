#!/usr/bin/env python3

from setuptools import setup

setup(name='VolComHoz',
      version='1.0',
      description='VolComHoz boiler tables',
      author='Vladislav Shpilevoy',
      author_email='vshpilevoi@mail.ru',
      url='https://github.com/Gerold103/volgograd',
      install_requires=['io', 'datetime', 'zipfile', 'json', 'argparse',
      			'tornado', 'tormysql', 'openpyxl']
      )