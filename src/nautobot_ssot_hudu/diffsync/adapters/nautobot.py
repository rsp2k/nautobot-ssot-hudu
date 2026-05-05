"""Nautobot-side DiffSync adapter (source of truth)."""

from diffsync import Adapter
from nautobot.dcim.models import Device, Rack
from nautobot.ipam.models import VLAN, IPAddress, Prefix
from nautobot.tenancy.models import Tenant

from nautobot_ssot_hudu.diffsync.models.company import Company
from nautobot_ssot_hudu.diffsync.models.device import Device as DeviceModel
from nautobot_ssot_hudu.diffsync.models.ipaddress import IPAddress as IPAddressModel
from nautobot_ssot_hudu.diffsync.models.network import Network as NetworkModel
from nautobot_ssot_hudu.diffsync.models.rack import Rack as RackModel
from nautobot_ssot_hudu.diffsync.models.rackitem import RackItem as RackItemModel
from nautobot_ssot_hudu.diffsync.models.vlan import VLAN as VLANModel


def _resolve_attr_path(obj, path: str):
    """Walk a dotted attribute path, returning None at any None hop.

    For ``device_field_map = {"Management IP": "primary_ip4.host"}`` we want
    ``getattr(getattr(device, "primary_ip4", None), "host", None)`` with safe
    None-propagation — a Device without a primary IP yields None for that
    field rather than crashing on AttributeError.
    """
    for part in path.split("."):
        if obj is None:
            return None
        obj = getattr(obj, part, None)
    return obj


