"""RackItem model: maps Nautobot Device-in-Rack <-> Hudu RackStorageItem.

This isn't an entity in Nautobot — it's the rack/position/face fields on a
Device that *together* describe its physical placement. We model the
relationship explicitly because Hudu represents it as a separate API
resource (``/api/v1/rack_storage_items``) rather than as fields on the
Asset itself.
"""

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class RackItem(HuduSSoTModel):
    """A Device's physical placement within a Rack.

    Identity is (company_name, asset_name) — each Asset can be in at most
    one rack at one position, so the asset name uniquely identifies the
    placement within a company.
    """

    _modelname = "rackitem"
    _identifiers = ("company_name", "asset_name")
    _attributes = ("rack_name", "start_unit", "end_unit", "side")

    company_name: str
    asset_name: str
    rack_name: str
    start_unit: int
    end_unit: int
    side: str = "front"


class HuduRackItem(RackItem):
    """Hudu-side RackItem: linked Asset+Rack record at a specific U range."""

    pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create a rack_storage_item linking a Hudu Asset to a Hudu Rack.

        Resolves both Asset.pk and Rack.pk by walking the adapter's already-
        loaded HuduDevice and HuduRack records. top_level=(..., "device",
        ..., "rack", "rackitem") guarantees both exist by the time we
        process rack items.
        """
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(
                f"Cannot create rackitem for {ids['asset_name']!r}: "
                f"parent Hudu Company {ids['company_name']!r} has no pk."
            )
        asset_pk = cls._lookup_asset_pk(adapter, ids["company_name"], ids["asset_name"])
        if asset_pk is None:
            raise RuntimeError(
                f"Cannot create rackitem: Hudu Asset {ids['asset_name']!r} in "
                f"{ids['company_name']!r} not loaded (was the device synced?)."
            )
        rack_pk = cls._lookup_rack_pk(adapter, ids["company_name"], attrs["rack_name"])
        if rack_pk is None:
            raise RuntimeError(
                f"Cannot create rackitem: Hudu Rack {attrs['rack_name']!r} in "
                f"{ids['company_name']!r} not loaded (was the rack synced?)."
            )
        # hudu-magic's resource-level validation for rack_storage_items
        # expects the payload wrapped in a single 'rack_storage_item' key,
        # unlike the networks endpoint which accepts top-level fields.
        # Library inconsistency, not an API one — both worked fine via raw curl.
        payload = {
            "rack_storage_item": {
                "rack_storage_id": rack_pk,
                "asset_id": asset_pk,
                "start_unit": attrs["start_unit"],
                "end_unit": attrs["end_unit"],
                "side": attrs.get("side") or "front",
            },
        }
        created = adapter.client.rack_storage_items.create(payload=payload)
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    @staticmethod
    def _lookup_asset_pk(adapter, company_name: str, asset_name: str) -> int | None:
        for d in adapter.get_all("device"):
            if d.company_name == company_name and d.name == asset_name:
                return d.pk
        return None

    @staticmethod
    def _lookup_rack_pk(adapter, company_name: str, rack_name: str) -> int | None:
        for r in adapter.get_all("rack"):
            if r.company_name == company_name and r.name == rack_name:
                return r.pk
        return None

    def update(self, attrs):
        """Apply changed attrs (position/side/rack) to the rack_storage_item."""
        payload: dict = {}
        if "start_unit" in attrs:
            payload["start_unit"] = attrs["start_unit"]
        if "end_unit" in attrs:
            payload["end_unit"] = attrs["end_unit"]
        if "side" in attrs:
            payload["side"] = attrs["side"] or "front"
        if "rack_name" in attrs:
            new_rack_pk = self._lookup_rack_pk(
                self.adapter, self.company_name, attrs["rack_name"]
            )
            if new_rack_pk is None:
                raise RuntimeError(
                    f"Cannot move rackitem {self.asset_name!r} to rack "
                    f"{attrs['rack_name']!r}: target rack not loaded."
                )
            payload["rack_storage_id"] = new_rack_pk
        if payload:
            self.adapter.client.rack_storage_items.update(
                self.pk, payload={"rack_storage_item": payload}
            )
        return super().update(attrs)

    def delete(self):
        """Delete the rack placement (unmounts the asset from the rack)."""
        self.adapter.client.rack_storage_items.delete(self.pk)
        return super().delete()
