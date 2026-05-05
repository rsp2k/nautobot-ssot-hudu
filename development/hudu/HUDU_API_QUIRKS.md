# Hudu REST API + `hudu-magic` quirks

Empirical notes from building this plugin against Hudu (self-hosted, version visible
in the instance footer). Anything documented here was discovered by trial and is
*not* in Hudu's official API docs at the time of writing.

If you're building something else against Hudu, this file may save you the same
debugging round-trips.

## Pagination — `?page=` rejection

Several collection endpoints return **HTTP 400 "page is not a valid filter parameter"** when called with the `?page=N` query parameter that `hudu-magic` adds automatically:

| Endpoint | Accepts `?page=` |
|---|---|
| `/api/v1/companies` | ✅ yes |
| `/api/v1/assets` | ✅ yes |
| `/api/v1/asset_layouts` | ✅ yes |
| `/api/v1/rack_storages` | ✅ yes |
| `/api/v1/networks` | ❌ rejects |
| `/api/v1/ip_addresses` | ❌ rejects |
| `/api/v1/vlans` | ❌ rejects |
| `/api/v1/rack_storage_items` | ❌ rejects |

**Workaround**: bypass the wrapper by calling `client.get(endpoint, paginate=False)` instead of the typed resource's `.list()`. Returns raw dicts — convert to whatever shape you need yourself.

```python
# Instead of:
networks = client.networks.list()  # 400

# Do:
networks = client.get("networks", paginate=False) or []
```

## Update operations — `hudu-magic` says "does not support update"

Several resources are present in `hudu-magic`'s registry but the validator rejects PUT calls with **`HuduValidationError: <RESOURCE> does not support update`** — even though Hudu's REST API accepts the PUT just fine.

Affected resources observed:
- `asset_layouts`
- `networks`
- `ip_addresses`

**Workaround**: use the underlying `client.put(endpoint, json={...})` directly:

```python
# Instead of:
client.networks.update(net_id, payload={"network": {...}})  # rejected by lib validator

# Do:
client.put(f"networks/{net_id}", json={"network": {"description": "..."}})
```

This works because `client.put` is the lower-level HTTP method that doesn't consult the resource registry.

## Per-company endpoints (Assets only)

**Asset CRUD is nested under company**, but the rest aren't. Easy to assume the pattern is universal — it isn't.

```
✅ POST /api/v1/companies/<cid>/assets                 (Asset create)
✅ PUT  /api/v1/companies/<cid>/assets/<aid>           (Asset update)
✅ DELETE /api/v1/companies/<cid>/assets/<aid>         (Asset delete)

❌ POST /api/v1/assets                                 (404)

✅ POST /api/v1/networks                               (Networks are TOP-LEVEL with company_id in body)
✅ POST /api/v1/ip_addresses                           (same)
✅ POST /api/v1/vlans                                  (same)
✅ POST /api/v1/rack_storages                          (same)
✅ POST /api/v1/rack_storage_items                     (same)
```

`hudu-magic`'s `c.assets.create()` takes `company_id` as a required positional/kwarg and constructs the nested URL automatically.

## Custom fields on Assets — payload shape

Hudu Asset custom_fields are passed as **a list of single-key dicts**, with the keys as **snake_cased label names** (Hudu auto-derives the snake_case form from the human-readable label):

```python
client.assets.create(
    company_id=1,
    asset_layout_id=1,
    name="acme-edge-01",
    custom_fields=[
        {"hostname": "acme-edge-01"},        # label "Hostname"
        {"management_ip": "10.0.0.1"},       # label "Management IP"
        {"model": "ISR4321"},                # label "Model"
    ],
)
```

The response, however, returns fields in the original Title-Case form:

```json
"fields": [
    {"id": 1, "label": "Hostname", "value": "acme-edge-01", "position": 1},
    {"id": 2, "label": "Management IP", "value": "10.0.0.1", "position": 2}
]
```

## Asset layout — no `update` method exposed by the API registry

`/api/v1/asset_layouts` accepts GET and POST. PUT also works (we tested with `curl -X PUT`) but `hudu-magic`'s registry rejects `client.asset_layouts.update(...)` with `<RESOURCE> does not support update`.

