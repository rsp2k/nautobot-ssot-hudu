# Extending the App

Adding a new Nautobot entity → Hudu entity mapping. Concrete walkthrough.

## Decide on identity

Most Nautobot entities scope under a Tenant or a Company. Hudu's data model is also company-scoped, so most entities use composite identity `(company_name, <unique-key-within-company>)`.

| Pattern | Identity | Examples |
|---|---|---|
| Globally unique | `(name,)` | Company |
| Per-company unique | `(company_name, name)` | Device, Rack |
| Per-company by content | `(company_name, address)` | Network, IPAddress |
| Per-company by tag value | `(company_name, vid)` | VLAN |

Pick whichever pair is naturally unique on **both** sides — Nautobot's ORM and Hudu's API. If they don't align, you'll need to pick one canonical key and translate at adapter boundaries (similar to how IPAddresses store host-only addresses despite Nautobot recording masks).

## Create the DiffSync model

Add `src/nautobot_ssot_hudu/diffsync/models/<entity>.py`:

```python
from nautobot_ssot_hudu.diffsync.models.base import HuduSSoTModel

class Foo(HuduSSoTModel):
    """A Nautobot Foo / Hudu Foo. Identity (company_name, name)."""

    _modelname = "foo"
    _identifiers = ("company_name", "name")
    _attributes = ("description",)

    company_name: str
    name: str
    description: str | None = None


class HuduFoo(Foo):
    """Hudu-side variant with CRUD methods."""

    pk: int | None = None  # captured at load/create

    @classmethod
    def create(cls, adapter, ids, attrs):
        company = adapter.get("company", ids["company_name"])
        if company.pk is None:
            raise RuntimeError(...)  # parent must exist first
        created = adapter.client.foos.create(
            company_id=company.pk,
            name=ids["name"],
            description=attrs.get("description") or "",
        )
        instance = super().create(adapter, ids, attrs)
        instance.pk = created.id
        return instance

    def update(self, attrs):
        ...

    def delete(self):
        ...
```

Note the **empty-string-to-None coercion** discipline — `attrs.get("description") or ""` writes empty-string when None to keep Hudu's storage consistent. Both adapters then load empty values back as None for stable diffs.

## Wire into adapters

In `adapters/nautobot.py`:

```python
from nautobot.<app>.models import Foo  # the Nautobot model
from nautobot_ssot_hudu.diffsync.models.foo import Foo as FooModel

class NautobotAdapter(Adapter):
    foo = FooModel
    # add to top_level tuple in the right order:
    top_level = ("company", "device", "vlan", "network", "ipaddress",
                 "rack", "rackitem", "foo")  # foo placed where dependencies allow

    def load(self) -> None:
        self._load_companies()
        # ...
        self._load_foos()

    def _load_foos(self) -> None:
        for foo in Foo.objects.filter(tenant__isnull=False):
            self.add(self.foo(
                company_name=foo.tenant.name,
                name=foo.name,
                description=foo.description or None,  # empty-to-None
            ))
```

In `adapters/hudu.py`:

```python
from nautobot_ssot_hudu.diffsync.models.foo import HuduFoo

class HuduAdapter(Adapter):
    foo = HuduFoo
    top_level = (..., "foo")  # match Nautobot's order

    def load(self) -> None:
        self._load_companies()
        # ...
        self._load_foos()

    def _load_foos(self) -> None:
        company_by_pk = {c.pk: c for c in self.get_all("company")}
        for raw in self.client.get("foos", paginate=False) or []:
            company = company_by_pk.get(raw.get("company_id"))
            if company is None:
                continue
            instance = self.foo(
                company_name=company.name,
                name=raw["name"],
                description=raw.get("description") or None,
            )
            instance.pk = raw["id"]
            self.add(instance)
```

## top_level ordering

The order in `top_level` matters for **write order** (DiffSync's sync phase processes models in this sequence). Cross-entity references must be resolvable when the dependent entity is created — for example, IPAddresses need their parent Networks to exist, so Network comes before IPAddress.

Current order: `("company", "device", "vlan", "network", "ipaddress", "rack", "rackitem")`

If your new entity references another, place it AFTER its dependency.

## Tests

Add to `tests/test_models.py`:

```python
class TestFoo:
    def test_modelname(self):
        assert Foo._modelname == "foo"

    def test_identifiers(self):
        assert Foo._identifiers == ("company_name", "name")

    def test_construction_requires_company_and_name(self):
        with pytest.raises(ValidationError):
            Foo(name="foo")   # missing company_name


class TestHuduFoo:
    def test_inherits_from_foo(self):
        assert issubclass(HuduFoo, Foo)

    def test_pk_is_optional_int_not_in_attributes(self):
        instance = HuduFoo(company_name="X", name="foo")
        assert instance.pk is None
        assert "pk" not in HuduFoo._attributes
```

Adapter-side tests in `tests/test_adapters.py` follow the same MagicMock pattern as the existing suite — see `TestHuduAdapter*` for examples.

## Documentation

- Add a row to the [mapping table](../user/app_overview.md#what-it-syncs)
- Create `docs/models/<entity>.md` with the per-entity reference (identity, attributes, mapping notes, API quirks)
- Add a nav entry in `mkdocs.yml`
- Update the README's mapping table

## Validate against the live stack

```shell
cd development/
make restart
make nbshell
```

```python
from nautobot_ssot_hudu.diffsync.adapters.nautobot import NautobotAdapter
from nautobot_ssot_hudu.diffsync.adapters.hudu import HuduAdapter

src = NautobotAdapter(...); src.load()
tgt = HuduAdapter(...); tgt.load()

# preview
print(src.diff_to(tgt).summary())

# apply
src.sync_to(tgt)

# verify idempotency
src2 = NautobotAdapter(...); src2.load()
tgt2 = HuduAdapter(...); tgt2.load()
print(src2.diff_to(tgt2).summary())  # should be all no-change
```

If the second run shows updates instead of no-change, your adapter has a diff-stability bug — usually empty-to-None coercion missing on one side.
