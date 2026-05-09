# Company

Maps Nautobot `tenancy.Tenant` ↔ Hudu **Company**.

## Identity

| | |
|---|---|
| Composite identity | `(name,)` — globally unique on both sides |
| Nautobot model | [`nautobot.tenancy.models.Tenant`](https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/tenancy/tenant/) |
| Hudu endpoint | `GET/POST/PUT/DELETE /api/v1/companies/<id>` |
| `hudu-magic` resource | `client.companies` |

## Attributes synced

| DiffSync attribute | Nautobot source | Hudu target | Notes |
|---|---|---|---|
| `name` | `Tenant.name` | `Company.name` | Identifier |
| `description` | `Tenant.description` | `Company.notes` | Empty string in Nautobot coerces to None |

## Lifecycle

- **Create** when a Nautobot Tenant has no matching Hudu Company. Sets `name` and `notes`.
- **Update** when `description` differs. Other Hudu Company fields (address, phone, website, etc.) are operator-managed and not touched.
- **Archive** (default) or **Delete** (`hard_delete=True`) when a Hudu Company has no matching Nautobot Tenant.

## API quirks

None specific to Companies. Standard pagination behavior. Standard CRUD endpoints.

## Limitations

- Hudu Company has rich address/contact fields (address_line_1, city, state, zip, phone_number, website, etc.) which the plugin does NOT currently populate from Nautobot. Operators who want this info synced should add to a future `tenant_field_map` config (not yet implemented).
- The `notes` field is the only one updated. Manual edits to address/contact fields in Hudu are preserved.
