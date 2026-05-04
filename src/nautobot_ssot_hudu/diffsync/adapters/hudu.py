"""Hudu-side DiffSync adapter (data target)."""

from diffsync import Adapter

from nautobot_ssot_hudu.diffsync.models.company import HuduCompany
from nautobot_ssot_hudu.utils.hudu_client import build_client


class HuduAdapter(Adapter):
    """Load current Hudu state into DiffSync models so we can diff against Nautobot."""

    company = HuduCompany

    top_level = ("company",)

    def __init__(
        self,
        *args,
        job=None,
        sync=None,
        client=None,
        hard_delete: bool = False,
        **kwargs,
    ) -> None:
        """Store Job, Sync, Hudu client, and delete-behavior flag.

        ``client`` is injectable for tests; in production it defaults to a
        client built from PLUGINS_CONFIG + Nautobot Secrets. ``hard_delete``
        is read by HuduCompany.delete() to choose archive() vs delete().
        """
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync
        self.client = client or build_client()
        self.hard_delete = hard_delete

    def load(self) -> None:
        """Populate DiffSync models from the live Hudu instance."""
        self._load_companies()

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
