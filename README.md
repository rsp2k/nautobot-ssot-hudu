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

| Nautobot | Hudu | Status |
|---|---|---|
| `tenancy.Tenant` | Company | ✅ name, description (notes) |
| `dcim.Device` | Asset (configurable layout + custom field map) | ✅ name + configurable custom-field map |
| `ipam.Prefix` | (TBD) | not started |
| `ipam.IPAddress` | (TBD) | not started |

**Identity model:**
- Companies match by `name` (globally unique on both sides)
- Devices match by `(company_name, name)` composite — Hudu Asset names are unique only within a company

**Empty-string normalization:** Both adapters coerce empty string `""` to `None` when loading. Hudu stores unset fields as null; Nautobot `CharField` defaults are `""`. Without coercion every sync would emit spurious updates for blank fields.

## Device custom field mapping

Operators choose which Nautobot Device attributes populate which Hudu custom-layout fields via PLUGINS_CONFIG:

```python
PLUGINS_CONFIG = {
    "nautobot_ssot_hudu": {
        "instance_url": "https://acme.huducloud.com",
        "secret_group_name": "Hudu Credentials",
        "asset_layouts": {
            "device": 7,  # Hudu asset_layout_id
        },
        # Hudu field label -> Nautobot Device attribute path (dotted)
        "device_field_map": {
            "Hostname": "name",
            "Management IP": "primary_ip4.host",
            "Model": "device_type.model",
            "Serial": "serial",
            "Status": "status.name",
            "Location": "location.name",
        },
    }
}
```

The Hudu asset_layout must already have custom fields with matching labels. Field-resolution uses safe None-propagation: a Device without a `primary_ip4` yields `None` for "Management IP" rather than raising `AttributeError`.

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

For static checks:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
```

For end-to-end testing against a real Nautobot instance, see `development/README.md` — a self-contained 4-container stack (postgres + redis + nautobot-web + nautobot-worker) with the plugin source bind-mounted for hot-reload and a seed script that creates synthetic Tenants + a Hudu SecretsGroup.

```bash
cd development/
cp .env.example .env  &&  $EDITOR .env
make build && make up
make seed
```

## License

Private / proprietary. Not yet published.
