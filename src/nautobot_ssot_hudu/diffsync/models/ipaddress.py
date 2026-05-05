"""IPAddress model: maps Nautobot IPAddress <-> Hudu IPAddress."""

import ipaddress as ipa

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class IPAddress(HuduSSoTModel):
    """A Nautobot IPAddress / Hudu IPAddress.

    Identity is (company_name, address) where address is just the IP host
    string (no mask). Hudu IPs are implicitly scoped per-company through
    their parent Network, so per-company uniqueness is the natural identity.

    asset_name links the IP to a Hudu Asset (Device). Stored as a name,
    not pk, for diff stability across asset recreation. None when the IP
    isn't assigned to any device interface.
    """

    _modelname = "ipaddress"
    _identifiers = ("company_name", "address")
    _attributes = ("dns_name", "description", "asset_name")

    company_name: str
    address: str
    dns_name: str | None = None
    description: str | None = None
    asset_name: str | None = None


class HuduIPAddress(IPAddress):
    """Hudu-side IPAddress with CRUD via /api/v1/ip_addresses.

    The Hudu API requires `network_id` at create time but does NOT return
    it in the response. We resolve it on the fly inside create() by checking
    which loaded HuduNetwork's CIDR contains this IP — relies on the
    top_level ordering placing 'network' before 'ipaddress' so all networks
    exist by the time we create IPs.
    """

    pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create an IPAddress in Hudu under the right Company + Network."""
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(
                f"Cannot create ipaddress {ids['address']!r} in {ids['company_name']!r}: "
                "parent Hudu Company has no pk."
            )
        network_id = cls._resolve_network_id(adapter, ids["company_name"], ids["address"])
        if network_id is None:
            raise RuntimeError(
                f"No Hudu Network in {ids['company_name']!r} contains "
                f"{ids['address']!r} — create a containing Prefix in Nautobot first."
            )
        payload = {
            "company_id": company.pk,
            "network_id": network_id,
            "address": ids["address"],
            "fqdn": attrs.get("dns_name") or "",
            "description": attrs.get("description") or "",
            # Trust the operator's FQDN values; don't try to DNS-resolve them
            # from Hudu's network (which often can't reach internal hostnames).
            "skip_dns_validation": True,
        }
        # Optional Asset linkage: makes the IP appear on the device's page in
        # Hudu and vice versa. Resolved by name at write time so the link
        # survives pk changes from delete-and-recreate.
        asset_name = attrs.get("asset_name")
        if asset_name:
            asset_pk = cls._lookup_asset_pk(adapter, ids["company_name"], asset_name)
            if asset_pk is not None:
                payload["asset_id"] = asset_pk
        created = adapter.client.ip_addresses.create(payload=payload)
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    @staticmethod
    def _lookup_asset_pk(adapter, company_name: str, asset_name: str) -> int | None:
        """Find a loaded HuduDevice by (company, name) and return its pk."""
        for d in adapter.get_all("device"):
            if d.company_name == company_name and d.name == asset_name:
                return d.pk
        return None

    @staticmethod
    def _resolve_network_id(adapter, company_name: str, ip_str: str) -> int | None:
        """Find the loaded HuduNetwork in this company that contains this IP.

        Returns the network's pk, or None if no containing network is loaded.
        Skips network records with malformed addresses defensively.
        """
        try:
            target = ipa.ip_address(ip_str)
        except ValueError:
            return None
        for net in adapter.get_all("network"):
            if net.company_name != company_name or net.pk is None:
                continue
            try:
                if target in ipa.ip_network(net.address, strict=False):
                    return net.pk
            except ValueError:
                continue
        return None

    def update(self, attrs):
        """Apply changed attrs to the Hudu IPAddress identified by self.pk."""
        payload: dict = {"skip_dns_validation": True}
        if "dns_name" in attrs:
            payload["fqdn"] = attrs["dns_name"] or ""
        if "description" in attrs:
            payload["description"] = attrs["description"] or ""
        if "asset_name" in attrs:
            new_asset_name = attrs["asset_name"]
            if new_asset_name:
                asset_pk = self._lookup_asset_pk(
                    self.adapter, self.company_name, new_asset_name
                )
                # If the asset can't be found, send None (clears the linkage)
                # rather than silently keeping the old pk — diff said this
                # IP should point at <asset_name>, so honor that intent.
                payload["asset_id"] = asset_pk
            else:
                payload["asset_id"] = None
        if len(payload) > 1:  # more than just the skip flag
            # hudu-magic's resource validator rejects update on IP_ADDRESSES
            # ("does not support update") even though the API supports PUT.
            # Same workaround as Networks: bypass via the underlying client.
            self.adapter.client.put(
                f"ip_addresses/{self.pk}",
                json={"ip_address": payload},
            )
        return super().update(attrs)

    def delete(self):
        """Delete the Hudu IPAddress (no archive concept on this entity)."""
        # Unlike companies/assets/networks, Hudu's IPAddress has discarded_at
        # in the model but no archive() helper in hudu-magic. Direct delete.
        self.adapter.client.ip_addresses.delete(self.pk)
        return super().delete()
