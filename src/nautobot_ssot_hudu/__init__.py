"""Nautobot SSoT integration for Hudu."""

from importlib.metadata import PackageNotFoundError, version

from nautobot.apps import NautobotAppConfig

try:
    __version__ = version("nautobot-ssot-hudu")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"


class NautobotSSoTHuduConfig(NautobotAppConfig):
    """App configuration for the Hudu SSoT integration."""

    name = "nautobot_ssot_hudu"
    verbose_name = "Nautobot SSoT Hudu"
    description = "Sync Nautobot data into Hudu (one-way: Nautobot -> Hudu)."
    version = __version__
    author = "Ryan Malloy"
    author_email = "ryan@supported.systems"
    base_url = "ssot-hudu"
    required_settings: list[str] = []
    default_settings: dict = {
        "instance_url": "",
        "secret_group_name": "",
        "asset_layouts": {},
    }
    caching_config: dict = {}


config = NautobotSSoTHuduConfig
