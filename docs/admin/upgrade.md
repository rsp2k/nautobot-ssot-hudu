# Upgrading the App

Date-based releases mean every version is a candidate to upgrade to — `YYYY.M.D` numbers don't carry semver semantics, but the API surface is stable: same `PLUGINS_CONFIG` schema, same Job parameters, same SecretsGroup conventions.

## Standard upgrade

```shell
pip install -U nautobot-ssot-hudu
nautobot-server post_upgrade
sudo systemctl restart nautobot nautobot-worker nautobot-scheduler
```

## Before upgrading across major Nautobot versions

The plugin pins Nautobot to `>=3.0,<4.0`. When Nautobot 4.x lands, this app's release notes will indicate the specific version that supports it. Until then, upgrading Nautobot to 4.x with this app installed will fail at install time (intentional — surfaces the incompatibility before a runtime ImportError).

## Verifying

After upgrade, confirm the app is loaded:

```shell
nautobot-server shell -c "import nautobot_ssot_hudu; print(nautobot_ssot_hudu.__version__)"
```

In the UI, navigate to **Apps → Installed Apps** and confirm `nautobot-ssot-hudu` is listed with the expected version.

A test sync in dry-run mode is the fastest end-to-end verification:

1. **Apps → Single Source of Truth → Dashboard**
2. Find **Hudu (Data Target)** under "Data Targets"
3. Click **Sync**
4. Leave `dryrun` checked, click **Run Job Now**
5. The Sync Detail page should show your existing Hudu records as no-change (or a clean diff if Nautobot has new/changed records)
