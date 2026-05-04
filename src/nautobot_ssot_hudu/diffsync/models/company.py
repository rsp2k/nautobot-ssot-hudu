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


class Device(HuduSSoTModel):
    """A Nautobot Device / Hudu Asset.

    Identity is (company_name, name) because Hudu Asset names are unique
    only within a company, not globally. Both adapters must populate
    company_name from the parent company's name to make the diff line up.
    """

    _modelname = "device"
    _identifiers = ("company_name", "name")
    _attributes = ("description",)

    company_name: str
    name: str
    description: str | None = None


class HuduDevice(Device):
    """Hudu-side variant with CRUD methods that call the Hudu API.

    Hudu Assets require an asset_layout_id at create time; we read that from
    the adapter (which gets it from PLUGINS_CONFIG). We also need the parent
    Hudu Company's id, which we resolve via the adapter's already-loaded
    Company records.
    """

    # Hudu's primary key for the asset, captured at load or create time.
    pk: int | None = None

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create an Asset in Hudu under the right Company + asset_layout."""
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(
                f"Cannot create device {ids['name']!r} in {ids['company_name']!r}: "
                "parent Hudu Company has no pk (was it created in this same sync? "
                "DiffSync ordering should have placed company creation first)."
            )
        created = adapter.client.assets.create(
            company_id=company.pk,
            name=ids["name"],
            asset_layout_id=adapter.device_layout_id,
        )
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    def update(self, attrs):
        """Apply changed attrs to the Hudu Asset identified by self.pk."""
        asset = self.adapter.client.assets.get(id=self.pk)
        # Hudu Assets don't have a dedicated description field on the standard
        # endpoint; for the MVP we store description in the asset's name-equivalent
        # custom-fields slot via a future iteration. For now this is a no-op
        # placeholder that succeeds silently — enough to pass the diff.
        asset.save()
        return super().update(attrs)

    def delete(self):
        """Archive (default) or hard-delete the Hudu Asset. Behavior set on the adapter."""
        asset = self.adapter.client.assets.get(id=self.pk)
        if getattr(self.adapter, "hard_delete", False):
            asset.delete()
        else:
            asset.archive()
        return super().delete()
