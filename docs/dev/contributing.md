# Contributing to the App

PRs welcome. Before opening one:

- Run `uv run pytest` — all tests pass
- Run `uvx ruff check .` — no lint errors
- Add a test for any new behavior (the test suite is 94 tests in <1s; one more shouldn't slow it down)
- Update `docs/` if your change affects user-visible behavior

## Commit style

- Imperative mood, present tense ("Add foo", not "Added foo" or "Adds foo")
- First line ≤72 chars, body wrapping at 72 chars
- No AI-attribution lines
- Reference the entity affected when relevant ("HuduDevice.create: pass custom_fields")

## Test discipline

The plugin runs unit tests *without* a Nautobot install (the `tests/conftest.py` mocks `nautobot.*`/`django.*`/`hudu_magic` import-time dependencies). This keeps the CI fast and portable.

For tests that require the live Django ORM, run them inside the dev container via `docker compose exec nautobot-web pytest`. We don't currently run those in CI.

## Adding a new entity type

See [Extending the App](extending.md) for the full walkthrough. Briefly:

1. Add the DiffSync model file under `src/nautobot_ssot_hudu/diffsync/models/<entity>.py`
2. Wire it into both adapters
3. Add to `top_level` in the right order (parents before children — see entity loading order in `adapters/hudu.py`)
4. Add tests
5. Update the [mapping table](../user/app_overview.md#what-it-syncs) and the per-entity model doc

## Reporting Hudu API quirks

If you find a Hudu behavior we don't already work around, please document it in [`development/hudu/HUDU_API_QUIRKS.md`](https://github.com/rpm/nautobot-plugin-ssot-hudu/blob/main/development/hudu/HUDU_API_QUIRKS.md) as part of the PR. The pattern is:

1. Brief description of the behavior
2. The endpoint(s) it affects
3. The workaround (with code example)
4. Any related `hudu-magic` library bug

Future contributors save real time by having quirks pre-documented.
