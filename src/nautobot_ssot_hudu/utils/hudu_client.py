"""Build a configured ``hudu_magic.HuduClient`` from Nautobot settings + Secrets."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from hudu_magic import HuduClient
from nautobot.extras.choices import (
    SecretsGroupAccessTypeChoices,
    SecretsGroupSecretTypeChoices,
)
from nautobot.extras.models import SecretsGroup

PLUGIN_NAME = "nautobot_ssot_hudu"


def get_plugin_settings() -> dict:
    """Return this plugin's PLUGINS_CONFIG block."""
    return settings.PLUGINS_CONFIG.get(PLUGIN_NAME, {})


def build_client() -> HuduClient:
    """Construct an authenticated HuduClient.

    The instance URL comes from PLUGINS_CONFIG; the API key is resolved from a
    Nautobot SecretsGroup at call time so credentials never live in config files.

    Raises:
        ImproperlyConfigured: if ``instance_url`` or ``secret_group_name`` is
            missing, or the named SecretsGroup does not exist.
    """
    cfg = get_plugin_settings()

    instance_url = cfg.get("instance_url")
    if not instance_url:
        raise ImproperlyConfigured(
            f"{PLUGIN_NAME}: 'instance_url' is required in PLUGINS_CONFIG"
        )

    secret_group_name = cfg.get("secret_group_name")
    if not secret_group_name:
        raise ImproperlyConfigured(
            f"{PLUGIN_NAME}: 'secret_group_name' is required in PLUGINS_CONFIG"
        )

    try:
        group = SecretsGroup.objects.get(name=secret_group_name)
    except SecretsGroup.DoesNotExist as exc:
        raise ImproperlyConfigured(
            f"{PLUGIN_NAME}: SecretsGroup '{secret_group_name}' not found"
        ) from exc

    api_key = group.get_secret_value(
        SecretsGroupAccessTypeChoices.TYPE_HTTP,
        SecretsGroupSecretTypeChoices.TYPE_TOKEN,
    )

    return HuduClient(api_key=api_key, instance_url=instance_url)
