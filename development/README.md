# Dev Stack

Self-contained Nautobot 3.1 + the SSoT-Hudu plugin, isolated from any other Nautobot you might have running.

## Prerequisites

- Docker + Docker Compose
- An external Docker network named `caddy` running `caddy-docker-proxy` (per `~/.claude/CLAUDE.md`'s caddy convention). If you don't have one yet:
  ```bash
  docker network create caddy
  ```
  Then run a `caddy-docker-proxy` container attached to it.

## Bootstrap

```bash
cd development/
cp .env.example .env
$EDITOR .env                                          # set passwords + DOMAIN
make build && make up
make logs-web                                         # wait for "running on http://..." (~60s first boot)
```

Open `https://<DOMAIN>/` (e.g. `https://ssot-hudu-dev.local/`) and log in with `NAUTOBOT_SUPERUSER_NAME` / `NAUTOBOT_SUPERUSER_PASSWORD`.

> Add `127.0.0.1 ssot-hudu-dev.local` to `/etc/hosts` if you're using the default `.local` domain and your Caddy config doesn't already resolve it.

## Seed test data

```bash
make seed
```

Creates five fictional Tenants (Acme, Globex, Initech, Soylent, Cyberdyne) and a SecretsGroup named "Hudu Credentials" wired to the `HUDU_API_KEY` env var. Idempotent — re-running is safe.

## Run the SSoT job

In the Nautobot UI: **Apps → Single Source of Truth → Dashboard → Hudu (Data Target) → Run**

Job parameters:
- `dryrun` (default True) — show the diff without writing to Hudu. *Provided by the SSoT framework's `DataTarget` base class.*
- `hard_delete` (default False) — archive (recoverable in Hudu UI) vs. permanently delete orphaned Hudu records.

To target a real Hudu instance, set `HUDU_INSTANCE_URL` and `HUDU_API_KEY` in `.env` and re-run `make up && make seed`.

## After editing plugin code

```bash
make restart        # restarts nautobot-web; worker picks up new imports too
```

The plugin `src/` is bind-mounted into the container, so file edits are immediately visible — but Python's import cache means a process restart is required.

## Gotchas surfaced during 2026-05-04 first bringup

These are the not-obvious failures we hit. Document so future-you doesn't.

### 1. `COMPOSE_PROJECT_NAME`, not `COMPOSE_PROJECT`

The `.env` *must* set `COMPOSE_PROJECT_NAME=ssot-hudu-dev` (the canonical docker-compose env var), not `COMPOSE_PROJECT`. The latter is only a YAML substitution variable — it renames containers but does **not** tell docker-compose what the project itself is called.

Without `COMPOSE_PROJECT_NAME`, docker-compose falls back to the directory name as the project. Our directory is `development/`, which collides with at least one other project on this host (e.g. `nautobot-app-phones/development/`). Symptom: postgres data volume `development_postgres-data` gets shared across both, and our nautobot's `NAUTOBOT_DB_PASSWORD` doesn't match the password baked into the volume. You see "FATAL: password authentication failed for user nautobot" on every web boot.

`make ps` and `docker compose ls` will both lie about which project owns what — `docker compose ls -a` is the truth and shows the collision clearly.

### 2. Volume permissions on first boot

Nautobot runs as uid 999 inside the container, but docker-named-volumes start as root-owned (uid 0). Result: `PermissionError: [Errno 13] Permission denied: '/opt/nautobot/media/devicetype-images'` during `_preprocess_settings` on first boot — Nautobot can't `mkdir` inside its own `MEDIA_ROOT`.

Fix once at install time:

```bash
docker compose down
docker run --rm \
  -v ssot-hudu-dev_nautobot-media:/m \
  -v ssot-hudu-dev_nautobot-static:/s \
  -v ssot-hudu-dev_nautobot-git-repos:/g \
  alpine sh -c 'chown -R 999:999 /m /s /g'
docker compose up -d
```

Alternative: bake the chown into an init container. Not done here for simplicity.

### 3. `dryrun` (framework) vs `dry_run` (ours) — *fixed*

The SSoT framework's `DataTarget` already provides a `dryrun` Job parameter. Our Job class originally also declared `dry_run`, so the UI showed **both** checkboxes side-by-side — confusing and only the framework's actually gated writeback. Removed our duplicate; the framework's `dryrun` is the canonical control.

### 4. Hudu HQ has email-OTP gating that can 500

When signing into Hudu HQ to get a license key, the OTP step occasionally returns a 500. Refreshing to `https://hq.hudu.com/` typically lands on the dashboard anyway — the cookie session was set despite the error page. Don't trust the error; refresh first.

## Inspect Sync history

```bash
make sync-status            # last 10 syncs from the DB
make nbshell                # interactive shell_plus for ad-hoc queries
```

## Tear down

```bash
make down       # stop containers, keep data
make clean      # destroy volumes (postgres, media, etc.)
```
