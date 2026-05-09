# Installing the App in Nautobot

This page covers **install** and **configure** for `nautobot-ssot-hudu` in your Nautobot environment.

## Prerequisites

- Nautobot 3.0+, Python 3.10+
- [`nautobot-app-ssot`](https://github.com/nautobot/nautobot-app-ssot) 4.2+
- A Hudu instance you have admin access to (cloud or self-hosted)
- A Nautobot SecretsGroup configured with the Hudu API key (see below)

!!! note
    See the [compatibility matrix](compatibility_matrix.md) for the full version matrix.

### Access Requirements

- Nautobot needs outbound HTTPS to your Hudu instance.
- The Hudu API key must have **Full access** scope. **Delete data** permission is required only if you plan to use `hard_delete=True`. **View passwords** and **Export data** can stay off — the plugin doesn't use them.

## Install Guide

The app is available on PyPI:

```shell
pip install nautobot-ssot-hudu
```

To make sure the app is reinstalled on every Nautobot upgrade, append it to `local_requirements.txt`:

```shell
echo nautobot-ssot-hudu >> local_requirements.txt
```

Once installed, enable the app in `nautobot_config.py`:

```python
PLUGINS = [
    "nautobot_ssot",         # required dependency
    "nautobot_ssot_hudu",
]

PLUGINS_CONFIG = {
    "nautobot_ssot_hudu": {
        "instance_url": "https://yourcompany.huducloud.com",
        "secret_group_name": "Hudu Credentials",
        "asset_layouts": {
            "device": 1,                    # default Hudu asset_layout_id
            "device_by_role": {              # optional per-Nautobot-Role overrides
                "firewall": 2,
            },
        },
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

Then run post-upgrade and restart Nautobot:

```shell
nautobot-server post_upgrade
sudo systemctl restart nautobot nautobot-worker nautobot-scheduler
```

## App Configuration

### Hudu side (one-time)

Before the first sync runs, set up Hudu:

1. **Create the asset_layout(s)** for Devices. Hudu doesn't ship a built-in "Device" layout. Each layout's custom fields must have labels matching the keys in `device_field_map` (e.g. "Hostname", "Management IP", etc.).
2. **Generate an API key** in Hudu (Admin → API Keys → New API Key).
3. **Note the layout IDs** from Admin → Asset Layouts and wire them into `PLUGINS_CONFIG["asset_layouts"]`.

### Nautobot side

Create a Nautobot SecretsGroup named `Hudu Credentials` (or whatever name you used in `secret_group_name`) containing one Secret:

- Access type: **HTTP**
- Secret type: **Token**
- Provider: any (environment-variable, file, Vault, etc.) — the plugin reads the value at sync time

The token must be the Hudu API key from step 2 above.

### PLUGINS_CONFIG keys

| Key | Required | Description |
|---|---|---|
| `instance_url` | yes | Base URL of your Hudu instance (no trailing slash) |
| `secret_group_name` | yes | Name of the Nautobot SecretsGroup containing the Hudu API token |
| `asset_layouts.device` | no | Default Hudu asset_layout_id used for Device→Asset sync. If unset and no role-override matches, the device is skipped. |
| `asset_layouts.device_by_role` | no | Map of Nautobot role name → Hudu asset_layout_id. Used to route different DeviceRoles to different Hudu layouts. |
| `device_field_map` | no | Map of Hudu custom-field label → Nautobot Device dotted-attribute path. Resolves at sync time with safe None-propagation. |
