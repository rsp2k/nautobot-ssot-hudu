"""Rack model: maps Nautobot Rack <-> Hudu RackStorage."""

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class Rack(HuduSSoTModel):
    """A Nautobot Rack / Hudu RackStorage.

    Identity is (company_name, name) because Hudu rack names are scoped
    per-company. Hudu calls these "rack_storages" in its API but the UI
    label is "Racks" — we use Rack to match Nautobot's terminology.
    """

    _modelname = "rack"
    _identifiers = ("company_name", "name")
    _attributes = (
        "height",
        "width",
        "serial",
        "asset_tag",
        "description",
        "descending_units",
    )

    company_name: str
    name: str
    height: int = 42
    width: int = 19
    serial: str | None = None
    asset_tag: str | None = None
    description: str | None = None
    descending_units: bool = False


class HuduRack(Rack):
    """Hudu-side Rack with CRUD via /api/v1/rack_storages.

    Note the API endpoint name is rack_storages (with the noun "storage"),
    not racks — Hudu's terminology, hudu-magic exposes it as
    ``client.rack_storages``.
    """

    pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create a Rack in Hudu under the right Company."""
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(
                f"Cannot create rack {ids['name']!r} in {ids['company_name']!r}: "
                "parent Hudu Company has no pk."
            )
        payload = {
            "company_id": company.pk,
            "name": ids["name"],
            "height": attrs.get("height") or 42,
            "width": attrs.get("width") or 19,
            "starting_unit": 1,
            "descending_units": attrs.get("descending_units", False),
            "serial_number": attrs.get("serial") or "",
            "asset_tag": attrs.get("asset_tag") or "",
            "description": attrs.get("description") or "",
        }
        created = adapter.client.rack_storages.create(payload=payload)
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    def update(self, attrs):
        """Apply changed attrs to the Hudu RackStorage identified by self.pk."""
        # Hudu's PUT semantics for rack_storages support partial updates.
        payload: dict = {}
        if "height" in attrs:
            payload["height"] = attrs["height"] or 42
        if "width" in attrs:
            payload["width"] = attrs["width"] or 19
        if "serial" in attrs:
            payload["serial_number"] = attrs["serial"] or ""
        if "asset_tag" in attrs:
            payload["asset_tag"] = attrs["asset_tag"] or ""
        if "description" in attrs:
            payload["description"] = attrs["description"] or ""
        if "descending_units" in attrs:
            payload["descending_units"] = attrs["descending_units"]
        if payload:
            self.adapter.client.rack_storages.update(self.pk, payload=payload)
        return super().update(attrs)

    def delete(self):
        """Delete the Hudu RackStorage."""
        # rack_storages doesn't appear to support archive in the API; direct delete.
        self.adapter.client.rack_storages.delete(self.pk)
        return super().delete()
