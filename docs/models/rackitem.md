# RackItem

Models the relationship "this Device is mounted in this Rack at this position." Maps Nautobot's `Device.rack` + `position` + `face` fields ↔ Hudu **RackStorageItem**.

## Identity

| | |
|---|---|
| Composite identity | `(company_name, asset_name)` — each Asset can be in at most one rack at one position |
| Nautobot source | [`nautobot.dcim.models.Device`](https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/dcim/device/) (devices with `rack` + `position` set) |
| Hudu endpoint | `GET/POST/PUT/DELETE /api/v1/rack_storage_items` |
| `hudu-magic` resource | `client.rack_storage_items` |

## Attributes synced

| DiffSync attribute | Nautobot source | Hudu target | Notes |
|---|---|---|---|
| `rack_name` | `Device.rack.name` | resolved to `rack_storage_id` at write time | |
| `start_unit` | `Device.position` | `rack_storage_item.start_unit` | |
| `end_unit` | `start_unit + Device.device_type.u_height - 1` | `rack_storage_item.end_unit` | Computed; 1U device gets `start=end` |
| `side` | `Device.face` | `rack_storage_item.side` | "front" / "rear" (lowercase only) |

## Lifecycle

- **Create**: requires both the parent Asset AND the parent Rack to exist in Hudu. The plugin resolves both Hudu pks via `adapter.get_all("device")` and `adapter.get_all("rack")` lookups by name.
- **Update**: PUT to `/api/v1/rack_storage_items/<id>` (changing position or face).
- **Delete**: 204 on the same endpoint. Removes the placement; doesn't affect the Asset itself.

## API quirks

This endpoint had three quirks worth flagging:

1. **Payload must be wrapped** in `{"rack_storage_item": {...}}` — other resources accept top-level fields without the wrapper. Inconsistent.
2. **Field is `end_unit`, not `size`** — a 1U device gets `start_unit=1, end_unit=1`. Validator returns 500 (not 422) on `end_unit < start_unit`.
3. **`rack_storage_id` missing from GET responses** — both list and individual GET omit it. The plugin reverse-looks-up by walking the rack list response, which DOES include `front_items` and `rear_items` arrays with item IDs.
4. **Pagination rejected** — same `paginate=False` bypass as Networks/IPs/VLANs.
5. **`side` is lowercase only** — Title-case `"Front"` returns 500.

## top_level ordering

RackItems must come AFTER both Devices AND Racks in `top_level` since they reference both. Current order:

```python
top_level = (
    "company",
    "device",
    "vlan",
    "network",
    "ipaddress",
    "rack",
    "rackitem",  # last — depends on device + rack existing
)
```

## Limitations

- One placement per Asset. If a Nautobot Device is somehow assigned to multiple racks, the plugin uses the first.
- No support for "reserved but empty" slots (Hudu has these via `is_reserved=true, has_items=false`). The plugin only manages slots backed by real Devices.
- Cabling, power connections, and other rack metadata aren't synced.
