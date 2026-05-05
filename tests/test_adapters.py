"""Adapter loader tests focused on the empty-string-to-None coercion.

This is the subtle behavior that protects diff stability across syncs: both
adapters must agree that "no description" → None (not ""), so DiffSync sees
a Nautobot Tenant with empty description and a Hudu Company with null/empty
notes as equivalent. Without this coercion every sync would emit a useless
update for every empty-description record forever.

Tests mock the external sources (Nautobot ORM, hudu-magic client) and
exercise the real adapter ``load()`` paths end-to-end through DiffSync.
"""

from unittest.mock import MagicMock, patch


def _make_obj(**attrs):
    """MagicMock that exposes the given attributes as plain values.

    MagicMock's constructor name kwarg sets the *mock's* repr name, not the
    instance's .name attribute, so we have to set attrs after construction.
    """
    m = MagicMock()
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


class TestNautobotAdapter:
    """NautobotAdapter._load_companies coercion."""

    @patch("nautobot_ssot_hudu.diffsync.adapters.nautobot.Tenant")
    def test_loads_tenants_into_companies(self, mock_tenant_cls) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        mock_tenant_cls.objects.all.return_value = [
            _make_obj(name="Acme", description="Real description."),
            _make_obj(name="Wonka", description="Confectionery."),
        ]

        adapter = NautobotAdapter()
        adapter.load()

        by_name = {c.name: c for c in adapter.get_all("company")}
        assert set(by_name) == {"Acme", "Wonka"}
        assert by_name["Acme"].description == "Real description."
        assert by_name["Wonka"].description == "Confectionery."

    @patch("nautobot_ssot_hudu.diffsync.adapters.nautobot.Tenant")
    def test_empty_string_description_coerced_to_none(self, mock_tenant_cls) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        # Nautobot's Tenant.description is a TextField(blank=True) → empty
        # string when unset. Coercion is what makes the diff stable.
        mock_tenant_cls.objects.all.return_value = [
            _make_obj(name="Initech", description=""),
        ]

        adapter = NautobotAdapter()
        adapter.load()

        company = adapter.get_all("company")[0]
        assert company.description is None, (
            "Empty Nautobot description must coerce to None, otherwise the "
            "diff against Hudu (which loads empty/null as None) emits a "
            "spurious update on every sync."
        )

    @patch("nautobot_ssot_hudu.diffsync.adapters.nautobot.Tenant")
    def test_loads_zero_tenants_cleanly(self, mock_tenant_cls) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        mock_tenant_cls.objects.all.return_value = []

        adapter = NautobotAdapter()
        adapter.load()

        assert list(adapter.get_all("company")) == []


