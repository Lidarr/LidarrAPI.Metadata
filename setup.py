"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

import lidarrmetadata

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='lidarrmetadata',
    version=lidarrmetadata.__version__,
    description='Lidarr metadata API',
    long_description=long_description,
    url='https://github.com/lidarr/lidarrapi.metadata',
    packages=find_packages(),

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['cherrypy',
                      'flasgger',
                      'flask',
                      'flask-cache',
                      'musicbrainzngs',
                      'peewee',
                      'psycopg2',
                      'pylast',
                      'python-dateutil',
                      'raven[flask]',
                      'requests',
                      'wikipedia'],

    package_data={
      'lidarrmetadata.sql': ['*.sql']
    },

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'lidarr-metadata-server=lidarrmetadata.server:main',
        ],
    },
)