When updating a layout's `fields`, **include the existing field's `id`** to preserve it; omit `id` to add new fields. Failing to include the id treats it as a new field with the same label and Hudu rejects with `Asset layout fields label has already been taken`.

```python
# update layout 1 to add fields without losing the existing "Hostname" field
client.put("asset_layouts/1", json={
    "asset_layout": {
        "fields": [
            {"id": 1, "label": "Hostname", "field_type": "Text", "position": 1},
            {"label": "Management IP", "field_type": "Text", "position": 2},
            {"label": "Model", "field_type": "Text", "position": 3},
        ],
    }
})
```

## IPAddresses — `network_id` required at create, missing in response

Creating a Hudu IPAddress **requires `network_id`** in the payload (otherwise the validator returns `Network does not belong to the specified company` even when the address is correct):

```json
POST /api/v1/ip_addresses
{
  "ip_address": {
    "company_id": 1,
    "network_id": 2,         // REQUIRED
    "address": "10.10.0.5",
    "fqdn": "host.lan",
    "skip_dns_validation": true,  // see below
    "description": "..."
  }
}
```

But the GET responses (both list and individual) **don't include `network_id`** — fields like `id`, `address`, `fqdn`, `company_id`, `asset_id` are present but `network_id` is absent.

**Reverse-lookup at sync time**: walk the loaded HuduNetworks, check IP membership in each `ipaddress.ip_network(n.address)`, and pick the first match. (Top-level ordering must place network loading before IP loading for this to work.)

## IPAddresses — `skip_dns_validation` flag

Without this flag, Hudu validates the FQDN actually resolves to the IP via DNS:

```
422 — "Fqdn does not resolve to 10.10.0.5. Select 'Skip DNS validation' if this is an internal-only hostname."
```

Sync-managed data is operator-curated; pass `skip_dns_validation: true` to bypass. Hudu's internal data still records the FQDN — it just doesn't try to externally verify it.

## RackStorageItems — three quirks at once

1. **Payload must be wrapped** in `rack_storage_item` key:
   ```json
   {"rack_storage_item": {"rack_storage_id": 2, "asset_id": 1, ...}}
   ```
   Networks, VLANs, etc. accept top-level fields without the wrapper. Inconsistent.

2. **Field is `end_unit`, not `size`**: a 1U device gets `start_unit=1, end_unit=1`. Hudu validates `end_unit >= start_unit` and emits a 500 (not a 422) on violation.

3. **`rack_storage_id` is missing from GET responses**: list and individual GET both omit it. The only way to know which rack an item belongs to is to walk `/api/v1/rack_storages` (which DOES include `front_items` and `rear_items` arrays with item IDs) and build an `item_id → rack_pk` map yourself.

## `side` casing

Lowercase only — `"front"` / `"rear"`. Title-case `"Front"` returns 500.

## Locations — no API surface

Hudu has `location_id` and `location_name` fields scattered on Networks, Racks, and Assets, but **`/api/v1/locations` doesn't exist** (404). No Locations admin page in the UI either, and `hudu-magic`'s `c.addresses` is just an alias for `c.ip_addresses` — not a separate locations resource.

What this means: locations on this Hudu version cannot be managed via API. They appear to derive from per-Company address fields (Hudu Companies have built-in `address_line_1`, `city`, `state`, `zip`, `country_name` fields) or from a non-public/admin path. Sync-side workaround is to populate Location info as a custom-field string on Assets (the default `device_field_map` already does this with `"Location": "location.name"`).

## Archive vs. delete

Most entities support both:

| | Archive | Delete |
|---|---|---|
| Recoverable | ✅ via Hudu UI ("Restore" link in archived list) | ❌ permanent |
| What's preserved | Record + all custom field values + linkages | Nothing (hard cascade) |
| API method | `<resource>.archive(id)` or `?archived=true` flag | `DELETE /api/v1/<resource>/<id>` (returns 204) |

Default plugin behavior is **archive** — when an entity disappears from Nautobot, the corresponding Hudu record is archived, recoverable. The `hard_delete` Job parameter switches to permanent delete when explicitly chosen.
