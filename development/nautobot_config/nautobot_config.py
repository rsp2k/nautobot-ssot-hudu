"""Nautobot config for the SSoT-Hudu dev stack.

Loaded via volume mount at /opt/nautobot/nautobot_config.py inside each
Nautobot container. Imports the upstream defaults, then overrides only
what we need: PLUGINS, PLUGINS_CONFIG, and a couple of dev toggles.
"""

import os

# Pull in Nautobot's default settings (DB/cache/Celery wiring from env vars).
from nautobot.core.settings import *  # noqa: F401,F403
from nautobot.core.settings_funcs import is_truthy  # noqa: F401

DEBUG = is_truthy(os.environ.get("NAUTOBOT_DEBUG", "true"))

PLUGINS = [
    "nautobot_ssot",
    "nautobot_ssot_hudu",
]

PLUGINS_CONFIG = {
    "nautobot_ssot": {
        # Hide the example DataSource job from the dashboard once we have ours wired up.
        "hide_example_jobs": False,
    },
    "nautobot_ssot_hudu": {
        "instance_url": os.environ.get("HUDU_INSTANCE_URL", ""),
        "secret_group_name": "Hudu Credentials",
        "asset_layouts": {
            # Hudu asset_layout_id under which Nautobot Devices are synced.
            # Unset → device sync is skipped (Companies still sync).
            "device": int(os.environ["HUDU_DEVICE_LAYOUT_ID"])
            if os.environ.get("HUDU_DEVICE_LAYOUT_ID")
            else None,
        },
        # device_field_map: keys are Hudu custom-field labels (must exist on
        # the device asset_layout); values are dotted attribute paths on the
        # Nautobot Device. Resolved with safe None-propagation: a missing
        # primary_ip4 yields None for "Management IP" rather than crashing.
        "device_field_map": {
            "Hostname": "name",
            "Management IP": "primary_ip4.host",
            "Model": "device_type.model",
            "Serial": "serial",
            "Status": "status.name",
            "Location": "location.name",
        },
    },
}