class NautobotAdapter(Adapter):
    """Load Nautobot ORM data into DiffSync models."""

    company = Company
    device = DeviceModel
    network = NetworkModel
    ipaddress = IPAddressModel
    vlan = VLANModel
    rack = RackModel
    rackitem = RackItemModel

    top_level = (
        "company",
        "device",
        "network",
        "ipaddress",
        "vlan",
        "rack",
        "rackitem",
    )

    def __init__(
        self,
        *args,
        job=None,
        sync=None,
        device_field_map: dict[str, str] | None = None,
        device_layout_id: int | None = None,
        device_layouts_by_role: dict[str, int] | None = None,
        **kwargs,
    ) -> None:
        """Store Job, Sync, and optional device field/layout mapping config.

        ``device_field_map`` maps Hudu custom-field labels to Nautobot Device
        attribute paths. Both adapters must be initialized with the same map.

        ``device_layout_id`` is the default Hudu asset_layout_id for devices
        whose role isn't mapped explicitly. ``device_layouts_by_role`` maps
        Nautobot Role names to layout IDs for finer-grained sorting (e.g.
        routers in one Hudu layout, switches in another). Devices whose role
        isn't mapped AND with no default → skipped at load time.
        """
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync
        self.device_field_map = device_field_map or {}
        self.device_layout_id = device_layout_id
        self.device_layouts_by_role = device_layouts_by_role or {}

    def load(self) -> None:
        """Populate DiffSync models from the Nautobot ORM."""
        self._load_companies()
        self._load_devices()
        self._load_prefixes()
        self._load_ipaddresses()
        self._load_vlans()
        self._load_racks()
        self._load_rack_items()

    def _load_companies(self) -> None:
        for tenant in Tenant.objects.all():
            self.add(
                self.company(
                    name=tenant.name,
                    # Both adapters normalize empty -> None so DiffSync sees "" and None as equal.
                    description=tenant.description or None,
                )
            )

    def _load_devices(self) -> None:
        # Only sync devices that have a tenant — the company_name identifier
        # requires a parent Hudu Company. Tenant-less Nautobot Devices have
        # no natural home in Hudu's company-scoped model and are skipped.
        for device in Device.objects.filter(tenant__isnull=False).select_related(
            "tenant", "role"
        ):
            layout_id = self._resolve_layout_id(device)
            if layout_id is None:
                # Role isn't in device_layouts_by_role and no default set;
                # skip silently — operator hasn't asked us to sync this role.
                continue
            field_values = {
                label: self._resolve_field_value(device, attr_path)
                for label, attr_path in self.device_field_map.items()
            }
            self.add(
                self.device(
                    company_name=device.tenant.name,
                    name=device.name,
                    asset_layout_id=layout_id,
                    field_values=field_values,
                )
            )

    def _load_rack_items(self) -> None:
        # Only Devices that are actually mounted: have rack + position + tenant.
        # Devices with no rack assignment skip; they're not "rack items."
        qs = Device.objects.filter(
            tenant__isnull=False, rack__isnull=False, position__isnull=False
        ).select_related("tenant", "rack", "device_type")
        for device in qs:
            u_height = getattr(device.device_type, "u_height", 1) or 1
            start_unit = device.position
            end_unit = start_unit + u_height - 1
            # Nautobot's face is "front"/"rear" or empty string; default to front.
            face = (device.face or "front").lower()
            self.add(
                self.rackitem(
                    company_name=device.tenant.name,
                    asset_name=device.name,
                    rack_name=device.rack.name,
                    start_unit=start_unit,
                    end_unit=end_unit,
                    side=face,
                )
            )

    def _load_racks(self) -> None:
        for rack in Rack.objects.filter(tenant__isnull=False).select_related("tenant"):
            self.add(
                self.rack(
                    company_name=rack.tenant.name,
                    name=rack.name,
                    height=rack.u_height or 42,
                    width=rack.width or 19,
                    serial=rack.serial or None,
                    asset_tag=rack.asset_tag or None,
                    # Nautobot uses `comments` for free-form text; map to
                    # Hudu's `description` for the same operator semantics.
                    description=rack.comments or None,
                    descending_units=rack.desc_units,
                )
            )

    def _load_vlans(self) -> None:
        for vlan in VLAN.objects.filter(tenant__isnull=False).select_related("tenant"):
            self.add(
                self.vlan(
                    company_name=vlan.tenant.name,
                    vid=vlan.vid,
                    name=vlan.name or None,
                    description=vlan.description or None,
                )
            )

    def _load_ipaddresses(self) -> None:
        # Same tenant-scoped filter as devices and prefixes.
        for ip in IPAddress.objects.filter(tenant__isnull=False).select_related("tenant"):
            self.add(
                self.ipaddress(
                    company_name=ip.tenant.name,
                    address=str(ip.host),
                    dns_name=ip.dns_name or None,
                    description=ip.description or None,
                )
            )

    def _resolve_layout_id(self, device) -> int | None:
        # Per-role override wins over the default. Role name matching is
        # case-sensitive — operators name their roles consistently in
        # Nautobot anyway.
        role_name = getattr(getattr(device, "role", None), "name", None)
        if role_name and role_name in self.device_layouts_by_role:
            return self.device_layouts_by_role[role_name]
        return self.device_layout_id

    def _load_prefixes(self) -> None:
        # Same tenant-scoped filter as devices: a prefix without a tenant
        # has no parent Hudu Company to attach to.
        for prefix in Prefix.objects.filter(tenant__isnull=False).select_related("tenant"):
            self.add(
                self.network(
                    company_name=prefix.tenant.name,
                    address=str(prefix.prefix),
                    # Nautobot Prefix has no first-class name field; derive one
                    # from the CIDR so Hudu has something readable to display.
                    name=str(prefix.prefix),
                    description=prefix.description or None,
                )
            )

    @staticmethod
    def _resolve_field_value(device, attr_path: str) -> str | None:
        """Resolve a configured Nautobot attr path to a string for the diff.

        Empty string is coerced to None so the diff is stable: Hudu stores
        unset fields as null, Nautobot's CharField defaults are often "" —
        without this coercion every sync would emit a spurious update for
        any blank field.
        """
        value = _resolve_attr_path(device, attr_path)
        if value is None:
            return None
        str_value = str(value)
        return str_value or None
