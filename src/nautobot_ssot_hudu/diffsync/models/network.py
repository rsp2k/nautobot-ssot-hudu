"""Network model: maps Nautobot Prefix <-> Hudu Network."""

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class Network(HuduSSoTModel):
    """A Nautobot Prefix / Hudu Network.

    Identity is (company_name, address) because Hudu Networks are scoped
    per-company (you can have 10.0.0.0/24 in two different companies).
    Address is the CIDR string ("10.0.0.0/24").

    vlan_vid links the Network to a VLAN by 802.1Q tag (1-4094). Stored
    as the vid (not the Hudu VLAN pk) so the linkage survives Hudu VLAN
    delete/recreate.
    """

    _modelname = "network"
    _identifiers = ("company_name", "address")
    _attributes = ("name", "description", "vlan_vid")

    company_name: str
    address: str
    name: str | None = None
    description: str | None = None
    vlan_vid: int | None = None


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
        # Optional VLAN linkage. Resolved by vid at write time so the link
        # survives Hudu VLAN delete-and-recreate cycles.
        vlan_vid = attrs.get("vlan_vid")
        if vlan_vid is not None:
            vlan_pk = cls._lookup_vlan_pk(adapter, ids["company_name"], vlan_vid)
            if vlan_pk is not None:
                payload["vlan_id"] = vlan_pk
        created = adapter.client.networks.create(payload=payload)
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    @staticmethod
    def _lookup_vlan_pk(adapter, company_name: str, vid: int) -> int | None:
        """Find a loaded HuduVLAN by (company, vid) and return its pk."""
        for v in adapter.get_all("vlan"):
            if v.company_name == company_name and v.vid == vid:
                return v.pk
        return None

    def update(self, attrs):
        """Apply changed attrs to the Hudu Network identified by self.pk."""
        payload: dict = {}
        if "name" in attrs:
            payload["name"] = attrs["name"] or self.address
        if "description" in attrs:
            payload["description"] = attrs["description"] or ""
        if "vlan_vid" in attrs:
            new_vid = attrs["vlan_vid"]
            if new_vid is not None:
                vlan_pk = self._lookup_vlan_pk(
                    self.adapter, self.company_name, new_vid
                )
                payload["vlan_id"] = vlan_pk  # may be None if not found
            else:
                payload["vlan_id"] = None
        if payload:
            # hudu-magic's resource-level validator rejects update on
            # NETWORKS ("does not support update") despite the API supporting
            # PUT just fine (verified by direct curl). Bypass via the
            # underlying client.put method.
            self.adapter.client.put(
                f"networks/{self.pk}",
                json={"network": payload},
            )
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
