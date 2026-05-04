# Hudu Self-Hosted (Caddy-fronted)

A Hudu instance for testing the `nautobot-ssot-hudu` plugin. Adapts Hudu's official self-hosted compose by **removing the bundled nginx** and reverse-proxying through your existing `caddy-docker-proxy` + LetsEncrypt setup.

> **Location note:** This lives in the plugin repo for now. If you keep Hudu past the trial, consider moving to `~/bingham/hudu/` to sit alongside `~/bingham/nautobot/`.

## Prerequisites

- Docker + Docker Compose
- The shared external `caddy` network (`docker network create caddy` if missing) running `caddy-docker-proxy`
- DNS for the chosen `DOMAIN` pointing to your Caddy host
- A Hudu HQ account at https://hq.hudu.com — license key is generated *after* first boot

## First-time bringup

```bash
cd development/hudu/
cp .env.example .env

# Generate the three encryption keys and paste into .env
echo "SECRET_KEY_BASE=$(openssl rand -hex 64)"
echo "PASSWORD_KEY=$(openssl rand -hex 16)"
echo "TWO_FACTOR_KEY=$(openssl rand -hex 16)"

$EDITOR .env                    # paste the three keys, set DOMAIN

docker compose up -d
docker compose logs -f app      # watch for "Listening on" / migrations done
```

Once the app is up, visit `https://${DOMAIN}/` — you should see Hudu's first-run admin/license screen.

## License key

1. Go to https://hq.hudu.com/ and sign in (Bing / Bingham account)
2. Navigate to the trial-start page → "Get Started!" → generates a license key
3. Paste the key into Hudu's first-run prompt
4. Create the admin user when asked

## Verify

```bash
docker compose ps               # all 4 services healthy
curl -I https://${DOMAIN}/      # 200 from Caddy → Puma
```

## Tear down

```bash
docker compose down             # keep volumes
docker compose down -v          # destroy postgres/redis/uploads (PERMANENT)
```

## Architecture deviations from upstream

| Upstream | Here | Why |
|---|---|---|
| `nginx` service (linuxserver/nginx) on ports 80/443 | removed | Caddy already handles edge HTTP/TLS |
| `proxy.conf` + `default.conf` manual editing | not needed | No Hudu nginx layer |
| `/var/www/hudu2/config:/config` host bind for nginx | not needed | Same reason |
| `worker` mounts `.:/app` for dev hot-reload | dropped | Production-style only |
| All services use docker-compose default names | `${COMPOSE_PROJECT}-` prefix | Avoid collisions with sibling stacks |

## Known unknowns (will surface during first boot)

- **Puma port assumption** — labels point to `3000`. If wrong, `docker compose exec app netstat -tnlp` shows what Puma actually binds; update `caddy.reverse_proxy` accordingly.
- **Static asset serving** — Rails in production normally has nginx in front to serve `/assets/`. Without it, Puma serves them, which is fine for testing but slower. If asset loading is sluggish under real use, we'd add `RAILS_SERVE_STATIC_FILES=true` and accept the perf cost, or re-introduce a thin nginx as a sidecar.
- **ActionCable WebSocket upgrade** — Caddy 2 handles `Upgrade: websocket` automatically. Should work without explicit labels, but if real-time features (notifications, presence) misbehave, that's the place to check.

## Backup what matters

```bash
# After Hudu has any real data:
docker compose exec db pg_dump -U postgres hudu_production | gzip > hudu-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
cp .env hudu-env-$(date -u +%Y%m%dT%H%M%SZ).bak  # CRITICAL — losing .env loses passwords
```
