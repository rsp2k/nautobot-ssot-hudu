# IPAddress

Maps Nautobot `ipam.IPAddress` ↔ Hudu **IPAddress**.

## Identity

| | |
|---|---|
| Composite identity | `(company_name, address)` where `address` is the host (no mask) |
| Nautobot model | [`nautobot.ipam.models.IPAddress`](https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/ipam/ipaddress/) |
| Hudu endpoint | `GET/POST/PUT/DELETE /api/v1/ip_addresses` (top-level, with `company_id` + `network_id` in body) |
| `hudu-magic` resource | `client.ip_addresses` |

## Attributes synced

| DiffSync attribute | Nautobot source | Hudu target | Notes |
|---|---|---|---|
| `address` | `IPAddress.host` | `ip_address.address` | Identifier — host only, no mask |
| `dns_name` | `IPAddress.dns_name` | `ip_address.fqdn` | DNS validation skipped (see below) |
| `description` | `IPAddress.description` | `ip_address.description` | Empty-to-None coercion |
| `asset_name` | resolved via `interface_assignments` → device.name | `ip_address.asset_id` (Hudu pk) | Cross-entity linkage |

## Linkages

When the IPAddress is assigned to a Nautobot Interface via `IPAddressToInterface`, the linked Device's name is captured. At sync time, the plugin resolves the device name to a Hudu Asset pk and writes it to `ip_address.asset_id`. Clicking on an IP in Hudu shows the assigned device.

The plugin uses Nautobot 3.x's `IPAddressToInterface` through-model: `ip.interface_assignments.first().interface.device`. Multi-assignment is handled defensively — picks the first.

## Lifecycle

- **Create**: requires the parent Network to already exist in Hudu. Plugin reverse-looks-up the parent Network by IP membership against loaded HuduNetwork records (Python `ipaddress.ip_network` containment check). top_level ordering ensures Networks are loaded before IPs.
- **Update**: uses `client.put(...)` directly (lib registry bug — same as Networks).
- **Archive** / **Delete** as standard.

## API quirks

- **Pagination rejected** — `/api/v1/ip_addresses?page=1` returns HTTP 400. Plugin uses `paginate=False` bypass.
- **`network_id` required at create, missing in response** — Hudu requires the network ID at create time but doesn't return it on GET. Plugin reverse-looks-up the parent network via IP membership.
- **DNS validation gate** — Hudu validates that the FQDN resolves to the IP via DNS, which fails for internal-only hostnames (HTTP 422). Plugin always passes `skip_dns_validation: true` since sync data is operator-curated.
- **`hudu-magic` says "does not support update"** — same library bug as Networks. Plugin uses `client.put` directly.

## Limitations

- Multi-interface IPs (the same IP assigned to multiple Nautobot Interfaces) link only to the first Interface's Device. Hudu's `asset_id` is a scalar FK — there's no list equivalent.
- Nautobot's `IPAddress.role` (Loopback, Anycast, etc.) is not synced — Hudu has its own `role_list_item_id` concept that doesn't map cleanly.
