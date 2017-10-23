# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '03/01/2017'

from setuptools import setup, find_packages

setup(
    name='cfnutil',
    version='0.1',
    description='AWS CloudFormation Utilities',
    author='Kotaimen',
    author_email='kotaimen.c@gmail.com',
    url='https://github.com/Kotaimen/cfn-templates',
    license='MIT',
    install_requires=[
        'troposphere>=2.0.0',
        'awacs>=0.7.1',
        'cfn-flip>=0.2.1',
        'pyminifier>=2.1',
    ],
    packages=find_packages(include='cfnutil'),
)
