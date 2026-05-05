"""Hudu-side DiffSync adapter (data target)."""

from diffsync import Adapter

from nautobot_ssot_hudu.diffsync.models.company import HuduCompany
from nautobot_ssot_hudu.diffsync.models.device import HuduDevice
from nautobot_ssot_hudu.diffsync.models.ipaddress import HuduIPAddress
from nautobot_ssot_hudu.diffsync.models.network import HuduNetwork
from nautobot_ssot_hudu.diffsync.models.rack import HuduRack
from nautobot_ssot_hudu.diffsync.models.rackitem import HuduRackItem
from nautobot_ssot_hudu.diffsync.models.vlan import HuduVLAN
from nautobot_ssot_hudu.utils.hudu_client import build_client


class HuduAdapter(Adapter):
    """Load current Hudu state into DiffSync models so we can diff against Nautobot."""

    company = HuduCompany
    device = HuduDevice
    network = HuduNetwork
    ipaddress = HuduIPAddress
    vlan = HuduVLAN
    rack = HuduRack
    rackitem = HuduRackItem

    top_level = (
        "company",
        "device",
        # vlan before network so Network -> VLAN linkage resolves at write time
        "vlan",
        "network",
        "ipaddress",
        "rack",
        "rackitem",
    )

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
        # VLANs before Networks so Network's vlan_vid linkage can resolve
        # via reverse lookup against loaded HuduVLAN records.
        self._load_vlans()
        self._load_networks()
        self._load_ipaddresses()
        self._load_racks()
        self._load_rack_items()

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
        # Reverse-lookup map for the optional VLAN linkage on Networks:
        # Hudu returns vlan_id (the VLAN pk); we translate to vlan_vid (the
        # 802.1Q tag) so the diff aligns with the Nautobot side which has
        # vid not pk.
        vid_by_vlan_pk = {
            v.pk: v.vid for v in self.get_all("vlan") if v.pk is not None
        }
        for net in self.client.get("networks", paginate=False) or []:
            company_pk = net.get("company_id")
            company_name = company_name_by_pk.get(company_pk)
            if company_name is None:
                continue  # archived/missing parent
            address = net.get("address")
            vlan_pk = net.get("vlan_id")
            self.add(
                self.network(
                    company_name=company_name,
                    address=address,
                    name=net.get("name") or address,
                    description=(net.get("description") or None),
                    vlan_vid=vid_by_vlan_pk.get(vlan_pk) if vlan_pk else None,
                    pk=net.get("id"),
                )
            )

    def _load_rack_items(self) -> None:
        device_by_pk = {
            d.pk: (d.company_name, d.name)
            for d in self.get_all("device")
            if d.pk is not None
        }
        rack_by_pk = {
            r.pk: (r.company_name, r.name)
            for r in self.get_all("rack")
            if r.pk is not None
        }
        # Hudu's GET /rack_storage_items response is missing rack_storage_id
        # — confirmed empirically against Hudu 2.40+. Reverse-look-up by
        # walking each rack's front_items + rear_items (which DO include
        # item ids and are returned in the rack list response). Single
        # rack_storages.list() call gives us everything.
        item_to_rack_pk: dict[int, int] = {}
        for r in self.client.rack_storages.list() or []:
            for slot in (getattr(r, "front_items", None) or []) + (
                getattr(r, "rear_items", None) or []
            ):
                slot_item_id = slot.get("id") if isinstance(slot, dict) else None
                if slot_item_id is not None:
                    item_to_rack_pk[slot_item_id] = r.id

        # Same pagination quirk as networks/ip_addresses/vlans on the items
        # endpoint itself. Bypass with paginate=False.
        for item in self.client.get("rack_storage_items", paginate=False) or []:
            asset = device_by_pk.get(item.get("asset_id"))
            if asset is None:
                continue  # asset is in a layout we don't sync; skip
            company_name, asset_name = asset
            rack_pk = item_to_rack_pk.get(item["id"])
            rack = rack_by_pk.get(rack_pk) if rack_pk else None
            if rack is None:
                continue  # rack not loaded (different company perhaps)
            _, rack_name = rack
            self.add(
                self.rackitem(
                    company_name=company_name,
                    asset_name=asset_name,
                    rack_name=rack_name,
                    start_unit=item["start_unit"],
                    end_unit=item["end_unit"],
                    side=(item.get("side") or "front").lower(),
                    pk=item["id"],
                )
            )

    def _load_racks(self) -> None:
        company_name_by_pk = {
            c.pk: c.name for c in self.get_all("company") if c.pk is not None
        }
        # Unlike networks/ip_addresses/vlans, /api/v1/rack_storages accepts
        # the `page` query param happily — no paginate=False bypass needed.
        for r in self.client.rack_storages.list() or []:
            company_name = company_name_by_pk.get(getattr(r, "company_id", None))
            if company_name is None:
                continue
            self.add(
                self.rack(
                    company_name=company_name,
                    name=r.name,
                    height=getattr(r, "height", None) or 42,
                    width=getattr(r, "width", None) or 19,
                    serial=getattr(r, "serial_number", None) or None,
                    asset_tag=getattr(r, "asset_tag", None) or None,
                    description=getattr(r, "description", None) or None,
                    descending_units=getattr(r, "descending_units", False),
                    pk=r.id,
                )
            )

    def _load_vlans(self) -> None:
        company_name_by_pk = {
            c.pk: c.name for c in self.get_all("company") if c.pk is not None
        }
        # Same pagination quirk as networks/ip_addresses: bypass via paginate=False.
        for v in self.client.get("vlans", paginate=False) or []:
            company_name = company_name_by_pk.get(v.get("company_id"))
            if company_name is None:
                continue
            vid = v.get("vlan_id")
            if vid is None:
                continue  # Hudu allows null vlan_id; skip — no Nautobot equivalent.
            self.add(
                self.vlan(
                    company_name=company_name,
                    vid=int(vid),
                    name=(v.get("name") or None),
                    description=(v.get("description") or None),
                    pk=v.get("id"),
                )
            )

    def _load_ipaddresses(self) -> None:
        company_name_by_pk = {
            c.pk: c.name for c in self.get_all("company") if c.pk is not None
        }
        # Reverse-lookup for the optional Asset linkage on IPs: Hudu returns
        # asset_id; we translate to asset_name so the diff aligns with the
        # Nautobot side (which works in names not pks).
        name_by_asset_pk = {
            d.pk: d.name for d in self.get_all("device") if d.pk is not None
        }
        # Same pagination quirk as networks: ip_addresses endpoint rejects
        # the `page` query param hudu-magic auto-adds. Bypass with paginate=False.
        for ip in self.client.get("ip_addresses", paginate=False) or []:
            company_name = company_name_by_pk.get(ip.get("company_id"))
            if company_name is None:
                continue
            asset_pk = ip.get("asset_id")
            self.add(
                self.ipaddress(
                    company_name=company_name,
                    address=ip.get("address"),
                    dns_name=(ip.get("fqdn") or None),
                    description=(ip.get("description") or None),
                    asset_name=name_by_asset_pk.get(asset_pk) if asset_pk else None,
                    pk=ip.get("id"),
                )
            )
