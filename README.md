# nautobot-ssot-hudu

A [Nautobot](https://nautobot.com) [SSoT](https://github.com/nautobot/nautobot-app-ssot) integration that pushes data from Nautobot into [Hudu](https://www.hudu.com).

**Direction:** Nautobot is the source of truth. Hudu is a Data Target — Nautobot writes Companies, Devices, and related records into Hudu.

**Status:** Beta. Seven entity types syncing end-to-end with full idempotency, 94 unit tests, validated against a live Hudu self-hosted instance. Not yet on PyPI.

**Compatibility:** Nautobot 3.0+, Python 3.10+, `nautobot-ssot` 4.2+, `hudu-magic` 0.4+.

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
| `dcim.Device` | Asset (per-role layouts + configurable custom field map) | ✅ name + custom-field map + role-based layout selection |
| `ipam.Prefix` | Network | ✅ address (CIDR), name, description |
| `ipam.IPAddress` | IPAddress | ✅ address (host), dns_name, description |
| `ipam.VLAN` | VLAN | ✅ vid (1-4094), name, description |
| `dcim.Rack` | RackStorage | ✅ name, height (U), width (in), serial, asset_tag, description, desc_units |
| `dcim.Device` rack/position/face | RackStorageItem | ✅ asset placement: rack_name, start_unit, end_unit, side |
| `dcim.Location` | *(no API equivalent)* | ⚠️ Hudu does not expose Locations as a CRUD entity. Per-device location is captured via `device_field_map["Location"] = "location.name"`. |

**Cross-entity linkages (set automatically when both sides are synced):**
- IPAddress → Asset (Hudu IP page shows the device it's assigned to, via Nautobot `IPAddress.interface_assignments → device`)
- Network → VLAN (Hudu Network page shows its VLAN, via Nautobot `Prefix.vlan`)

**Identity model:**

| Entity | Identifier | Notes |
|---|---|---|
| Company | `(name,)` | Both sides enforce uniqueness on name |
| Device | `(company_name, name)` | Hudu Asset names unique only within a company |
| Network | `(company_name, address)` | Networks are scoped per-company |
| IPAddress | `(company_name, address)` | `address` is the host, no mask |
| VLAN | `(company_name, vid)` | 802.1Q tag, two companies can each own VLAN 100 |
| Rack | `(company_name, name)` | Same scoping as Device |
| RackItem | `(company_name, asset_name)` | One rack item per asset max |

We deliberately use **human-readable identifiers** (names/vids) across the diff boundary, not Hudu primary keys. If a Hudu record is deleted and recreated, its pk changes but the identifier stays the same — the next sync rebinds by name rather than diffing as "needs update."

**Empty-string normalization:** Both adapters coerce empty string `""` to `None` when loading. Hudu stores unset fields as null; Nautobot `CharField` defaults are `""`. Without coercion every sync would emit spurious updates for blank fields.

## Device custom field mapping

Operators choose which Nautobot Device attributes populate which Hudu custom-layout fields via PLUGINS_CONFIG:

```python
PLUGINS_CONFIG = {
    "nautobot_ssot_hudu": {
        "instance_url": "https://acme.huducloud.com",
        "secret_group_name": "Hudu Credentials",
        "asset_layouts": {
            # Default Hudu asset_layout_id for Devices whose role isn't
            # explicitly mapped below. Unset/None → those devices skip.
            "device": 7,
            # Optional per-Nautobot-Role overrides. Keys are role names;
            # values are Hudu asset_layout_ids. Useful for MSPs documenting
            # heterogeneous fleets across multiple Hudu layouts.
            "device_by_role": {
                "router": 8,
                "switch": 9,
                "firewall": 10,
            },
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

## Limitations

- **Locations don't sync as a separate entity.** Hudu's REST API doesn't expose Locations as a manageable resource (verified empirically — `/api/v1/locations` returns 404, no Locations admin page). Per-device location is captured via the `device_field_map["Location"] = "location.name"` entry, which appears as a custom-field string on each synced Asset.
- **Layout migration isn't supported.** Hudu's API can't move an existing Asset between asset_layouts. If a Nautobot Device's role is reassigned and the new role maps to a different Hudu layout, the diff surfaces it but the writeback logs a warning and skips. Operator must delete + recreate manually.
- **`hudu-magic` library quirks** are documented in `development/hudu/HUDU_API_QUIRKS.md` — several endpoints reject the lib's auto-paginated `?page=1` parameter, and several update operations are missing from the lib's resource registry. The plugin works around all of them.

## Hudu prep

Before the first sync, the operator must:

1. **Create the asset_layout(s)** that Devices will live in. Hudu doesn't ship a built-in "Network Device" layout — each operator defines their own. Each layout's custom fields must have labels matching the keys in `device_field_map` (e.g. "Hostname", "Management IP", "Model", "Serial", "Status", "Location").
2. **Generate an API key** in Hudu (Admin → API Keys → New API Key). Scope: Full access. The "Delete data" permission is required if you plan to use `hard_delete=True`; "View passwords" and "Export data" can stay off — the plugin doesn't read passwords or export bulk data.
3. **Note the layout IDs** — visible in Hudu's Admin → Asset Layouts list. You'll wire them into `PLUGINS_CONFIG.asset_layouts.device` (and optionally `device_by_role`).

## Run-time options

Exposed as Job parameters in the Nautobot UI:

- **`dryrun`** *(framework-provided)* — calculate the diff but don't write. Default: `True`. This is the canonical control; we don't redeclare it.
- **`hard_delete`** — when an entity exists in Hudu but no longer in Nautobot, archive it (default, recoverable via Hudu UI) or hard-delete (irreversible).

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
