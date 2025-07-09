# Logging Configuration

The application uses structured logging with configurable levels and formats.

## Environment Variables

### LOG_LEVEL
Controls the minimum log level to display:
- `debug` - Show all logs including debug messages
- `info` - Show info, warning, error, and critical (default)
- `warning` or `warn` - Show warning, error, and critical
- `error` - Show error and critical only  
- `critical` - Show critical only

### LOG_FORMAT
Controls the log output format:
- `json` - Structured JSON logs for production (default)
- `text` - Human-readable colored logs for development

## Examples

### Development (Debug logs with readable format)
```bash
LOG_LEVEL=debug LOG_FORMAT=text python -m lidarrmetadata.server
```

### Production (Info logs with JSON format)
```bash
LOG_LEVEL=info LOG_FORMAT=json python -m lidarrmetadata.server
```

### Troubleshooting (Error logs only)
```bash
LOG_LEVEL=error LOG_FORMAT=text python -m lidarrmetadata.server
```

## Provider Debug Instrumentation

When `LOG_LEVEL=debug`, you'll see detailed timing information for all provider operations:

```
[debug] Provider operation started provider=tadb operation=get_artist_images
[info] Provider operation completed provider=tadb operation=get_artist_images elapsed_seconds=0.1234 success=True
```

This helps identify slow or failing external API calls and async performance issues.

## Migration from Legacy Configuration

The old `DEBUG=true` configuration is still supported for backward compatibility, but it's recommended to use the new environment variables:

| Legacy | New Equivalent |
|--------|----------------|
| `DEBUG=true` | `LOG_LEVEL=debug LOG_FORMAT=text` |
| `DEBUG=false` | `LOG_LEVEL=info LOG_FORMAT=json` |