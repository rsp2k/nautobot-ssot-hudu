# External Interactions

What this plugin does to your Hudu instance, what it reads, and the API quirks it works around.

## What gets created/updated/deleted in Hudu

For each entity in [the mapping](app_overview.md#what-it-syncs), the plugin executes:

- **Create** when a Nautobot record has no matching Hudu record (matched by composite identifier — see [Synced Entities](../models/company.md))
- **Update** when both sides exist but attribute values differ
- **Archive** (default) or **Delete** (`hard_delete=True`) when a Hudu record has no matching Nautobot record

All write operations go through the [`hudu-magic`](https://pypi.org/project/hudu-magic/) Python client, which makes standard HTTPS REST calls.

## Hudu-side prerequisites

These must exist before the first sync:

- **API key** — generated in Hudu Admin → API Keys with **Full access** scope
- **Asset layouts** — at least one layout for Devices, with custom fields whose labels match the keys in `device_field_map`. Layouts with names like "Network Device" are conventional.
- **Custom fields on the layout** matching the labels in your `device_field_map` config

## API quirks worked around

These are non-obvious Hudu-API behaviors the plugin handles transparently. Documented here so operators can confirm what they're seeing in their Hudu logs is expected.

### Pagination — `?page=` rejection

Several Hudu endpoints reject the auto-added `?page=1` query parameter:

| Endpoint | Pagination |
|---|---|
| `/api/v1/companies` | accepts page |
| `/api/v1/assets` | accepts page |
| `/api/v1/asset_layouts` | accepts page |
| `/api/v1/rack_storages` | accepts page |
| `/api/v1/networks` | rejects |
| `/api/v1/ip_addresses` | rejects |
| `/api/v1/vlans` | rejects |
| `/api/v1/rack_storage_items` | rejects |

The plugin bypasses pagination on the affected endpoints by calling the underlying client.get with `paginate=False`.

### Per-company vs top-level CRUD

**Asset CRUD is nested under the company**:

```
POST   /api/v1/companies/<cid>/assets
PUT    /api/v1/companies/<cid>/assets/<aid>
DELETE /api/v1/companies/<cid>/assets/<aid>
```

But Networks, IPAddresses, VLANs, Racks, and RackStorageItems are top-level, with `company_id` in the request body. The plugin handles both styles.

### IPAddress requires `network_id`, doesn't return it

Creating an IPAddress requires `network_id` in the payload, but GET responses don't include it. The plugin reverse-looks-up the parent Network at sync time using Python's `ipaddress` module against the loaded Hudu Network records.

### IPAddress DNS validation

Hudu validates that the FQDN resolves to the IP via DNS. For internal-only hostnames this fails with HTTP 422. The plugin always passes `skip_dns_validation: true` since sync data is operator-curated.

### RackStorageItem oddities

- The payload must be wrapped in `{"rack_storage_item": {...}}` (other resources accept top-level fields)
- The field is `end_unit`, not `size` (1U device gets `start_unit=1, end_unit=1`)
- GET responses **don't** include `rack_storage_id` — the plugin reverse-looks-up by walking the rack list response, which DOES include `front_items` and `rear_items` arrays with item IDs.

### Asset `custom_fields` payload format

Custom fields are passed as a list of single-key dicts with snake-cased label names:

```json
"custom_fields": [
    {"hostname": "acme-edge-01"},
    {"management_ip": "10.0.0.1"}
]
```

Hudu auto-derives the snake_case form from the human-readable label. GET responses return Title-Case labels in a `fields` array.

For the full discussion see the in-repo [HUDU_API_QUIRKS.md](https://github.com/rpm/nautobot-plugin-ssot-hudu/blob/main/development/hudu/HUDU_API_QUIRKS.md).

## What the plugin does NOT do

- It does not read Hudu Articles, Passwords, Procedures, or other documentation entities.
- It does not modify Hudu's account or admin settings.
- It does not delete companies/assets/etc. unless `hard_delete=True` is explicitly selected; default is archive (recoverable in the Hudu UI).
- It does not write to Nautobot — Nautobot is the source of truth.
