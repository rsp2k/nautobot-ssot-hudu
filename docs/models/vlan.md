# VLAN

Maps Nautobot `ipam.VLAN` ↔ Hudu **VLAN**.

## Identity

| | |
|---|---|
| Composite identity | `(company_name, vid)` — two companies can each own VLAN 100 |
| Nautobot model | [`nautobot.ipam.models.VLAN`](https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/ipam/vlan/) |
| Hudu endpoint | `GET/POST/PUT/DELETE /api/v1/vlans` |
| `hudu-magic` resource | `client.vlans` |

## Attributes synced

| DiffSync attribute | Nautobot source | Hudu target | Notes |
|---|---|---|---|
| `vid` | `VLAN.vid` (1-4094) | `vlan.vlan_id` | Identifier (the 802.1Q tag) |
| `name` | `VLAN.name` | `vlan.name` | |
| `description` | `VLAN.description` | `vlan.description` | Empty-to-None coercion |

## Linkages (incoming)

Networks reference VLANs via `Network.vlan_id` (Hudu pk). The plugin resolves this at sync time — see [Network](network.md).

## Lifecycle

Standard create / update / archive / delete. No quirks specific to VLANs beyond the cross-cutting ones (pagination bypass, etc.).

## API quirks

- **Pagination rejected** — `/api/v1/vlans?page=1` returns HTTP 400. Plugin uses `paginate=False` bypass.

## Limitations

- Nautobot `VLAN.vlan_group` is not synced. Hudu has a `vlan_zone_id` concept which we don't currently populate.
- Nautobot `VLAN.role` and `VLAN.status` are not synced as separate fields — `status` is captured into the description if relevant via custom fields (TBD).
