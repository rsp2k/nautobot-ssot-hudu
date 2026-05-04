"""Hudu-side DiffSync adapter (data target)."""

from diffsync import Adapter

from nautobot_ssot_hudu.diffsync.models.company import Company


class HuduAdapter(Adapter):
    """Load current Hudu state into DiffSync models so we can diff against Nautobot."""

    company = Company

    top_level = ("company",)

    def __init__(self, *args, job=None, sync=None, client=None, **kwargs) -> None:
        """Store Job, Sync, and Hudu client references."""
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync
        self.client = client

    def load(self) -> None:
        """Populate DiffSync models from the live Hudu instance."""
        raise NotImplementedError
