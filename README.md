# nautobot-ssot-hudu

A [Nautobot](https://nautobot.com) [SSoT](https://github.com/nautobot/nautobot-app-ssot) integration that pushes data from Nautobot into [Hudu](https://www.hudu.com).

**Direction:** Nautobot is the source of truth. Hudu is a Data Target — Nautobot writes Companies, Devices, and related records into Hudu.

**Status:** Alpha. Under active development.

**Compatibility:** Nautobot 3.0+, Python 3.10+, `nautobot-ssot` 4.2+.

## Architecture

Built on the [DiffSync](https://github.com/networktocode/diffsync) library bundled with `nautobot-ssot`. The [hudu-magic](https://pypi.org/project/hudu-magic/) client library handles all Hudu API I/O.

```
Nautobot ORM ──> Nautobot DiffSync adapter ─┐
                                            ├──> diff ──> Hudu DiffSync adapter ──> hudu-magic ──> Hudu API
                                  Hudu API ─┘   (read current state)
```

## Mapping

| Nautobot | Hudu |
|---|---|
| `tenancy.Tenant` | Company |
| `dcim.Device` | Asset (configurable layout) |
| `ipam.Prefix` | (TBD) |
| `ipam.IPAddress` | (TBD) |

## Configuration

Configuration lives in `nautobot_config.py` under `PLUGINS_CONFIG`. Hudu API credentials are stored as a Nautobot Secret and resolved at sync time.

```python
PLUGINS_CONFIG = {
    "nautobot_ssot_hudu": {
        "instance_url": "https://acme.huducloud.com",
        "secret_group_name": "Hudu Credentials",  # Name of a Nautobot SecretsGroup
        "asset_layouts": {
            "device": 7,  # Hudu asset_layout_id
        },
    }
}
```

The named SecretsGroup must contain a Secret with access-type **HTTP** and
secret-type **Token** holding the Hudu API key.

```python
```

Run-time options (dry-run, scope filters) are exposed as Job parameters.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
```

## License

Private / proprietary. Not yet published.
