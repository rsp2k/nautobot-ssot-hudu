"""Hudu-side DiffSync adapter (data target)."""

from diffsync import Adapter

from nautobot_ssot_hudu.diffsync.models.company import (
    HuduCompany,
    HuduDevice,
    HuduNetwork,
)
from nautobot_ssot_hudu.utils.hudu_client import build_client


class HuduAdapter(Adapter):
    """Load current Hudu state into DiffSync models so we can diff against Nautobot."""

    company = HuduCompany
    device = HuduDevice
    network = HuduNetwork

    top_level = ("company", "device", "network")

    def __init__(
        self,
        *args,
        job=None,
        sync=None,
        client=None,
        hard_delete: bool = False,
        device_layout_id: int | None = None,
        device_layouts_by_role: dict[str, int] | None = None,
        device_field_map: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        """Store Job, Sync, Hudu client, delete-behavior flag, and device config.

        ``device_layouts_by_role`` mirrors NautobotAdapter's same arg. The
        union of its values + ``device_layout_id`` is the set of Hudu layouts
        we'll load assets from.
        """
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync
        self.client = client or build_client()
        self.hard_delete = hard_delete
        self.device_layout_id = device_layout_id
        self.device_layouts_by_role = device_layouts_by_role or {}
        self.device_field_map = device_field_map or {}

    def load(self) -> None:
        """Populate DiffSync models from the live Hudu instance."""
        self._load_companies()
        if self._all_device_layout_ids():
            self._load_devices()
        self._load_networks()

    def _all_device_layout_ids(self) -> set[int]:
        """The union of layouts to load assets from: default + per-role values."""
        ids: set[int] = set()
        if self.device_layout_id is not None:
            ids.add(self.device_layout_id)
        ids.update(self.device_layouts_by_role.values())
        return ids

    def _load_companies(self) -> None:
        for company in self.client.companies.list():
            self.add(
                self.company(
                    name=company.name,
                    # Hudu's `notes` is the closest analog to Nautobot's `description`.
                    # Normalize missing/empty -> None to match the Nautobot adapter.
                    description=getattr(company, "notes", None) or None,
                    pk=company.id,
                )
            )

    def _load_devices(self) -> None:
        # Build a pk -> company_name map so we can attach each asset to its
        # parent's identifier (composite identity needs company_name, not pk).
        company_name_by_pk = {
            c.pk: c.name for c in self.get_all("company") if c.pk is not None
        }
        # Only consider Hudu custom-field labels that the operator has mapped;
        # pulling everything would mean fields managed by humans show up as
        # "diffs to clear" because the Nautobot side doesn't know about them.
        managed_labels = set(self.device_field_map.keys())
        # Hudu's asset list endpoint accepts asset_layout_id as a filter; pull
        # assets from each configured layout (default + per-role overrides),
        # avoiding the user's other asset_layouts that aren't sync-managed.
        for layout_id in self._all_device_layout_ids():
            for asset in self.client.assets.list(asset_layout_id=layout_id):
                company_name = company_name_by_pk.get(asset.company_id)
                if company_name is None:
                    # Asset belongs to a Hudu Company we didn't see in _load_companies
                    # (e.g., archived). Skip — no Nautobot side to diff against.
                    continue
                field_values = {
                    f["label"]: (f.get("value") or None)
                    for f in (asset.fields or [])
                    if f.get("label") in managed_labels
                }
                # Fill in missing managed labels as None so both sides have the same key set.
                for label in managed_labels:
                    field_values.setdefault(label, None)
                self.add(
                    self.device(
                        company_name=company_name,
                        name=asset.name,
                        asset_layout_id=layout_id,
                        field_values=field_values,
                        pk=asset.id,
                        company_pk=asset.company_id,
                    )
                )

    def _load_networks(self) -> None:
        company_name_by_pk = {
            c.pk: c.name for c in self.get_all("company") if c.pk is not None
        }
        # hudu-magic's `c.networks.list()` auto-appends `?page=1` for
        # pagination but Hudu's /api/v1/networks endpoint rejects `page` as
        # an invalid filter param (HTTP 400). Bypass by going through
        # HuduClient.get directly with paginate=False, which returns a list
        # of raw dicts instead of the wrapped objects.
        for net in self.client.get("networks", paginate=False) or []:
            company_pk = net.get("company_id")
            company_name = company_name_by_pk.get(company_pk)
            if company_name is None:
                continue  # archived/missing parent
            address = net.get("address")
            self.add(
                self.network(
                    company_name=company_name,
                    address=address,
                    name=net.get("name") or address,
                    description=(net.get("description") or None),
                    pk=net.get("id"),
                )
            )
