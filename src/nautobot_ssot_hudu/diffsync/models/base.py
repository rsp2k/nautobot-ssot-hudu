"""Base DiffSync model shared by Nautobot and Hudu sides."""

from diffsync import DiffSyncModel


class HuduSSoTModel(DiffSyncModel):
    """Common base so we can hang shared behavior here later (logging, validation)."""
