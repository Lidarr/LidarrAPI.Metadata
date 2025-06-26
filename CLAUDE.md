# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LidarrAPI.Metadata is a Python-based metadata API server that provides music metadata services for Lidarr. It integrates with MusicBrainz database, Solr search, Redis caching, and external music services like Spotify to deliver comprehensive music metadata.

## Development Commands

### Environment Setup
```bash
# Install dependencies with poetry (preferred)
poetry install --with=dev
poetry shell

# Or use pip with requirements.txt
pip install -r requirements.txt
```

### Running the Application
```bash
# Run the metadata server directly
python lidarrmetadata/server.py

# Or use the installed command
lidarr-metadata-server

# Run the crawler
lidarr-metadata-crawler
```

### Testing
```bash
# Run tests with pytest (in poetry environment)
pytest tests --doctest-modules

# Run tests with coverage
pytest tests --doctest-modules --cov=lidarrmetadata --cov-report=xml --cov-report=html

# Run tests with tox
tox
```

### Docker Services
```bash
# Start database services
docker-compose up -d db
docker-compose run --rm musicbrainz /usr/local/bin/createdb.sh -fetch

# Set up search indexing
docker-compose up -d indexer musicbrainz
docker-compose exec indexer python -m sir amqp_setup

# Development environment (exposes service ports)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production environment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Architecture

### Core Components
- **lidarrmetadata/app.py**: Main Quart application with API routes
- **lidarrmetadata/api.py**: Core API logic and data processing functions
- **lidarrmetadata/server.py**: Gunicorn-based WSGI server wrapper
- **lidarrmetadata/provider.py**: External service integrations (Spotify, Last.fm, etc.)
- **lidarrmetadata/cache.py**: Redis caching layer
- **lidarrmetadata/crawler.py**: Background data crawler

### Data Layer
- **lidarrmetadata/sql/**: SQL queries for MusicBrainz database operations
- PostgreSQL database with MusicBrainz schema
- Redis for caching and session management
- Solr for search indexing

### External Services
- MusicBrainz: Primary metadata source
- Spotify: Additional metadata and mapping
- Last.fm: Charts and popularity data
- Billboard: Chart data integration

### Configuration
- Environment-based configuration in `lidarrmetadata/config.py`
- Docker environment files: `postgres.env`
- Test configuration via `LIDARR_METADATA_CONFIG=TEST`

## Key Files
- **pyproject.toml**: Poetry dependencies and project configuration
- **tox.ini**: Test runner configuration
- **docker-compose*.yml**: Service orchestration for different environments
- **lidarrmetadata/sql/CreateIndices.sql**: Additional database indices for Lidarr

## Development Best Practices

- Use semantic commits like `feat(component): Add ...`

## Version Control

- Use git flow branches