# Frequently Asked Questions

## Why one-way only? Can I sync Hudu → Nautobot?

The plugin is a **DataTarget** (Nautobot writes to Hudu), not a DataSource (Hudu writes to Nautobot). Bidirectional sync requires conflict resolution semantics — what wins when both sides edit the same field? — and that design isn't free.

If your team's actual workflow is "we edit in Hudu, want it to appear in Nautobot," that's a different plugin shape. The SSoT framework supports DataSources too; we just haven't built one.

## Why are my manual Hudu edits getting overwritten?

Nautobot is the source of truth. Every time the sync runs, it overwrites Hudu fields with their Nautobot values. If you want a field to be operator-managed in Hudu, don't include it in `device_field_map`.

For ad-hoc Hudu fields (custom layout fields not in our map), the plugin leaves them alone. It only writes to fields it's configured to.

## Why doesn't the plugin sync Locations?

Hudu's REST API doesn't expose Locations as a manageable resource — `/api/v1/locations` returns 404, there's no admin page for them, and `hudu-magic` doesn't have a `locations` resource. The `location_id` field on Networks/Racks/Assets is filterable but not creatable via API.

Per-device location IS still captured — it's a custom field via `device_field_map["Location"] = "location.name"` by default. So the location info appears on the synced Hudu Asset, just as a string rather than as a typed FK.

## What happens if my Nautobot Devices don't have a `tenant`?

They're skipped. The plugin filters Devices by `tenant__isnull=False` because Hudu's data model is company-scoped — there's no concept of a "tenant-less device" in Hudu. Same applies to Prefixes, IPAddresses, VLANs, and Racks.

## Does the plugin modify Nautobot data?

No. Nautobot is the source of truth — the plugin only reads from Nautobot. Sync state (the Sync record, JobLogs, etc.) is written by the SSoT framework itself, not by this plugin.

## What about the SSoT framework's `dryrun` vs. our `dry_run`?

There's only one — the framework's `dryrun`. Earlier versions of the plugin also declared a `dry_run` Job parameter, which was redundant and confusing (UI showed both checkboxes). The plugin's duplicate has been removed; the framework's `dryrun` is the canonical control.

## Can I run multiple Hudu instances from one Nautobot?

Not currently. `PLUGINS_CONFIG` is single-instance — `instance_url` and `secret_group_name` are scalars, not lists. Multi-instance support would be a substantial design change (likely a per-Tenant Hudu mapping).

## What happens to deleted Nautobot records?

Default behavior: they're archived in Hudu (recoverable via the Hudu UI). With `hard_delete=True`, they're permanently deleted. Archive is the safer default.

Note: if a Nautobot Tenant is deleted, the Hudu Company will be archived. All its child Assets, Networks, IPs, etc. become orphans in Hudu — operators may want to manually clean those up, or use `hard_delete` and accept the cascade.

## How fast is the sync?

For a small fleet (~50 devices, ~100 IPs), a full sync takes 5-15 seconds. Hudu's API is the bottleneck; the plugin makes one HTTPS call per record and Hudu doesn't bulk-create. For large environments (thousands of records), expect proportional scaling.

## Does it work with Hudu Cloud?

Should — the API is the same as self-hosted. Not currently part of the test matrix, but no Hudu-Cloud-specific gotchas have been reported.
