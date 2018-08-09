#!/usr/bin/env python

from setuptools import setup

setup(name='tap-logmeinrescue',
      version='0.0.1',
      description='Singer.io tap for extracting data from the LogMeIn Rescue API',
      author='Fishtown Analytics',
      url='http://fishtownanalytics.com',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_logmeinrescue'],
      install_requires=[
          'singer-python==5.0.12',
          'backoff==1.3.2',
          'requests==2.18.4',
          'funcy==1.10.1',
          'pytz',
      ],
      dependency_links=[
          '-e ../tap-framework',
      ],
      entry_points='''
          [console_scripts]
          tap-logmeinrescue=tap_logmeinrescue:main
      ''',
      packages=['tap_logmeinrescue'])
