# Compatibility Matrix

| Nautobot SSoT Hudu Version | Nautobot Version Range | `nautobot-app-ssot` | `hudu-magic` | Hudu (tested) |
|---|---|---|---|---|
| 2026.5.X | 3.0.0 – 3.99.99 | 4.2.X | 0.4.X | 2.40+ self-hosted |

Versioning follows [CalVer](https://calver.org/) — `YYYY.M.D` communicates *when* the package was tested against external API surfaces (Nautobot, Hudu, hudu-magic), not internal API stability.

## Minimum dependencies

- Python 3.10+ (intersection of `nautobot-ssot` 4.x and `hudu-magic` 0.4)
- Nautobot 3.0+ (transitively required by `nautobot-ssot` 4.x; we pin directly so install-time errors surface clearly if Nautobot is bumped to 4.x)

## Hudu API support

Tested against self-hosted Hudu 2.40+. Cloud-hosted Hudu (`*.huducloud.com`) should work identically — the API is the same — but is not currently part of the test matrix.

See [`docs/user/external_interactions.md`](../user/external_interactions.md) for the API quirks the plugin works around.
