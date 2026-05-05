"""VLAN model: maps Nautobot VLAN <-> Hudu VLAN."""

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class VLAN(HuduSSoTModel):
    """A Nautobot VLAN / Hudu VLAN.

    Identity is (company_name, vid) because two companies can each have
    their own VLAN 100 (management) without collision. ``vid`` is the
    802.1Q VLAN identifier (1-4094); Hudu calls the same field ``vlan_id``.
    """

    _modelname = "vlan"
    _identifiers = ("company_name", "vid")
    _attributes = ("name", "description")

    company_name: str
    vid: int
    name: str | None = None
    description: str | None = None


class HuduVLAN(VLAN):
    """Hudu-side VLAN with CRUD via /api/v1/vlans."""

    pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create a VLAN in Hudu under the right Company."""
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(
                f"Cannot create vlan {ids['vid']} in {ids['company_name']!r}: "
                "parent Hudu Company has no pk."
            )
        payload = {
            "company_id": company.pk,
            "vlan_id": ids["vid"],
            "name": attrs.get("name") or f"VLAN {ids['vid']}",
            "description": attrs.get("description") or "",
        }
        created = adapter.client.vlans.create(payload=payload)
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    def update(self, attrs):
        """Apply changed attrs to the Hudu VLAN identified by self.pk."""
        payload: dict = {}
        if "name" in attrs:
            payload["name"] = attrs["name"] or f"VLAN {self.vid}"
        if "description" in attrs:
            payload["description"] = attrs["description"] or ""
        if payload:
            self.adapter.client.vlans.update(self.pk, payload=payload)
        return super().update(attrs)

    def delete(self):
        """Archive (default) or hard-delete the Hudu VLAN."""
        vlan = self.adapter.client.vlans.get(id=self.pk)
        if getattr(self.adapter, "hard_delete", False):
            vlan.delete()
        else:
            vlan.archive()
        return super().delete()
