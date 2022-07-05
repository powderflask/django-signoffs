#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'Django>=3.2, <4.0',
    'persisting-theory',
    'regex',
]

test_requirements = [ ]

setup(
    author="Joseph Fall",
    author_email='powderflask@gmail.coom',
    python_requires='>=3.7',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Generic signoffs, approvals, and approval processes for django models.",
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='django_signoffs',
    name='django_signoffs',
    packages=find_packages(include=['signoffs', 'signoffs.*']),
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/powderflask/django_signoffs',
    version='0.1.0',
    zip_safe=False,
)
