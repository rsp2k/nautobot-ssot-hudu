"""Schema tests for the DiffSync model classes.

These guard against accidental edits to identifiers/attributes/inheritance
that would silently break diffing or CRUD targeting. They run against the
real model definitions but stub out Nautobot framework imports (see
``conftest.py``), so they need only ``diffsync`` and ``pytest`` installed.
"""

import pytest
from pydantic import ValidationError

from nautobot_ssot_hudu.diffsync.models.company import (
    Company,
    Device,
    HuduCompany,
    HuduDevice,
)


class TestCompany:
    """The shared Company model used by both adapters for matching/diffing."""

    def test_modelname(self) -> None:
        assert Company._modelname == "company"

    def test_identifiers_is_name_only(self) -> None:
        # Renaming or expanding identifiers would change how records match
        # across the two adapters — every sync would suddenly create-vs-update
        # incorrectly.
        assert Company._identifiers == ("name",)

    def test_attributes_is_description_only(self) -> None:
        # Adding fields here without updating both adapters' load() methods
        # would emit spurious diffs forever.
        assert Company._attributes == ("description",)

    def test_construction_with_minimal_fields(self) -> None:
        c = Company(name="Acme")
        assert c.name == "Acme"
        assert c.description is None

    def test_construction_with_full_fields(self) -> None:
        c = Company(name="Acme", description="Roadrunner-tracking.")
        assert c.name == "Acme"
        assert c.description == "Roadrunner-tracking."

    def test_construction_rejects_missing_name(self) -> None:
        with pytest.raises(ValidationError):
            Company()


class TestHuduCompany:
    """Hudu-side variant: same schema as Company plus a ``pk`` field for CRUD."""

    def test_inherits_from_company(self) -> None:
        assert issubclass(HuduCompany, Company)

    def test_keeps_company_identifiers(self) -> None:
        # If HuduCompany ever overrode _identifiers, the diff would match
        # records by a different key on the two sides — chaos.
        assert HuduCompany._identifiers == Company._identifiers

    def test_keeps_company_attributes(self) -> None:
        # Same: shared _attributes guarantees the diff compares the same fields.
        assert HuduCompany._attributes == Company._attributes

    def test_pk_field_is_optional_int(self) -> None:
        # pk gets populated at create or load time. Must accept None for
        # the brief window between Nautobot-side instantiation and Hudu create.
        instance = HuduCompany(name="Acme")
        assert instance.pk is None

        instance_with_pk = HuduCompany(name="Acme", pk=42)
        assert instance_with_pk.pk == 42

    def test_pk_is_not_in_attributes(self) -> None:
        # CRITICAL: pk being in _attributes would mean DiffSync compares it
        # across sides. Nautobot doesn't have a Hudu pk → diff would always
        # report an update, every sync, forever.
        assert "pk" not in HuduCompany._attributes

    def test_crud_methods_exist(self) -> None:
        # The whole point of HuduCompany is overriding these.
        assert hasattr(HuduCompany, "create")
        assert hasattr(HuduCompany, "update")
        assert hasattr(HuduCompany, "delete")


class TestDevice:
    """Device model — Hudu Asset names are company-scoped, not globally unique."""

    def test_modelname(self) -> None:
        assert Device._modelname == "device"

    def test_identifiers_is_composite(self) -> None:
        # CRITICAL: Hudu Asset names are unique within company, not globally.
        # Identity must be the (company_name, name) tuple, otherwise two
        # different Hudu instances of "edge-router-01" in different companies
        # would clobber each other in the diff.
        assert Device._identifiers == ("company_name", "name")

    def test_attributes(self) -> None:
        assert Device._attributes == ("description",)

    def test_construction_requires_company_and_name(self) -> None:
        with pytest.raises(ValidationError):
            Device(name="edge-router-01")  # missing company_name
        with pytest.raises(ValidationError):
            Device(company_name="Acme")  # missing name

    def test_construction_with_full_fields(self) -> None:
        d = Device(company_name="Acme", name="edge-router-01", description="Edge router.")
        assert d.company_name == "Acme"
        assert d.name == "edge-router-01"
        assert d.description == "Edge router."


class TestHuduDevice:
    """Hudu-side Device variant: same schema + pk + CRUD."""

    def test_inherits_from_device(self) -> None:
        assert issubclass(HuduDevice, Device)

    def test_keeps_device_identifiers(self) -> None:
        assert HuduDevice._identifiers == Device._identifiers

    def test_keeps_device_attributes(self) -> None:
        assert HuduDevice._attributes == Device._attributes

    def test_pk_is_optional_int_not_in_attributes(self) -> None:
        instance = HuduDevice(company_name="Acme", name="edge-01")
        assert instance.pk is None
        assert "pk" not in HuduDevice._attributes

    def test_crud_methods_exist(self) -> None:
        assert hasattr(HuduDevice, "create")
        assert hasattr(HuduDevice, "update")
        assert hasattr(HuduDevice, "delete")
