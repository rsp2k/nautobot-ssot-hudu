"""Schema tests for the DiffSync model classes.

These guard against accidental edits to identifiers/attributes/inheritance
that would silently break diffing or CRUD targeting. They run against the
real model definitions but stub out Nautobot framework imports (see
``conftest.py``), so they need only ``diffsync`` and ``pytest`` installed.
"""

import pytest
from pydantic import ValidationError

from nautobot_ssot_hudu.diffsync.models.company import Company, HuduCompany
from nautobot_ssot_hudu.diffsync.models.device import Device, HuduDevice
from nautobot_ssot_hudu.diffsync.models.ipaddress import HuduIPAddress, IPAddress
from nautobot_ssot_hudu.diffsync.models.network import HuduNetwork, Network
from nautobot_ssot_hudu.diffsync.models.rack import HuduRack, Rack
from nautobot_ssot_hudu.diffsync.models.rackitem import HuduRackItem, RackItem
from nautobot_ssot_hudu.diffsync.models.vlan import VLAN, HuduVLAN


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
        # asset_layout_id is in _attributes so the diff surfaces layout drift
        # (Hudu API can't migrate layouts; HuduDevice.update logs and skips).
        # field_values is the per-field label -> value dict (operator-configured).
        assert Device._attributes == ("asset_layout_id", "field_values")

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


class TestIPAddress:
    """IPAddress model — IPs are scoped per-company via their parent Network."""

    def test_modelname(self) -> None:
        assert IPAddress._modelname == "ipaddress"

    def test_identifiers_is_company_and_address(self) -> None:
        assert IPAddress._identifiers == ("company_name", "address")

    def test_attributes(self) -> None:
        assert IPAddress._attributes == ("dns_name", "description")

    def test_construction_requires_company_and_address(self) -> None:
        with pytest.raises(ValidationError):
            IPAddress(address="10.0.0.1")  # missing company_name
        with pytest.raises(ValidationError):
            IPAddress(company_name="Acme")  # missing address

    def test_construction_with_full_fields(self) -> None:
        ip = IPAddress(
            company_name="Acme",
            address="10.0.0.5",
            dns_name="server-01.acme.lan",
            description="Database primary",
        )
        assert ip.company_name == "Acme"
        assert ip.address == "10.0.0.5"
        assert ip.dns_name == "server-01.acme.lan"
        assert ip.description == "Database primary"


class TestHuduIPAddress:
    """Hudu-side IPAddress: same schema + pk + CRUD."""

    def test_inherits_from_ipaddress(self) -> None:
        assert issubclass(HuduIPAddress, IPAddress)

    def test_keeps_identifiers_and_attributes(self) -> None:
        assert HuduIPAddress._identifiers == IPAddress._identifiers
        assert HuduIPAddress._attributes == IPAddress._attributes

    def test_pk_is_optional_and_not_in_attributes(self) -> None:
        instance = HuduIPAddress(company_name="Acme", address="10.0.0.5")
        assert instance.pk is None
        assert "pk" not in HuduIPAddress._attributes

    def test_resolve_network_id_finds_containing_network(self) -> None:
        # The static method that picks the right Hudu Network by IP
        # membership at create time. Critical for proper FK resolution.
        from unittest.mock import MagicMock

        adapter = MagicMock()
        net1 = MagicMock(company_name="Acme", address="10.10.0.0/24", pk=1)
        net2 = MagicMock(company_name="Acme", address="10.20.0.0/24", pk=2)
        net_other = MagicMock(company_name="Globex", address="10.10.0.0/24", pk=3)
        adapter.get_all.return_value = [net1, net2, net_other]

        # IP in 10.10.0.0/24 within Acme → net1.pk
        assert HuduIPAddress._resolve_network_id(adapter, "Acme", "10.10.0.5") == 1
        # IP in 10.20.0.0/24 within Acme → net2.pk
        assert HuduIPAddress._resolve_network_id(adapter, "Acme", "10.20.0.99") == 2
        # IP in no Acme network
        assert HuduIPAddress._resolve_network_id(adapter, "Acme", "192.0.2.1") is None
        # Same /24 in a different company doesn't match for Acme
        assert HuduIPAddress._resolve_network_id(adapter, "Globex", "10.10.0.5") == 3

    def test_resolve_network_id_handles_invalid_ip(self) -> None:
        from unittest.mock import MagicMock

        adapter = MagicMock()
        adapter.get_all.return_value = []
        assert HuduIPAddress._resolve_network_id(adapter, "Acme", "not-an-ip") is None


class TestVLAN:
    """VLAN model — Hudu's vlan_id is the 802.1Q tag (1-4094)."""

    def test_modelname(self) -> None:
        assert VLAN._modelname == "vlan"

    def test_identifiers_is_company_and_vid(self) -> None:
        # Two companies can each own VLAN 100; identity must include company.
        assert VLAN._identifiers == ("company_name", "vid")

    def test_attributes(self) -> None:
        assert VLAN._attributes == ("name", "description")

    def test_construction_requires_company_and_vid(self) -> None:
        with pytest.raises(ValidationError):
            VLAN(vid=100)  # missing company_name
        with pytest.raises(ValidationError):
            VLAN(company_name="Acme")  # missing vid

    def test_vid_is_int(self) -> None:
        # Pydantic should coerce strings to int (Nautobot stores as integer).
        v = VLAN(company_name="Acme", vid=100)
        assert v.vid == 100
        assert isinstance(v.vid, int)


