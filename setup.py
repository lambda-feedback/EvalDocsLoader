import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='evaldocsloader',
    packages=find_packages(include=['evaldocsloader']),
    version='0.1.5',
    description=
    'Mkdocs plugin for fetching additional .md files based on a fetched list, specifically designed to work with the LambdaFeedback architecture.',
    author='Pierre Tharreau',
    license='MIT',
    long_description_content_type="text/markdown",
    long_description=read('README.md'),
    install_requires=["mkdocs", "requests"],
    entry_points={
        'mkdocs.plugins': [
            'evaldocsloader = evaldocsloader.plugin:EvalDocsLoader',
        ]
    })
