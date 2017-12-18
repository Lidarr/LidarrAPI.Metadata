LidarrAPI.Metadata
==================

[![Travis Build Status](https://travis-ci.org/lidarr/LidarrAPI.Metadata.svg?branch=develop)](https://travis-ci.org/lidarr/LidarrAPI.Metadata)
[![Appveyor Build status](https://ci.appveyor.com/api/projects/status/fek6wd3ljyb7ty4h?svg=true)](https://ci.appveyor.com/project/Lidarr/lidarrapi-metadata)

This hosts the custom metadata API and resources Lidarr relies on.

Installation
============

The metadata server may be installed with ``pip install .`` in the root
directory or ``python setup.py install``. A development install that is linked
to the most recent file versions may be installed with ``pip install -e .`` or
``python setup.py develop``.

Running
=======

The metadata API server may be run by executing the ``server.py`` file or by
the command ``lidarr-metadata-server`` that is installed with the installation
instructions above.
