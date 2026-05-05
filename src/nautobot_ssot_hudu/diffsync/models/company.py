"""Company model: maps Nautobot Tenant <-> Hudu Company."""

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
