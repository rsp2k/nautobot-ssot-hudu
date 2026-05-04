"""Nautobot-side DiffSync adapter (source of truth)."""

from diffsync import Adapter

from nautobot_ssot_hudu.diffsync.models.company import Company


class NautobotAdapter(Adapter):
    """Load Nautobot ORM data into DiffSync models."""

    company = Company

    top_level = ("company",)

    def __init__(self, *args, job=None, sync=None, **kwargs) -> None:
        """Store the Job and Sync references for logging and progress."""
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync

    def load(self) -> None:
        """Populate DiffSync models from the Nautobot ORM."""
        raise NotImplementedError
