# FastAPI Migration Progress

## Overview
Converting Lidarr Metadata API from Quart to FastAPI endpoint by endpoint to resolve async issues while maintaining service availability.

## Phase 1: Dual Setup
- [x] Add FastAPI dependencies to pyproject.toml (also updated aiohttp, async-timeout, yarl, typing-extensions)
- [x] Create FastAPI app alongside existing Quart app
- [ ] Set up routing logic to direct specific endpoints to FastAPI vs Quart
- [ ] Port shared middleware (CORS, Sentry, rate limiting)

## Phase 2: Endpoint Migration (Simple to Complex)

### Basic Endpoints
- [ ] `GET /` - Basic info endpoint (no external dependencies)
- [ ] `GET /recent/artist` - Database queries only
- [ ] `GET /recent/album` - Database queries only

### Core Functionality
- [ ] `GET /artist/{mbid}` - Artist information with validation
- [ ] `POST /artist/{mbid}/refresh` - Artist cache refresh
- [ ] `GET /album/{mbid}` - Album information with validation
- [ ] `POST /album/{mbid}/refresh` - Album cache refresh
- [ ] `GET /series/{mbid}` - Series information

### Search Endpoints
- [ ] `GET /search/artist` - Artist search
- [ ] `GET /search/album` - Album search
- [ ] `GET /search/all` - Combined search
- [ ] `GET /search` - Generic search router
- [ ] `POST /search/fingerprint` - Fingerprint search

### Chart Endpoints (External Dependencies)
- [ ] `GET /chart/{name}/{type}/{selection}` - Music charts
  - [ ] Billboard integration
  - [ ] Apple Music integration
  - [ ] iTunes integration
  - [ ] Last.fm integration

### Spotify Integration (OAuth + External API)
- [ ] `GET /spotify/artist/{spotify_id}` - Spotify artist lookup
- [ ] `GET /spotify/album/{spotify_id}` - Spotify album lookup
- [ ] `POST /spotify/lookup` - Bulk Spotify lookup
- [ ] `GET /spotify/auth` - OAuth redirect handling
- [ ] `GET /spotify/renew` - Token renewal

### Administrative
- [ ] `GET /invalidate` - Cache invalidation

## Phase 3: Cleanup
- [ ] Remove Quart dependencies
- [ ] Update deployment configuration
- [ ] Update documentation
- [ ] Performance validation

## Per-Endpoint Process
For each endpoint:
1. **Create Pydantic models** for request/response validation
2. **Implement FastAPI route** with identical behavior
3. **Add feature flag** to route traffic between implementations
4. **Run tests** against both FastAPI and Quart versions
5. **Performance comparison** and validation
6. **Switch traffic** to FastAPI version
7. **Remove Quart route** after successful validation

## Critical Async Issues to Address
- [ ] Replace synchronous Redis client in rate limiter with aioredis
- [ ] Replace or wrap synchronous libraries (billboard, spotipy, pylast)
- [ ] Remove `asyncio.sleep()` anti-patterns
- [ ] Add proper async rate limiting

## Migration Notes
- Maintain backward compatibility throughout migration
- Use feature flags for gradual rollout
- Monitor performance and error rates per endpoint
- Keep rollback capability for each endpoint