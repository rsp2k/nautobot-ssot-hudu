"""Build a configured ``hudu_magic.HuduClient`` from Nautobot settings + Secrets."""

from django.conf import settings

PLUGIN_NAME = "nautobot_ssot_hudu"


def get_plugin_settings() -> dict:
    """Return this plugin's PLUGINS_CONFIG block, with defaults applied."""
    return settings.PLUGINS_CONFIG.get(PLUGIN_NAME, {})


def build_client():
    """Construct an authenticated HuduClient.

    The instance URL comes from PLUGINS_CONFIG, while the API key is resolved
    from a Nautobot Secrets Group at call time so we never pin credentials in
    config files.
    """
    raise NotImplementedError
