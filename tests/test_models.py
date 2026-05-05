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
    HuduNetwork,
    Network,
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
        # field_values is the dict of Hudu custom-field label -> value pairs;
        # both adapters populate it from the operator-configured field_map.
        assert Device._attributes == ("field_values",)

    def test_construction_requires_company_and_name(self) -> None:
        with pytest.raises(ValidationError):
            Device(name="edge-router-01")  # missing company_name
        with pytest.raises(ValidationError):
            Device(company_name="Acme")  # missing name

    def test_field_values_defaults_to_empty_dict(self) -> None:
        d = Device(company_name="Acme", name="edge-01")
        assert d.field_values == {}

    def test_field_values_accepts_label_value_dict(self) -> None:
        d = Device(
            company_name="Acme",
            name="edge-01",
            field_values={
                "Hostname": "edge-01.acme.lan",
                "Management IP": "10.0.0.1",
                "Serial": None,  # null is allowed for unset fields
            },
        )
        assert d.field_values["Hostname"] == "edge-01.acme.lan"
        assert d.field_values["Management IP"] == "10.0.0.1"
        assert d.field_values["Serial"] is None

    def test_field_values_dict_equality_is_order_independent(self) -> None:
        # CRITICAL: DiffSync compares attributes with ==, and Python dict
        # equality is set-of-(k,v) — order-independent. If this ever stopped
        # being true (e.g. someone changed field_values to a list of tuples)
        # the diff would emit spurious updates whenever the load order shifted.
        a = Device(company_name="Acme", name="x", field_values={"A": "1", "B": "2"})
        b = Device(company_name="Acme", name="x", field_values={"B": "2", "A": "1"})
        assert a.field_values == b.field_values


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

    def test_company_pk_is_optional_int_not_in_attributes(self) -> None:
        # company_pk is captured at load time and used by update() to hit the
        # per-company Hudu endpoint. Like pk, it's metadata and must not be
        # part of the diff — otherwise a Hudu Company id renumbering would
        # show every device as needing update.
        instance = HuduDevice(company_name="Acme", name="edge-01")
        assert instance.company_pk is None
        assert "company_pk" not in HuduDevice._attributes

    def test_crud_methods_exist(self) -> None:
        assert hasattr(HuduDevice, "create")
        assert hasattr(HuduDevice, "update")
        assert hasattr(HuduDevice, "delete")


class TestNetwork:
    """Network model — Hudu Networks are CIDR blocks scoped per-company."""

    def test_modelname(self) -> None:
        assert Network._modelname == "network"

    def test_identifiers_is_company_and_address(self) -> None:
        # Hudu allows the same CIDR (e.g. 10.0.0.0/24) in multiple companies,
        # so identity must be composite to match across both adapters correctly.
        assert Network._identifiers == ("company_name", "address")

    def test_attributes(self) -> None:
        assert Network._attributes == ("name", "description")

    def test_construction_requires_company_and_address(self) -> None:
        with pytest.raises(ValidationError):
            Network(address="10.0.0.0/24")  # missing company_name
        with pytest.raises(ValidationError):
            Network(company_name="Acme")  # missing address

    def test_construction_with_full_fields(self) -> None:
        n = Network(
            company_name="Acme",
            address="10.0.0.0/24",
            name="LAN",
            description="Office LAN.",
        )
        assert n.company_name == "Acme"
        assert n.address == "10.0.0.0/24"
        assert n.name == "LAN"
        assert n.description == "Office LAN."


class TestHuduNetwork:
    """Hudu-side Network variant: same schema + pk + CRUD."""

    def test_inherits_from_network(self) -> None:
        assert issubclass(HuduNetwork, Network)

    def test_keeps_identifiers_and_attributes(self) -> None:
        assert HuduNetwork._identifiers == Network._identifiers
        assert HuduNetwork._attributes == Network._attributes

    def test_pk_is_optional_and_not_in_attributes(self) -> None:
        instance = HuduNetwork(company_name="Acme", address="10.0.0.0/24")
        assert instance.pk is None
        assert "pk" not in HuduNetwork._attributes

    def test_crud_methods_exist(self) -> None:
        assert hasattr(HuduNetwork, "create")
        assert hasattr(HuduNetwork, "update")
        assert hasattr(HuduNetwork, "delete")


class TestCustomFieldsHelpers:
    """Helpers that translate between our field_values dict and Hudu's API format."""

    def test_label_to_field_key_lowercases_and_underscores(self) -> None:
        from nautobot_ssot_hudu.diffsync.models.company import _label_to_field_key

        assert _label_to_field_key("Hostname") == "hostname"
        assert _label_to_field_key("Management IP") == "management_ip"
        assert _label_to_field_key("Serial Number") == "serial_number"

    def test_build_custom_fields_payload_includes_none_values(self) -> None:
        # CRITICAL: None must be included so the diff can explicitly clear a
        # field. Omitting it would let Hudu retain the previous value, and
        # the diff would loop forever wanting to set it to None.
        from nautobot_ssot_hudu.diffsync.models.company import (
            _build_custom_fields_payload,
        )

        payload = _build_custom_fields_payload(
            {"Hostname": "edge-01", "Serial": None},
        )
        assert payload == [{"hostname": "edge-01"}, {"serial": None}]
