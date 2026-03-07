# Deployment

## Production baseline

1. Copy `app_config_example.toml` to `app_config.toml`.
2. Set `THINKING_GRAPH_SECRET_KEY` to a strong random value.
3. Keep `debug = false`, `enable_cors = false`, `allow_runtime_settings_write = false`, and `allow_db_fallback = false`.
4. Mount `./data` as a persistent volume.

## User isolation

The application now stores all nodes, connections, audits, and saved graphs with an `owner_id`.

- Default mode: session isolation. Each browser session gets its own graph space.
- Recommended production mode: proxy identity isolation. Configure your reverse proxy or auth gateway to inject a trusted user header, then set `trusted_identity_header` in `app_config.toml` or `THINKING_GRAPH_TRUSTED_IDENTITY_HEADER`.

Example:

```toml
[auth]
trusted_identity_header = "X-Forwarded-User"
session_cookie_secure = true
```

Important:

- Your reverse proxy must strip any client-supplied `X-Forwarded-User` header and set it itself.
- Runtime settings writes are disabled by default so normal users cannot change shared server-side LLM config.
- `/api/settings` no longer returns API keys in plaintext.

## Docker

Build:

```bash
docker build -t thinking-graph:latest .
```

Run:

```bash
docker run -d \
  --name thinking-graph \
  -p 5000:5000 \
  -e THINKING_GRAPH_SECRET_KEY='replace-with-a-long-random-secret' \
  -e THINKING_GRAPH_SESSION_COOKIE_SECURE=true \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/app_config.toml:/app/app_config.toml:ro \
  thinking-graph:latest
```

If you terminate TLS at a reverse proxy, also set:

```bash
-e APP_TRUSTED_PROXY_HOPS=1
```

## Reverse proxy checklist

- Terminate HTTPS before exposing the app publicly.
- Forward `X-Forwarded-Proto`, `X-Forwarded-Host`, and optionally `X-Forwarded-User`.
- If using header-based identity, strip any incoming `X-Forwarded-User` from the public internet first.
- Keep the app behind the proxy; do not expose Flask debug mode.
