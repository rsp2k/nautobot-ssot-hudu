"""Company model: maps Nautobot Tenant <-> Hudu Company."""

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class Company(HuduSSoTModel):
    """A Hudu Company / Nautobot Tenant."""

    _modelname = "company"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: str | None = None
