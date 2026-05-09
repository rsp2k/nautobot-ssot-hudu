# Development Environment

The repo includes a self-contained dev stack at `development/` (Nautobot side) and `development/hudu/` (Hudu self-hosted side).

## Quick start

```shell
# clone, then:
cd development/
cp .env.example .env
$EDITOR .env                # set passwords + DOMAIN
make build && make up
make seed                   # synthetic Tenants + Hudu SecretsGroup
```

Open `https://<DOMAIN>/` and log in. The plugin is installed in editable mode against the bind-mounted `src/` directory — file edits are visible in the container, but Python's import cache means a `make restart` is required for changes to take effect.

## Hudu side

For end-to-end tests against a real Hudu instance, see `development/hudu/`. That subdirectory contains a Caddy-fronted Hudu self-hosted stack (4 containers: postgres + redis + Rails app + Sidekiq worker) adapted from Hudu's official docker-compose by removing the bundled nginx layer.

```shell
cd development/hudu/
cp .env.example .env
# generate the three encryption keys and paste into .env
docker compose up -d
```

See [`development/hudu/README.md`](https://github.com/rpm/nautobot-plugin-ssot-hudu/blob/main/development/hudu/README.md) for the full bringup, including the license-key flow.

## Tests

```shell
uv sync --extra dev
uv run pytest                  # unit tests, no Nautobot needed (conftest mocks)
uv run ruff check
```

The unit-test suite runs in <1s with no Docker. For integration tests against the live Django ORM, use `make nbshell` inside the dev container.

## Bringup gotchas

Documented at length in `development/README.md`. The four real ones:

1. **`COMPOSE_PROJECT_NAME` (not `COMPOSE_PROJECT`)** — docker-compose's canonical project-name env var. Without it, the project name defaults to the directory name ("development"), which collides with sibling stacks and causes shared volumes.
2. **Volume permissions** — Nautobot runs as uid 999; docker-named-volumes start root-owned. First-boot `chown` is required.
3. **`dryrun` (framework) vs. `dry_run` (ours)** — the plugin's duplicate has been removed; framework's `dryrun` is canonical.
4. **Hudu HQ OTP 500** — occasional. Refresh the dashboard URL after submitting OTP; the cookie is usually set despite the error page.

## Project structure

```
src/nautobot_ssot_hudu/
├── __init__.py                  # NautobotAppConfig
├── jobs.py                      # HuduDataTarget Job
├── diffsync/
│   ├── adapters/
│   │   ├── nautobot.py          # source: Nautobot ORM → DiffSync models
│   │   └── hudu.py              # target: writes via hudu-magic
│   └── models/
│       ├── base.py
│       ├── company.py           # Company + HuduCompany
│       ├── device.py            # Device + HuduDevice + custom-fields helpers
│       ├── network.py           # Network + HuduNetwork
│       ├── ipaddress.py         # IPAddress + HuduIPAddress
│       ├── vlan.py              # VLAN + HuduVLAN
│       ├── rack.py              # Rack + HuduRack
│       └── rackitem.py          # RackItem + HuduRackItem
├── utils/
│   └── hudu_client.py           # build_client() resolves URL + Secret
└── tests/                       # 94 unit tests, conftest mocks Nautobot
```

Each entity gets its own model file with both the shared DiffSync model and the Hudu-side subclass that has the CRUD methods. The Hudu-side subclasses are the only place that knows about `hudu-magic`.
