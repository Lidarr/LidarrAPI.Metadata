LidarrAPI.Metadata
==================

.. image:: https://dev.azure.com/Lidarr/Lidarr/_apis/build/status/lidarr.LidarrAPI.Metadata?branchName=develop
    :target: https://dev.azure.com/Lidarr/Lidarr/_build/latest?definitionId=3&branchName=develop
.. image:: https://api.codacy.com/project/badge/Grade/80dc9be416934129a9959b4620522e8f
   :alt: Codacy Badge
   :target: https://www.codacy.com/app/Lidarr/LidarrAPI.Metadata?utm_source=github.com&utm_medium=referral&utm_content=lidarr/LidarrAPI.Metadata&utm_campaign=badger

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

Docker services
===============

The metadata server requires access to a musicbrainz postgresql database and solr search server.

To initialize these in docker you can run

```
docker-compose build
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
docker-compose exec musicbrainz /createdb.sh -fetch
docker-compose exec sir make install
docker-compose exec sir make index
```

These will take several hours to complete.

 - `docker-compose.yml` defines the base services required - the musicbrainz database, server, solr and supporting services.
 - `docker-compose.dev.yml` exposes ports for the supporting services in `docker-compose.yml` to allow running the lidarr metadata service on the host.
 - `docker-compose.prod.yml` runs the lidarr metadata service in docker in addition to the supporting services.  Supporting services are not exposed.
