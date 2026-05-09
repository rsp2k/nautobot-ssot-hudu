# Device

Maps Nautobot `dcim.Device` ↔ Hudu **Asset** (with operator-configured custom fields).

## Identity

| | |
|---|---|
| Composite identity | `(company_name, name)` — Hudu Asset names are unique only within a company |
| Nautobot model | [`nautobot.dcim.models.Device`](https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/dcim/device/) |
| Hudu endpoint | `GET/POST/PUT/DELETE /api/v1/companies/<cid>/assets/<aid>` (per-company nested) |
| `hudu-magic` resource | `client.assets` |

## Attributes synced

| DiffSync attribute | Nautobot source | Hudu target | Notes |
|---|---|---|---|
| `name` | `Device.name` | `Asset.name` | Identifier |
| `asset_layout_id` | derived from role + config | `Asset.asset_layout_id` | See per-role layouts below |
| `field_values` | walked from `device_field_map` | `Asset.fields[*].value` | Hudu custom-layout fields |

## Per-role asset_layout selection

`PLUGINS_CONFIG["asset_layouts"]["device_by_role"]` routes Devices to different Hudu layouts based on Nautobot role:

```python
"asset_layouts": {
    "device": 1,                     # default fallback
    "device_by_role": {
        "router":   2,
        "switch":   3,
        "firewall": 4,
    },
},
```

Resolution: per-role override wins; falls back to `asset_layouts.device` if not in the map. If neither matches, the device is skipped.

## Custom field mapping

`PLUGINS_CONFIG["device_field_map"]` maps Hudu custom-field labels to Nautobot Device dotted-attribute paths:

```python
"device_field_map": {
    "Hostname":      "name",
    "Management IP": "primary_ip4.host",
    "Model":         "device_type.model",
    "Serial":        "serial",
    "Status":        "status.name",
    "Location":      "location.name",
},
```

Resolution uses safe None-propagation — a Device without `primary_ip4` yields `None` for "Management IP" rather than raising `AttributeError`.

The Hudu asset_layout must already have custom fields with **matching labels** (Title Case as shown). Hudu auto-derives the snake_case API key from the label.

## Lifecycle

- **Create**: POST to `/api/v1/companies/<cid>/assets` with `name`, `asset_layout_id`, and `custom_fields` array. Returns the new asset id, captured as `pk` for future updates.
- **Update**: PUT to the same path. Only the changed `field_values` are sent.
- **Layout migration is NOT supported by Hudu's API.** If a Nautobot Device's role changes such that its `asset_layout_id` would change, the diff surfaces it but the writeback logs a warning and skips. Operator must manually delete + recreate to migrate layouts.
- **Archive** or **Delete** as the company-archive/delete pattern.

## API quirks

- **Per-company nested endpoint** — Asset CRUD is at `/api/v1/companies/<cid>/assets`, not `/api/v1/assets`. The plugin handles this transparently.
- **`custom_fields` payload format** — array of single-key dicts with snake_cased label keys: `[{"hostname": "..."}, {"management_ip": "..."}]`. Server-derived from the label.

## Linked entities

- **IPAddresses** assigned to the Device's interfaces are linked back via `IPAddress.asset_id` — see [IPAddress](ipaddress.md).
- **RackItems** for rack-mounted devices are created as separate records — see [RackItem](rackitem.md).
