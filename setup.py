#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name            = 'django-dbfs',
    version         = '0.0.0',
    description     = 'Fuse filesystem stored in database',
    author          = 'Jakub Dorňák',
    author_email    = 'jakub.dornak@misli.cz',
    license         = 'BSD',
    url             = 'https://github.com/misli/django-dbfs',
    packages        = find_packages(),
    install_requires=[
        'Django',
        'fusepy',
    ],
    classifiers     = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Framework :: Django :: 1.11',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
    ],
)
