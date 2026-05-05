"""Stub out heavy framework imports so unit tests can run without Nautobot.

The real package's ``__init__.py`` imports ``nautobot.apps.NautobotAppConfig``
at top level, which in turn requires the entire Django + Nautobot install
chain. For schema-only tests on the DiffSync models we don't need any of
that — we just need ``diffsync`` (already a transitive dep) and Python.

This conftest installs lightweight ``MagicMock`` placeholders for every
external module our package imports, *before* pytest has a chance to import
the package. Result: ``import nautobot_ssot_hudu`` succeeds against the
mocks, the AppConfig class exists, but no real framework code runs.

Tests that need real Nautobot/Django machinery should live in a separate
``tests/integration/`` tree and run inside the dev container.
"""

import sys
from unittest.mock import MagicMock

_FAKE_MODULES = [
    "nautobot",
    "nautobot.apps",
    "nautobot.apps.jobs",
    "nautobot.dcim",
    "nautobot.dcim.models",
    "nautobot.ipam",
    "nautobot.ipam.models",
    "nautobot.tenancy",
    "nautobot.tenancy.models",
    "nautobot.extras",
    "nautobot.extras.choices",
    "nautobot.extras.models",
    "nautobot_ssot",
    "nautobot_ssot.jobs",
    "nautobot_ssot.jobs.base",
    "django",
    "django.conf",
    "django.core",
    "django.core.exceptions",
    "hudu_magic",
]

for name in _FAKE_MODULES:
    sys.modules.setdefault(name, MagicMock())
