"""Hudu-side DiffSync adapter (data target)."""

from diffsync import Adapter

from nautobot_ssot_hudu.diffsync.models.company import HuduCompany, HuduDevice
from nautobot_ssot_hudu.utils.hudu_client import build_client


class HuduAdapter(Adapter):
    """Load current Hudu state into DiffSync models so we can diff against Nautobot."""

    company = HuduCompany
    device = HuduDevice

    top_level = ("company", "device")

    def __init__(
        self,
        *args,
        job=None,
        sync=None,
        client=None,
        hard_delete: bool = False,
        device_layout_id: int | None = None,
        **kwargs,
    ) -> None:
        """Store Job, Sync, Hudu client, delete-behavior flag, and device layout id.

        ``client`` is injectable for tests; in production it defaults to a
        client built from PLUGINS_CONFIG + Nautobot Secrets. ``hard_delete``
        is read by HuduCompany.delete() to choose archive() vs delete().
        ``device_layout_id`` is the Hudu asset_layout_id under which Devices
        will be created/loaded; required when syncing devices.
        """
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync
        self.client = client or build_client()
        self.hard_delete = hard_delete
        self.device_layout_id = device_layout_id

    def load(self) -> None:
        """Populate DiffSync models from the live Hudu instance."""
        self._load_companies()
        if self.device_layout_id is not None:
            self._load_devices()

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
        # Hudu's asset list endpoint accepts asset_layout_id as a filter; only
        # pull assets in our configured layout to avoid loading the user's
        # other asset types into the diff.
        for asset in self.client.assets.list(asset_layout_id=self.device_layout_id):
            company_name = company_name_by_pk.get(asset.company_id)
            if company_name is None:
                # Asset belongs to a Hudu Company we didn't see in _load_companies
                # (e.g., archived). Skip — no Nautobot side to diff against.
                continue
            self.add(
                self.device(
                    company_name=company_name,
                    name=asset.name,
                    description=None,  # MVP: no description mapping yet.
                    pk=asset.id,
                )
            )
