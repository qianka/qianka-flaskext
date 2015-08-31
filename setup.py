# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='qianka-flaskext',
    version='1.1.1',

    packages=find_packages(),

    install_requires=[
        'Flask',
        'Flask-Assets',
        'redis',
        'msgpack-python',
        'qianka-sqlalchemy',
    ],
    setup_requires=[],
    tests_require=[],

    author="Qianka Inc.",
    description="",
    url='http://github.com/qianka/qianka-flaskext'
)
