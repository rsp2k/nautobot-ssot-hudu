"""Company and Device DiffSync models."""

from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel


class Company(HuduSSoTModel):
    """A Hudu Company / Nautobot Tenant. Read-only; used by both adapters for diffing."""

    _modelname = "company"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: str | None = None


class HuduCompany(Company):
    """Hudu-side variant with CRUD methods that call the Hudu API.

    Only HuduAdapter uses this subclass. Keeping CRUD off the base Company
    enforces direction at the type level: NautobotAdapter literally cannot
    write because its model class has no create/update/delete.
    """

    # Hudu's primary key, captured at load or create time. Outside _attributes
    # so DiffSync ignores it for diffing — it's metadata, not syncable state.
    pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create a Company in Hudu via hudu-magic and capture its new id."""
        created = adapter.client.companies.create(
            name=ids["name"],
            notes=attrs.get("description") or "",
        )
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    def update(self, attrs):
        """Apply changed attrs to the Hudu Company identified by self.pk."""
        company = self.adapter.client.companies.get(id=self.pk)
        if "description" in attrs:
            company.notes = attrs["description"] or ""
        company.save()
        return super().update(attrs)

    def delete(self):
        """Archive (default) or hard-delete the Hudu Company. Behavior set on the adapter."""
        company = self.adapter.client.companies.get(id=self.pk)
        if getattr(self.adapter, "hard_delete", False):
            company.delete()
        else:
            company.archive()
        return super().delete()


def _label_to_field_key(label: str) -> str:
    """Convert a Hudu custom-field label to its API key form.

    Hudu's API accepts custom_fields as ``[{"snake_case_label": "value"}, ...]``.
    The label "Management IP" becomes the key "management_ip" — lowercase, with
    spaces replaced by underscores. Confirmed empirically against Hudu 2.40+.
    """
    return label.lower().replace(" ", "_")


def _build_custom_fields_payload(field_values: dict[str, str | None]) -> list[dict]:
    """Convert our internal {label: value} dict into Hudu's custom_fields list.

    Sends every key — including None values — so the diff is the source of
    truth: if Nautobot says ``None`` and Hudu had a value, we explicitly clear
    it. Omitting keys would be Hudu's "leave it alone" behavior, which would
    let the diff loop forever ("I want None, Hudu still has the old value").
    """
    return [{_label_to_field_key(label): value} for label, value in field_values.items()]


class Device(HuduSSoTModel):
    """A Nautobot Device / Hudu Asset.

    Identity is (company_name, name) because Hudu Asset names are unique
    only within a company, not globally. Both adapters must populate
    company_name from the parent company's name to make the diff line up.

    field_values is a label-keyed dict matching the operator-configured
    device_field_map; both adapters produce the same set of keys (drawn
    from the config), with None for unset values. Dict equality is set-of-
    (k,v) so DiffSync compares it order-independently.

    asset_layout_id is included in _attributes so the diff surfaces layout
    drift — if a Nautobot Device's role is reassigned to a different Hudu
    layout, the diff shows it. Hudu's API doesn't support migrating an
    existing asset between layouts; HuduDevice.update logs and skips.
    """

    _modelname = "device"
    _identifiers = ("company_name", "name")
    _attributes = ("asset_layout_id", "field_values")

    company_name: str
    name: str
    asset_layout_id: int | None = None
    field_values: dict[str, str | None] = {}


class HuduDevice(Device):
    """Hudu-side variant with CRUD methods that call the Hudu API.

    Hudu Assets require an asset_layout_id at create time; we read that from
    the adapter (which gets it from PLUGINS_CONFIG). We also need the parent
    Hudu Company's id, which we resolve via the adapter's already-loaded
    Company records.
    """

    # Hudu's primary key for the asset, captured at load or create time.
    pk: int | None = None
    # The parent Hudu Company's pk, captured at load time. Needed at update/
    # delete time because Hudu's asset endpoints are nested under company.
    company_pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create an Asset in Hudu under the right Company + asset_layout.

        asset_layout_id comes from attrs (NautobotAdapter resolved it from
        the device's role via device_layouts_by_role config). If unset, fall
        back to the adapter-level default — but typically NautobotAdapter
        skips devices it can't resolve, so this fallback is defensive.
        """
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(
                f"Cannot create device {ids['name']!r} in {ids['company_name']!r}: "
                "parent Hudu Company has no pk (was it created in this same sync? "
                "DiffSync ordering should have placed company creation first)."
            )
        layout_id = attrs.get("asset_layout_id") or adapter.device_layout_id
        if layout_id is None:
            raise RuntimeError(
                f"Cannot create device {ids['name']!r}: no asset_layout_id resolved "
                "(device's role isn't in device_layouts_by_role and no default "
                "asset_layouts.device is set)."
            )
        custom_fields = _build_custom_fields_payload(attrs.get("field_values") or {})
        created = adapter.client.assets.create(
            company_id=company.pk,
            name=ids["name"],
            asset_layout_id=layout_id,
            custom_fields=custom_fields,
        )
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        instance.company_pk = company.pk
        return instance

    def update(self, attrs):
        """Apply changed attrs to the Hudu Asset identified by self.pk.

        Hudu's API does NOT support changing an existing asset's layout. If
        the diff says the layout changed, log a warning and skip — operator
        must migrate manually (delete + recreate). field_values updates
        proceed normally.
        """
        if "asset_layout_id" in attrs:
            logger = getattr(getattr(self.adapter, "job", None), "logger", None)
            msg = (
                f"Device {self.company_name!r}/{self.name!r}: layout change "
                f"detected (asset_layout_id) but Hudu does not support migrating "
                f"existing assets between layouts. Skipping. Migrate manually."
            )
            if logger:
                logger.warning(msg)
        if "field_values" in attrs:
            custom_fields = _build_custom_fields_payload(attrs["field_values"])
            self.adapter.client.assets.update(
                self.pk,
                self.company_pk,
                custom_fields=custom_fields,
            )
        return super().update(attrs)

    def delete(self):
        """Archive (default) or hard-delete the Hudu Asset. Behavior set on the adapter."""
        asset = self.adapter.client.assets.get(id=self.pk)
        if getattr(self.adapter, "hard_delete", False):
            asset.delete()
        else:
            asset.archive()
        return super().delete()


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
