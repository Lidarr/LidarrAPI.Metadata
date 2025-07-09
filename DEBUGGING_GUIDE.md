# Debugging Guide for /artist/<mbid> Timeout Issues

This guide explains how to use the comprehensive debugging tools implemented to diagnose and resolve persistent timeout issues in the `/artist/<mbid>` endpoint.

## Quick Start - Debugging a Timeout

When you encounter a timeout on `/artist/<mbid>`, follow these steps:

### 1. Check Overall Health
```bash
curl http://localhost:5001/health/async
```
This shows:
- Active async operations
- Hanging operations (operations running longer than their timeout)
- Recent failures
- Circuit breaker status

### 2. Check Database Performance
```bash
curl http://localhost:5001/debug/database
```
This shows:
- Connection pool utilization
- Average query times
- Slow queries
- Connection acquisition metrics

### 3. Debug Specific Artist
```bash
curl "http://localhost:5001/debug/artist/<PROBLEMATIC_MBID>"
```
This provides:
- Current timeout settings
- Database metrics at the moment
- Active async operations
- Provider information
- Circuit breaker status

### 4. Monitor Real-Time Operations
```bash
curl http://localhost:5001/debug/operations/hanging
```
This shows currently hanging operations with detailed context.

## Understanding the Debug Output

### Database Metrics (`/debug/database`)

```json
{
  "connection_pool": {
    "pool_size": 10,
    "active_connections": 2,
    "idle_connections": 8,
    "utilization_percent": 20.0
  },
  "connection_acquisition": {
    "total_acquisitions": 150,
    "failed_acquisitions": 0,
    "avg_acquisition_time": 0.0034,
    "failure_rate_percent": 0.0
  },
  "query_performance": {
    "recent_queries_count": 12,
    "avg_query_time": 0.156,
    "slow_queries_count": 2,
    "slow_query_threshold": 5.0
  }
}
```

**Red Flags:**
- `utilization_percent > 80%` - Connection pool exhaustion
- `avg_acquisition_time > 1.0` - Slow connection acquisition
- `failure_rate_percent > 5%` - Connection failures
- `avg_query_time > 2.0` - Slow queries

### Async Operations (`/health/async`)

```json
{
  "healthy": false,
  "active_operations": 3,
  "hanging_operations": 1,
  "hanging_details": [
    {
      "name": "database_artist_lookup",
      "running_time": 15.4,
      "timeout": 10.0,
      "context": {
        "mbids": ["artist-id-here"]
      }
    }
  ]
}
```

**Red Flags:**
- `hanging_operations > 0` - Operations stuck longer than timeout
- `active_operations` growing without completing

## Common Timeout Scenarios and Solutions

### Scenario 1: Database Query Timeout
**Symptoms:**
- `database_artist_lookup` appears in hanging operations
- High `avg_query_time` in database metrics
- EXPLAIN ANALYZE logs showing slow query plans

**Investigation:**
1. Check slow queries in `/debug/database`
2. Look for EXPLAIN ANALYZE logs in application logs
3. Check connection pool utilization

**Solutions:**
- Optimize slow SQL queries
- Add database indexes
- Increase database_query timeout
- Scale database resources

### Scenario 2: External API Timeout
**Symptoms:**
- `artist_overviews_batch` or `artist_images_*` in hanging operations
- Circuit breaker showing failures for external services

**Investigation:**
1. Check circuit breaker status in `/debug/artist/<mbid>`
2. Monitor external API response times in logs
3. Check network connectivity to external services

**Solutions:**
- Increase external_api timeout
- Implement retry logic
- Use circuit breaker more aggressively
- Cache external API responses longer

### Scenario 3: Provider-Specific Issues
**Symptoms:**
- Specific provider operations appearing in hanging operations
- Provider operation logs showing slow responses

**Investigation:**
1. Check provider-specific metrics in debug output
2. Look for "Slow provider operation" warnings in logs
3. Monitor specific provider response times

**Solutions:**
- Increase timeout for specific provider operations
- Implement provider-specific circuit breakers
- Cache provider responses more aggressively

## Log Analysis

### Key Log Entries to Monitor

1. **Slow Database Queries:**
```
logger.warning("Slow database query detected", extra={
    'execution_time': 8.5,
    'sql_preview': 'SELECT row_to_json(artist_data)...',
    'performance_issue': True
})
```

2. **Critical Slow Queries with EXPLAIN:**
```
logger.error("Critical slow query - EXPLAIN ANALYZE", extra={
    'execution_time': 9.8,
    'explain_plan': {...},
    'critical_performance_issue': True
})
```

3. **Hanging Operations:**
```
logger.warning("album_search tasks timed out after 20s: get_overview(), artist_images_primary()", extra={
    'timed_out_coroutines': ['get_overview()', 'artist_images_primary()']
})
```

4. **Provider Operations:**
```
logger.warning("Slow provider operation", extra={
    'provider': 'WikipediaProvider',
    'operation': 'get_artist_overview',
    'elapsed_seconds': 7.2,
    'performance_concern': True
})
```

## Timeout Configuration

Current timeout settings can be viewed via environment variables or in the debug output:

```bash
# View current timeouts
curl http://localhost:5001/debug/artist/any-valid-uuid | jq '.timeouts'
```

### Environment Variables for Timeout Tuning:
```bash
export ASYNC_TIMEOUT_ARTIST_INFO=60        # Increase from 45s
export ASYNC_TIMEOUT_DATABASE_QUERY=15     # Increase from 10s  
export ASYNC_TIMEOUT_EXTERNAL_API=15       # Increase from 10s
export ASYNC_TIMEOUT_ARTIST_IMAGES=15      # Increase from 10s
```

## Emergency Actions

### Clear Hanging Operations
```bash
curl -X POST http://localhost:5001/health/async/cleanup
```

### Reset Database Metrics
```bash
curl -X POST http://localhost:5001/debug/database/reset
```

### Circuit Breaker Status
Check if external services are being circuit-broken:
```bash
curl http://localhost:5001/health/async | jq '.circuit_breakers'
```

## Performance Monitoring Script

Use this script to continuously monitor for issues:

```bash
#!/bin/bash
# monitor_performance.sh

echo "Monitoring artist endpoint performance..."
while true; do
    echo "=== $(date) ==="
    
    # Check for hanging operations
    hanging=$(curl -s http://localhost:5001/health/async | jq '.hanging_operations')
    if [ "$hanging" -gt 0 ]; then
        echo "⚠️  ALERT: $hanging hanging operations detected!"
        curl -s http://localhost:5001/debug/operations/hanging | jq '.'
    fi
    
    # Check database performance
    db_util=$(curl -s http://localhost:5001/debug/database | jq '.connection_pool.utilization_percent')
    if (( $(echo "$db_util > 80" | bc -l) )); then
        echo "⚠️  ALERT: High database connection utilization: $db_util%"
    fi
    
    echo "Status: $hanging hanging ops, $db_util% DB utilization"
    sleep 30
done
```

## Next Steps

If timeouts persist after using these debugging tools:

1. **Gather Evidence:** Collect logs and debug output during a timeout event
2. **Identify Pattern:** Determine if it's always the same operation timing out
3. **Resource Analysis:** Check if it's a resource constraint (CPU, memory, network)
4. **Infrastructure:** Consider if the issue is at the infrastructure level
5. **Code Review:** Review the specific operation that's consistently timing out

The comprehensive tracking added should now give you exact visibility into where the 45-second timeout is being consumed in the `/artist/<mbid>` endpoint.