# Uninstalling the App

The plugin doesn't add any Django models to Nautobot's database — all sync state lives in the SSoT framework's `Sync` records, which belong to `nautobot-app-ssot` itself. Removing this plugin doesn't lose Nautobot data; the records that were *pushed to Hudu* remain in Hudu untouched.

## Standard uninstall

```shell
# Disable the app first
$EDITOR /opt/nautobot/nautobot_config.py
# Remove "nautobot_ssot_hudu" from PLUGINS and the corresponding entry from PLUGINS_CONFIG

sudo systemctl restart nautobot nautobot-worker nautobot-scheduler

# Then uninstall the package
pip uninstall nautobot-ssot-hudu

# (Optional) Remove from local_requirements.txt:
sed -i '/^nautobot-ssot-hudu$/d' /opt/nautobot/local_requirements.txt
```

## What's left behind

- **The SecretsGroup** (e.g. "Hudu Credentials") and its Secret remain. Delete via Nautobot UI if no longer needed.
- **Existing Sync records** in `nautobot-app-ssot`'s history remain searchable in **Apps → Single Source of Truth → Sync History**. The Job is gone, so they can't be re-run, but the diff/log records persist for audit purposes.
- **Hudu data** is unaffected — uninstalling this plugin doesn't touch Hudu. Data created by previous syncs stays in Hudu.

## What's removed

- The "Hudu" Data Target entry from the SSoT Dashboard
- The Job (`nautobot_ssot_hudu.jobs.HuduDataTarget`) — its DB row is removed automatically by `post_upgrade` after the package is uninstalled
- All `nautobot_ssot_hudu.*` Python imports
