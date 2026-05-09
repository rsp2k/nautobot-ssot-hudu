# App Overview

This document gives a top-level view of what the App does, who it's for, and which Nautobot facilities it leans on.

!!! note
    Throughout this documentation the terms "app" and "plugin" are used interchangeably.

## Description

`nautobot-ssot-hudu` is a one-way sync from Nautobot into [Hudu](https://www.hudu.com/) — IT documentation software popular with MSPs and internal IT teams. Nautobot is the source of truth for the network model; Hudu is the destination where that model becomes documentation.

The app is built on top of [`nautobot-app-ssot`](https://github.com/nautobot/nautobot-app-ssot)'s **DataTarget** framework, so it appears in the SSoT dashboard alongside other integrations and inherits the framework's diff/dry-run/sync-history machinery.

## What it syncs

| Nautobot | Hudu |
|---|---|
| `tenancy.Tenant` | Company |
| `dcim.Device` | Asset (custom asset_layout, per-role mapping supported) |
| `ipam.Prefix` | Network |
| `ipam.IPAddress` | IPAddress (linked to its parent network and to the assigned device) |
| `ipam.VLAN` | VLAN (linked from the parent Network) |
| `dcim.Rack` | RackStorage |
| `dcim.Device` rack/position/face | RackStorageItem (an Asset placed in a Rack) |

Cross-entity linkages (IP→Asset, Network→VLAN) are populated automatically when both sides are synced — clicking on an IP in Hudu shows the device it's assigned to, and clicking on a Network shows its VLAN.

## Audience (User Personas)

- **MSPs** documenting customer networks: Nautobot models the technical truth; Hudu surfaces it to technicians and ops staff who don't need (or shouldn't have) Nautobot access.
- **Internal IT departments** that want a separation between "the source of truth" (Nautobot) and "the runbook everyone reads" (Hudu).
- **Network architects** who already have a Hudu instance for general IT documentation and don't want to manually keep network records in sync.

## Direction & authority

**Nautobot is the source of truth. Hudu is read-mostly.**

When the sync runs:

- Records that exist in Nautobot but not in Hudu are **created** in Hudu.
- Records that exist on both sides with different attributes are **updated** in Hudu to match Nautobot.
- Records that exist in Hudu but not in Nautobot are **archived** in Hudu by default (recoverable via the Hudu UI). With the `hard_delete` job parameter set to True, they are permanently deleted instead.

Manual edits in Hudu will be overwritten on the next sync. Operators who want to preserve manual edits should make those edits via Nautobot.

## Nautobot Features Used

- **SSoT framework** — DataTarget Job, Sync model, dashboard integration
- **Jobs** — sync runs as a Nautobot Job, schedulable via the cron UI
- **Secrets / SecretsGroups** — Hudu API token resolved at sync time, never hardcoded in `nautobot_config.py`
- **PLUGINS_CONFIG** — instance URL, asset-layout IDs, and field-mapping config

## Authors and Maintainers

- Ryan Malloy (`@rpm`)
