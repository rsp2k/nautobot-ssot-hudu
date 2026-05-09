# Rack

Maps Nautobot `dcim.Rack` ↔ Hudu **RackStorage**.

## Identity

| | |
|---|---|
| Composite identity | `(company_name, name)` |
| Nautobot model | [`nautobot.dcim.models.Rack`](https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/dcim/rack/) |
| Hudu endpoint | `GET/POST/PUT/DELETE /api/v1/rack_storages` (Hudu's UI calls them "Racks" but the API path is `rack_storages`) |
| `hudu-magic` resource | `client.rack_storages` |

## Attributes synced

| DiffSync attribute | Nautobot source | Hudu target | Notes |
|---|---|---|---|
| `name` | `Rack.name` | `rack_storage.name` | Identifier |
| `height` | `Rack.u_height` | `rack_storage.height` | Default 42 if unset |
| `width` | `Rack.width` | `rack_storage.width` | 10 / 19 / 21 / 23 (inches); plain int on both sides |
| `serial` | `Rack.serial` | `rack_storage.serial_number` | Empty-to-None |
| `asset_tag` | `Rack.asset_tag` | `rack_storage.asset_tag` | Empty-to-None |
| `description` | `Rack.comments` | `rack_storage.description` | Note the Nautobot↔Hudu naming difference (Nautobot uses `comments`, Hudu uses `description`) |
| `descending_units` | `Rack.desc_units` | `rack_storage.descending_units` | |

`starting_unit` is hardcoded to 1 (Nautobot doesn't model this).

## Lifecycle

Standard create / update / archive / delete. Pagination works normally on this endpoint (unlike Networks/IPs/VLANs).

## API quirks

None specific to Racks. Pagination accepts `?page=` normally.

## Limitations

- `Rack.location`, `Rack.rack_group`, `Rack.role` foreign keys are NOT synced. They'd require cross-reference resolution to Hudu entities the plugin doesn't currently model.
- `Rack.status` is not synced (no clean Hudu equivalent for the rack status concept).
- Hudu's `max_wattage`, `power_draw_utilization`, etc. are operator-managed; the plugin doesn't populate them.

## Related entities

When Devices are mounted in racks (Nautobot's `Device.rack` + `position` + `face`), each placement is synced as a separate **RackItem** record — see [RackItem](rackitem.md).
