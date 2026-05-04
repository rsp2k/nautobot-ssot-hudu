"""Nautobot Jobs that drive the Hudu sync."""

from nautobot.apps.jobs import BooleanVar, register_jobs
from nautobot_ssot.jobs.base import DataTarget

from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter
from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter


class HuduDataTarget(DataTarget):
    """Push Nautobot data into Hudu."""

    hard_delete = BooleanVar(
        default=False,
        description="Permanently delete Hudu records that no longer exist in Nautobot. "
        "If False (default), archive them instead — recoverable via the Hudu UI.",
    )

    class Meta:
        """Job metadata."""

        name = "Nautobot -> Hudu"
        data_target = "Hudu"
        data_target_icon = "/static/nautobot_ssot_hudu/hudu_logo.png"
        description = "Sync Nautobot tenants/devices to Hudu companies/assets."

    def load_source_adapter(self) -> None:
        """Load Nautobot data into the source DiffSync adapter."""
        self.source_adapter = NautobotAdapter(job=self, sync=self.sync)
        self.source_adapter.load()

    def load_target_adapter(self) -> None:
        """Load current Hudu state into the target DiffSync adapter."""
        from django.conf import settings

        plugin_cfg = settings.PLUGINS_CONFIG.get("nautobot_ssot_hudu", {})
        device_layout_id = plugin_cfg.get("asset_layouts", {}).get("device")

        self.target_adapter = HuduAdapter(
            job=self,
            sync=self.sync,
            hard_delete=self.hard_delete,
            device_layout_id=device_layout_id,
        )
        self.target_adapter.load()


jobs = [HuduDataTarget]
register_jobs(*jobs)