class TestHuduVLAN:
    def test_inherits_from_vlan(self) -> None:
        assert issubclass(HuduVLAN, VLAN)

    def test_keeps_identifiers_and_attributes(self) -> None:
        assert HuduVLAN._identifiers == VLAN._identifiers
        assert HuduVLAN._attributes == VLAN._attributes

    def test_pk_is_optional_and_not_in_attributes(self) -> None:
        instance = HuduVLAN(company_name="Acme", vid=100)
        assert instance.pk is None
        assert "pk" not in HuduVLAN._attributes


class TestRack:
    """Rack model — Hudu calls them 'rack_storages' in the API."""

    def test_modelname(self) -> None:
        assert Rack._modelname == "rack"

    def test_identifiers_is_company_and_name(self) -> None:
        assert Rack._identifiers == ("company_name", "name")

    def test_attributes_includes_dimensions_and_metadata(self) -> None:
        assert Rack._attributes == (
            "height",
            "width",
            "serial",
            "asset_tag",
            "description",
            "descending_units",
        )

    def test_construction_requires_company_and_name(self) -> None:
        with pytest.raises(ValidationError):
            Rack(name="rack-01")  # missing company_name
        with pytest.raises(ValidationError):
            Rack(company_name="Acme")  # missing name

    def test_defaults_match_typical_42u_19in_rack(self) -> None:
        # Sensible defaults so partial Nautobot data doesn't surprise the
        # operator with weird values in Hudu.
        r = Rack(company_name="Acme", name="rack-01")
        assert r.height == 42
        assert r.width == 19
        assert r.descending_units is False


class TestHuduRack:
    def test_inherits_from_rack(self) -> None:
        assert issubclass(HuduRack, Rack)

    def test_keeps_identifiers_and_attributes(self) -> None:
        assert HuduRack._identifiers == Rack._identifiers
        assert HuduRack._attributes == Rack._attributes

    def test_pk_is_optional_and_not_in_attributes(self) -> None:
        instance = HuduRack(company_name="Acme", name="rack-01")
        assert instance.pk is None
        assert "pk" not in HuduRack._attributes


class TestRackItem:
    """RackItem — Device-in-Rack relationship (Nautobot Device.rack/pos/face)."""

    def test_modelname(self) -> None:
        assert RackItem._modelname == "rackitem"

    def test_identifiers_one_per_asset(self) -> None:
        # Each Asset can only be in one rack at a time, so the asset name
        # within company is the natural identity.
        assert RackItem._identifiers == ("company_name", "asset_name")

    def test_attributes_includes_position_and_side(self) -> None:
        assert RackItem._attributes == ("rack_name", "start_unit", "end_unit", "side")

    def test_construction_requires_company_asset_rack_position(self) -> None:
        with pytest.raises(ValidationError):
            RackItem(asset_name="srv", rack_name="r", start_unit=1, end_unit=1)
        with pytest.raises(ValidationError):
            RackItem(company_name="Acme", rack_name="r", start_unit=1, end_unit=1)

    def test_default_side_is_front(self) -> None:
        # Most Nautobot Devices don't have face explicitly set; defaulting
        # to front matches Nautobot's convention and Hudu's lowercase "front".
        item = RackItem(
            company_name="Acme", asset_name="srv", rack_name="r",
            start_unit=1, end_unit=1,
        )
        assert item.side == "front"


class TestHuduRackItem:
    def test_inherits_from_rackitem(self) -> None:
        assert issubclass(HuduRackItem, RackItem)

    def test_keeps_identifiers_and_attributes(self) -> None:
        assert HuduRackItem._identifiers == RackItem._identifiers
        assert HuduRackItem._attributes == RackItem._attributes

    def test_pk_is_optional_and_not_in_attributes(self) -> None:
        from nautobot_ssot_hudu.diffsync.models.rackitem import HuduRackItem
        instance = HuduRackItem(
            company_name="Acme", asset_name="srv", rack_name="r",
            start_unit=1, end_unit=1,
        )
        assert instance.pk is None
        assert "pk" not in HuduRackItem._attributes

    def test_lookup_asset_pk(self) -> None:
        from unittest.mock import MagicMock

        # MagicMock(name=...) sets the mock's repr name, not the attribute.
        # Use plain assignment so .name returns our value.
        def make(company, name, pk):
            m = MagicMock()
            m.company_name = company
            m.name = name
            m.pk = pk
            return m

        adapter = MagicMock()
        adapter.get_all.return_value = [
            make("Acme", "srv-1", 10),
            make("Acme", "srv-2", 11),
            make("Globex", "srv-1", 12),
        ]
        assert HuduRackItem._lookup_asset_pk(adapter, "Acme", "srv-1") == 10
        # Same name in different company doesn't cross-match
        assert HuduRackItem._lookup_asset_pk(adapter, "Acme", "srv-3") is None
        assert HuduRackItem._lookup_asset_pk(adapter, "Globex", "srv-1") == 12


class TestCustomFieldsHelpers:
    """Helpers that translate between our field_values dict and Hudu's API format."""

    def test_label_to_field_key_lowercases_and_underscores(self) -> None:
        from nautobot_ssot_hudu.diffsync.models.device import _label_to_field_key

        assert _label_to_field_key("Hostname") == "hostname"
        assert _label_to_field_key("Management IP") == "management_ip"
        assert _label_to_field_key("Serial Number") == "serial_number"

    def test_build_custom_fields_payload_includes_none_values(self) -> None:
        # CRITICAL: None must be included so the diff can explicitly clear a
        # field. Omitting it would let Hudu retain the previous value, and
        # the diff would loop forever wanting to set it to None.
        from nautobot_ssot_hudu.diffsync.models.device import (
            _build_custom_fields_payload,
        )

        payload = _build_custom_fields_payload(
            {"Hostname": "edge-01", "Serial": None},
        )
        assert payload == [{"hostname": "edge-01"}, {"serial": None}]
