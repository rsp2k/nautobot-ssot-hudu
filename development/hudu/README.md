# Hudu Self-Hosted (Caddy-fronted)

A Hudu instance for testing the `nautobot-ssot-hudu` plugin. Adapts Hudu's official self-hosted compose by **removing the bundled nginx** and reverse-proxying through your existing `caddy-docker-proxy` + LetsEncrypt setup.

> **Location note:** This lives in the plugin repo for now. If you keep Hudu past the trial, consider moving to `~/your-stacks/hudu/` to sit alongside `~/your-stacks/nautobot/`.

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

1. Go to https://hq.hudu.com/ and sign in (your Hudu HQ account)
2. Navigate to the trial-start page → "Get Started!" → generates a license key
3. Paste the key into Hudu's first-run prompt
4. Create the admin user when asked

> **Trial expiry:** the Hudu trial is 14 days from license generation (e.g. created 2026-05-04 → expires 2026-05-19). Convert to a paid license or stand up a fresh trial after expiry.

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

## Validated during first bringup (2026-05-04)

All three "known unknowns" from the original design ended up working as guessed. Captured here for posterity:

- **Puma binds port 3000** — confirmed via `docker compose ps` showing `3000/tcp` for both `app` and `worker`. Caddy labels were correct.
- **Static asset serving works from Puma** — no `RAILS_SERVE_STATIC_FILES=true` env var needed; Hudu's Rails app handles `/assets/` requests itself in production mode. Performance has been adequate for testing-scale traffic; for real use a sidecar nginx may help.
- **ActionCable through Caddy** — basic browsing/notifications work. Real-time-heavy features (presence, live updates) not exercised under load. If they misbehave under real use, add explicit websocket-upgrade handling to the Caddy labels.

## Backup what matters

```bash
# After Hudu has any real data:
docker compose exec db pg_dump -U postgres hudu_production | gzip > hudu-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
cp .env hudu-env-$(date -u +%Y%m%dT%H%M%SZ).bak  # CRITICAL — losing .env loses passwords
```
