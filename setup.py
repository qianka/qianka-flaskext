# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='qianka-flaskext',
    version='1.0.dev',

    install_requires=[
        'Flask',
        'Flask-Assets',
        'Flask-SQLAlchemy',
        'redis',
        'msgpack-python',
    ],
    setup_requires=[],
    tests_require=[],

    author="Qianka Inc.",
    description="",
    url=''
)
