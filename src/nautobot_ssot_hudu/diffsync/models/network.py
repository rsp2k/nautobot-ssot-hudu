"""Network model: maps Nautobot Prefix <-> Hudu Network."""

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class Network(HuduSSoTModel):
    """A Nautobot Prefix / Hudu Network.

    Identity is (company_name, address) because Hudu Networks are scoped
    per-company (you can have 10.0.0.0/24 in two different companies).
    Address is the CIDR string ("10.0.0.0/24").
    """

    _modelname = "network"
    _identifiers = ("company_name", "address")
    _attributes = ("name", "description")

    company_name: str
    address: str
    name: str | None = None
    description: str | None = None


class HuduNetwork(Network):
    """Hudu-side Network with CRUD methods that call the Hudu API.

    Unlike Assets, Hudu Networks live at /api/v1/networks (top-level) with
    company_id passed in the body — not under /api/v1/companies/<cid>/...
    so the create/update calls don't need company_pk separately.
    """

    pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create a Network in Hudu under the right Company."""
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(
                f"Cannot create network {ids['address']!r} in {ids['company_name']!r}: "
                "parent Hudu Company has no pk."
            )
        payload = {
            "company_id": company.pk,
            "address": ids["address"],
            "name": attrs.get("name") or ids["address"],
            "description": attrs.get("description") or "",
        }
        created = adapter.client.networks.create(payload=payload)
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    def update(self, attrs):
        """Apply changed attrs to the Hudu Network identified by self.pk."""
        payload: dict = {}
        if "name" in attrs:
            payload["name"] = attrs["name"] or self.address
        if "description" in attrs:
            payload["description"] = attrs["description"] or ""
        if payload:
            self.adapter.client.networks.update(self.pk, payload=payload)
        return super().update(attrs)

    def delete(self):
        """Archive (default) or hard-delete the Hudu Network."""
        network = self.adapter.client.networks.get(id=self.pk)
        if getattr(self.adapter, "hard_delete", False):
            network.delete()
        else:
            # Hudu Networks support archive too (archived_at field on the model).
            network.archive()
        return super().delete()
