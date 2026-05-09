# Using the App

Common scenarios this plugin solves and how to configure them.

## Use case 1 — MSP documenting customer networks

You're an MSP. Each customer is a Nautobot **Tenant**, and you want a Hudu **Company** per customer with the network gear documented as Hudu Assets.

Configure once:

```python
PLUGINS_CONFIG = {
    "nautobot_ssot_hudu": {
        "instance_url": "https://msp.huducloud.com",
        "secret_group_name": "Hudu Credentials",
        "asset_layouts": {"device": 1},  # your "Network Device" layout id
        "device_field_map": {
            "Hostname":      "name",
            "Management IP": "primary_ip4.host",
            "Model":         "device_type.model",
            "Serial":        "serial",
            "Status":        "status.name",
            "Location":      "location.name",
        },
    },
}
```

Schedule the Job to run nightly. Customers' Hudu pages get refreshed automatically; manual edits in Hudu get overwritten on the next sync (Nautobot is the source of truth).

## Use case 2 — Heterogeneous device fleets across multiple Hudu layouts

You document switches in a "Switches" layout, routers in a "Routers" layout, and firewalls in a "Firewalls" layout — each with custom fields specific to that role.

Use the per-role layout override:

```python
"asset_layouts": {
    "device": 1,                    # default layout, used for unmapped roles
    "device_by_role": {
        "router":   2,
        "switch":   3,
        "firewall": 4,
    },
},
```

The plugin looks up each device's `role.name` and routes to the matching layout. Devices with no matching role mapping fall back to the default `device` layout.

## Use case 3 — IPAM and VLAN documentation

You want Hudu's IPAM module populated from Nautobot's authoritative IPAM data. With `device_field_map` and the cross-entity linkages enabled (default behavior):

- `ipam.Prefix` → Hudu Network, linked to the parent VLAN automatically
- `ipam.IPAddress` → Hudu IPAddress, linked to the assigned device's Asset automatically

The links are derived from Nautobot's existing FK relationships:

- `Prefix.vlan` → Network's `vlan_id` in Hudu
- `IPAddress.interface_assignments → first interface → device` → IPAddress's `asset_id` in Hudu

Operators don't need to maintain the Hudu-side linkages manually. They follow the Nautobot model.

## Use case 4 — Rack diagrams in Hudu

Hudu's rack-storage feature renders rack diagrams. With `dcim.Device` records that have `rack`, `position`, and `face` set in Nautobot, the sync populates Hudu's rack slots automatically.

No additional config — works out of the box once Devices and Racks are syncing. The composite identity `(company_name, asset_name)` keeps placements correct even when the same hostname (e.g. `core-sw-01`) exists in multiple customer environments.

## Use case 5 — Validation before write

Every sync can be run with `dryrun=True` (default). The Sync Detail page shows the diff without writing anything. Useful for:

- Verifying a config change before applying it
- Auditing what's drifted between Nautobot and Hudu
- Demonstrating to stakeholders what the sync would do

The framework's `dryrun` parameter is the canonical control. The plugin doesn't redeclare it.
