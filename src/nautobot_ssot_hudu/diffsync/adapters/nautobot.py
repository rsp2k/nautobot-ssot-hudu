"""Nautobot-side DiffSync adapter (source of truth)."""

from diffsync import Adapter
from nautobot.dcim.models import Device
from nautobot.tenancy.models import Tenant

from nautobot_ssot_hudu.diffsync.models.company import Company
from nautobot_ssot_hudu.diffsync.models.company import Device as DeviceModel


class NautobotAdapter(Adapter):
    """Load Nautobot ORM data into DiffSync models."""

    company = Company
    device = DeviceModel

    top_level = ("company", "device")

    def __init__(self, *args, job=None, sync=None, **kwargs) -> None:
        """Store the Job and Sync references for logging and progress."""
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync

    def load(self) -> None:
        """Populate DiffSync models from the Nautobot ORM."""
        self._load_companies()
        self._load_devices()

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
        for device in Device.objects.filter(tenant__isnull=False).select_related("tenant"):
            self.add(
                self.device(
                    company_name=device.tenant.name,
                    name=device.name,
                    description=None,  # Nautobot Device has no description field; placeholder.
                )
            )