class TestNautobotAdapterFieldResolution:
    """The dotted-path attribute resolver used to populate device field_values."""

    def test_simple_attribute(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        device = _make_obj(name="edge-01")
        assert NautobotAdapter._resolve_field_value(device, "name") == "edge-01"

    def test_dotted_path(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        device = _make_obj(device_type=_make_obj(model="ISR4321"))
        assert NautobotAdapter._resolve_field_value(device, "device_type.model") == "ISR4321"

    def test_none_propagates_through_dotted_path(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        # Device without primary_ip4 → primary_ip4 is None → no AttributeError,
        # just returns None for the whole path.
        device = _make_obj(primary_ip4=None)
        assert NautobotAdapter._resolve_field_value(device, "primary_ip4.host") is None

    def test_empty_string_coerced_to_none(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        # CharField defaults are "" but Hudu stores unset as null. Without
        # coercion every sync would emit spurious updates for blank fields.
        device = _make_obj(serial="")
        assert NautobotAdapter._resolve_field_value(device, "serial") is None

    def test_real_value_passes_through(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        device = _make_obj(serial="FOC1234XYZ")
        assert NautobotAdapter._resolve_field_value(device, "serial") == "FOC1234XYZ"


class TestHuduAdapter:
    """HuduAdapter._load_companies coercion + pk capture."""

    def test_loads_companies_with_pk(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

        mock_client = MagicMock()
        mock_client.companies.list.return_value = [
            _make_obj(id=1, name="Acme", notes="Real notes."),
            _make_obj(id=2, name="Wonka", notes="Confectionery."),
        ]

        adapter = HuduAdapter(client=mock_client)
        adapter.load()

        by_name = {c.name: c for c in adapter.get_all("company")}
        assert by_name["Acme"].pk == 1
        assert by_name["Acme"].description == "Real notes."
        assert by_name["Wonka"].pk == 2
        assert by_name["Wonka"].description == "Confectionery."

    def test_empty_notes_coerced_to_none(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

        mock_client = MagicMock()
        mock_client.companies.list.return_value = [
            _make_obj(id=10, name="Initech", notes=""),
        ]

        adapter = HuduAdapter(client=mock_client)
        adapter.load()

        company = adapter.get_all("company")[0]
        assert company.description is None

    def test_none_notes_stays_none(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

        mock_client = MagicMock()
        mock_client.companies.list.return_value = [
            _make_obj(id=11, name="Globex", notes=None),
        ]

        adapter = HuduAdapter(client=mock_client)
        adapter.load()

        company = adapter.get_all("company")[0]
        assert company.description is None

    def test_missing_notes_attribute_treated_as_none(self) -> None:
        """If hudu-magic's Company object doesn't expose ``notes`` for some
        reason (different layout, API version drift), we get None instead of
        AttributeError. Defensive ``getattr`` in the adapter does the work.
        """
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

        mock_client = MagicMock()
        company_with_no_notes = MagicMock(spec=["id", "name"])
        company_with_no_notes.id = 99
        company_with_no_notes.name = "MysteryCorp"
        mock_client.companies.list.return_value = [company_with_no_notes]

        adapter = HuduAdapter(client=mock_client)
        adapter.load()

        company = adapter.get_all("company")[0]
        assert company.description is None


class TestHuduAdapterDeviceLoading:
    """HuduAdapter._load_devices opt-in via device_layout_id."""

    def test_skips_device_load_when_layout_id_is_none(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

        mock_client = MagicMock()
        mock_client.companies.list.return_value = []

        adapter = HuduAdapter(client=mock_client, device_layout_id=None)
        adapter.load()

        # Companies were loaded (empty, but the call happened)...
        mock_client.companies.list.assert_called_once()
        # ...but assets.list must NOT have been called: no device_layout_id
        # means we have no idea which Hudu layout represents devices, so we
        # skip rather than dragging every asset of every layout into the diff.
        mock_client.assets.list.assert_not_called()

    def test_loads_devices_filtered_by_layout_id_when_set(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

        mock_client = MagicMock()
        mock_client.companies.list.return_value = [
            _make_obj(id=1, name="Acme", notes=""),
        ]
        mock_client.assets.list.return_value = [
            _make_obj(id=100, name="edge-01", company_id=1, notes=""),
        ]

        adapter = HuduAdapter(client=mock_client, device_layout_id=7)
        adapter.load()

        mock_client.assets.list.assert_called_once_with(asset_layout_id=7)
        device = adapter.get_all("device")[0]
        assert device.company_name == "Acme"
        assert device.name == "edge-01"
        assert device.pk == 100

    def test_skips_assets_whose_company_isnt_loaded(self) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

        mock_client = MagicMock()
        mock_client.companies.list.return_value = [
            _make_obj(id=1, name="Acme", notes=""),
        ]
        # Asset references company_id=999 which we never loaded — could be an
        # archived/deleted Hudu Company. Skip silently rather than crash on
        # the missing parent identifier.
        mock_client.assets.list.return_value = [
            _make_obj(id=100, name="orphan", company_id=999, notes=""),
        ]

        adapter = HuduAdapter(client=mock_client, device_layout_id=7)
        adapter.load()

        assert adapter.get_all("device") == []


class TestDiffStability:
    """End-to-end check: empty-on-both-sides matches as no-change."""

    @patch("nautobot_ssot_hudu.diffsync.adapters.nautobot.Tenant")
    def test_empty_description_diffs_clean_against_empty_notes(
        self, mock_tenant_cls
    ) -> None:
        from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter
        from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter

        # Nautobot: Initech with empty-string description (TextField default)
        mock_tenant_cls.objects.all.return_value = [
            _make_obj(name="Initech", description=""),
        ]
        src = NautobotAdapter()
        src.load()

        # Hudu: same Initech, empty notes
        mock_client = MagicMock()
        mock_client.companies.list.return_value = [
            _make_obj(id=1, name="Initech", notes=""),
        ]
        tgt = HuduAdapter(client=mock_client)
        tgt.load()

        diff = src.diff_to(tgt)
        summary = diff.summary()
        assert summary == {
            "create": 0,
            "update": 0,
            "delete": 0,
            "no-change": 1,
            "skip": 0,
        }, (
            f"Expected idempotent no-change diff for matching empty-description "
            f"records on both sides; got {summary}"
        )
