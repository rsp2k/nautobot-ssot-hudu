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
- `dry_run` (default True) — show the diff without writing to Hudu
- `hard_delete` (default False) — archive vs. permanently delete orphaned Hudu Companies

To target a real Hudu instance, set `HUDU_INSTANCE_URL` and `HUDU_API_KEY` in `.env` and re-run `make up && make seed`.

## After editing plugin code

```bash
make restart        # restarts nautobot-web; worker picks up new imports too
```

The plugin `src/` is bind-mounted into the container, so file edits are immediately visible — but Python's import cache means a process restart is required.

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
