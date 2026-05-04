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
            # Filled in once we know the Hudu instance's layout IDs.
        },
    },
}
