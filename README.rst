LidarrAPI.Metadata
==================

.. image:: https://dev.azure.com/Lidarr/Lidarr/_apis/build/status/lidarr.LidarrAPI.Metadata?branchName=develop
    :target: https://dev.azure.com/Lidarr/Lidarr/_build/latest?definitionId=3&branchName=develop
.. image:: https://api.codacy.com/project/badge/Grade/80dc9be416934129a9959b4620522e8f
   :alt: Codacy Badge
   :target: https://www.codacy.com/app/Lidarr/LidarrAPI.Metadata?utm_source=github.com&utm_medium=referral&utm_content=lidarr/LidarrAPI.Metadata&utm_campaign=badger

This hosts the custom metadata API and resources Lidarr relies on.

Development
===========

Dependencies are managed with `poetry <https://python-poetry.org>`_. A
development environment can be set up with
  
..  code-block:: shell

  poetry install --with=dev
  poetry shell # or poetry run ...

Running
=======

The metadata API server may be run by executing the ``server.py`` file or by
the command ``lidarr-metadata-server`` that is installed with the installation
instructions above.

Docker services
===============

The metadata server requires access to a musicbrainz postgresql database and solr search server.

To initialize a fresh VM, you can use::

  #! /bin/bash
  curl -fsSL https://get.docker.com | sh
  curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
  apt install -y --no-install-recommends emacs-nox git

To initialize the musicbrainz db run (**do not set brainzcode at this point**)::

  docker-compose up -d db
  docker-compose run --rm musicbrainz /usr/local/bin/createdb.sh -fetch

To set up the search index triggers, run::

  docker-compose up -d indexer musicbrainz
  docker-compose exec indexer python -m sir amqp_setup
  admin/create-amqp-extension
  admin/setup-amqp-triggers install

To set up the search indices, run::

  docker-compose run --rm musicbrainz fetch-dump.sh search
  docker-compose run --rm search load-search-indexes.sh --force

The database / search indices are now in line with the latest musicbrainz weekly dump.  To enable replication, set the brainzcode and run::

  docker-compose up -d

And wait for the database / indices to catch up with the latest hourly replication.  This could take a long time.

Next create the extra indices lidarr needs in::

  lidarrmetadata/sql/CreateIndices.sql

Then you need to set up the lidarr cache::

  docker-compose up -d cache-db
  docker-compose run --rm crawler 
  
- `docker-compose.yml` defines the base services required - the musicbrainz database, server, solr and supporting services.
- `docker-compose.dev.yml` exposes ports for the supporting services in `docker-compose.yml` to allow running the lidarr metadata service on the host.
- `docker-compose.prod.yml` runs the lidarr metadata service in docker in addition to the supporting services.  Supporting services are not exposed.
