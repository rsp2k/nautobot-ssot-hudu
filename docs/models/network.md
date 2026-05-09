# Network

Maps Nautobot `ipam.Prefix` ↔ Hudu **Network**.

## Identity

| | |
|---|---|
| Composite identity | `(company_name, address)` — Networks are scoped per-company |
| Nautobot model | [`nautobot.ipam.models.Prefix`](https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/ipam/prefix/) |
| Hudu endpoint | `GET/POST/PUT/DELETE /api/v1/networks` (top-level, with `company_id` in body) |
| `hudu-magic` resource | `client.networks` |

## Attributes synced

| DiffSync attribute | Nautobot source | Hudu target | Notes |
|---|---|---|---|
| `address` | `str(Prefix.prefix)` (CIDR like `10.0.0.0/24`) | `Network.address` | Identifier |
| `name` | `Prefix.description` (or `address` if blank) | `Network.name` | Hudu requires a name; we default to address if Nautobot has no description |
| `description` | `Prefix.description` | `Network.description` | Empty string in Nautobot coerces to None |
| `vlan_vid` | `Prefix.vlan.vid` (or None) | `Network.vlan_id` (Hudu pk) | Cross-entity linkage; resolved to Hudu pk at write time |

## Linkages

When `Prefix.vlan` is set in Nautobot AND a matching Hudu VLAN exists (matched by `(company_name, vid)`), the synced Hudu Network's `vlan_id` is populated. Clicking on a Network in Hudu shows its parent VLAN.

## Lifecycle

- **Create**: POST to `/api/v1/networks` with `company_id`, `address`, `name`, `description`, optionally `vlan_id`.
- **Update**: PUT to `/api/v1/networks/<id>`. The plugin uses `client.put(...)` directly because `hudu-magic`'s registry incorrectly reports Networks as not supporting update.
- **Archive** / **Delete** as the standard pattern.

## API quirks

- **Pagination rejected** — `/api/v1/networks?page=1` returns HTTP 400. Plugin uses `client.get("networks", paginate=False)` to bypass.
- **`hudu-magic` says "does not support update"** — this is a library bug; the API actually accepts PUT. Plugin uses the underlying `client.put` to work around.

## Limitations

- Nautobot `Prefix.namespace` is not synced. Hudu doesn't have an equivalent concept; all networks within a Hudu Company share a flat namespace.
- Hudu Network has additional fields (`network_type`, `notes`, `is_radar`, `role_list_item_id`) that the plugin does NOT populate. These are operator-managed.
