# Screenshot Tools

Utilities for capturing screenshots from the Solar Smart Clock remotely.

## Prerequisites

The clock must be running with the HTTP screenshot server enabled (port 8080).

## Scripts

### clockshot

Fast screenshot capture with automatic fallback:
1. Tries HTTP first (~155ms) - fastest method
2. Falls back to SSH with multiplexing (~250ms)
3. Final fallback to direct SSH (~3800ms)

```bash
# Capture to default location
./clockshot

# Capture to specific file
./clockshot /path/to/output.png
```

### clockshot-connect

Pre-establish SSH master connection for faster SSH-based captures:

```bash
./clockshot-connect
```

## SSH Configuration

For optimal SSH performance, copy `ssh_config.example` to `~/.ssh/config` and create the socket directory:

```bash
mkdir -p ~/.ssh/sockets && chmod 700 ~/.ssh/sockets
```

## HTTP Endpoints

The clock exposes these endpoints on port 8080:

| Endpoint | Description |
|----------|-------------|
| `/screenshot` | Capture current display as PNG |
| `/health` | Health check (returns "OK") |
| `/next` | Navigate to next view |
| `/prev` | Navigate to previous view |
| `/view` | Get current view name and index |

Example:
```bash
curl -o screen.png http://clock.local:8080/screenshot
curl http://clock.local:8080/next
curl http://clock.local:8080/view
```
