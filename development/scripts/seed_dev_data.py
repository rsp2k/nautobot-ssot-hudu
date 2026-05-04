"""Seed dev data for the SSoT-Hudu integration.

Idempotent. Re-run is safe — uses get_or_create / update_or_create.

Creates:
- Five fictional Tenants (Acme, Globex, Initech, Soylent, Cyberdyne)
- A SecretsGroup named "Hudu Credentials" containing a Token-type Secret
  whose value is read from the HUDU_API_KEY env var (if set).

Run via: ``nautobot-server runscript dev_scripts.seed_dev_data``
The dev_scripts package is mounted at /opt/nautobot/jobs/dev_scripts/.
"""

import os

from nautobot.extras.choices import (
    SecretsGroupAccessTypeChoices,
    SecretsGroupSecretTypeChoices,
)
from nautobot.extras.models import Secret, SecretsGroup, SecretsGroupAssociation
from nautobot.tenancy.models import Tenant

TENANTS = [
    ("Acme Corp", "Roadrunner-tracking holding company."),
    ("Globex Industries", "Diversified multinational. Description deliberately long-ish."),
    ("Initech", ""),  # Empty description — exercise empty/None coercion path.
    ("Soylent Industries", "Foodstuffs."),
    ("Cyberdyne Systems", "Defense contractor specializing in HK series."),
]

SECRET_GROUP_NAME = "Hudu Credentials"
SECRET_NAME = "Hudu API Key"


def run() -> None:
    """Entry point invoked by nautobot-server runscript."""
    print("=== Seeding Tenants ===")
    for name, description in TENANTS:
        tenant, created = Tenant.objects.update_or_create(
            name=name,
            defaults={"description": description},
        )
        action = "created" if created else "updated"
        print(f"  {action}: {tenant.name!r}")

    print()
    print("=== Seeding SecretsGroup ===")
    api_key = os.environ.get("HUDU_API_KEY", "")

    secret, secret_created = Secret.objects.update_or_create(
        name=SECRET_NAME,
        defaults={
            "provider": "environment-variable",
            "parameters": {"variable": "HUDU_API_KEY"},
        },
    )
    print(f"  Secret {SECRET_NAME!r} {'created' if secret_created else 'updated'}")
    if not api_key:
        print("  (HUDU_API_KEY env var is empty — secret resolution will fail until set)")

    group, group_created = SecretsGroup.objects.get_or_create(name=SECRET_GROUP_NAME)
    print(f"  SecretsGroup {SECRET_GROUP_NAME!r} {'created' if group_created else 'exists'}")

    SecretsGroupAssociation.objects.update_or_create(
        secrets_group=group,
        access_type=SecretsGroupAccessTypeChoices.TYPE_HTTP,
        secret_type=SecretsGroupSecretTypeChoices.TYPE_TOKEN,
        defaults={"secret": secret},
    )
    print("  Associated Secret to SecretsGroup with (HTTP, Token)")

    print()
    print(f"Tenants in DB: {Tenant.objects.count()}")
    print(f"SecretsGroups in DB: {SecretsGroup.objects.count()}")
