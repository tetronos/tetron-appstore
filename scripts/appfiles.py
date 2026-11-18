"""The app and collection files (ASCAT-001 to ASCAT-008): read, check against
schema/, and write them back in one fixed layout. Stdlib only (Python 3.11+).

The recipe tools (match_brew.py, match_lang_recipes.py, merge_recipes.py,
derive_os.py) write their recipes into apps/<id>.toml with save_recipes().
"""
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS = ROOT / "apps"
COLLECTIONS = ROOT / "collections"
SCHEMA = ROOT / "schema"
CATALOG = ROOT / "assets" / "catalog.json"
MANAGERS = ("apt", "dnf", "pacman", "brew")
# Collections, smallest first; each includes the one before it (ASCAT-007).
COLLECTION_NAMES = ("desktop", "essentials", "recommended", "extras")

# The layout of an app file: top-level keys, then tables, in this order.
TOP = ("id", "aliases", "name", "bin", "check", "category", "description", "homepage", "license",
       "cli", "requires_cwd", "needs_url", "group", "store")
TABLES = ("notes", "variants", "agent", "install", "source")
SUB = {
    "notes": ("tip", "how"),
    "agent": ("label", "command", "args", "context_files", "briefing", "mcp"),
    "install": ("pkg", "release", "recipe", "deb", "script"),
    "source": ("lists", "seen", "gone"),
    "pkg": MANAGERS,
    "release": ("repo", "amd64", "arm64"),
    "recipe": ("install", "method", "os", "verified"),
    "briefing": ("file", "template", "args", "env"),
    "mcp": ("file", "template", "args", "env"),
    "variants": ("suffix", "args", "warn"),
}


class FileError(Exception):
    pass


def slug(name: str) -> str:
    """A file id from a name: lower case, runs of other characters become '-'."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "app"


def gh_repo(url):
    """owner/repo (lower case) of a github.com repository root URL, else None."""
    m = re.fullmatch(r"https?://(?:www\.)?github\.com/([^/?#]+/[^/?#]+?)/?", url or "", re.I)
    return m.group(1).lower().removesuffix(".git") if m else None


# ── Schema check (the subset of JSON Schema schema/ uses) ──────────────


def _schema(name):
    return json.loads((SCHEMA / name).read_text(encoding="utf-8"))


def validate(doc, schema, root=None, path=""):
    """Problems of doc against schema, as "field: message" strings."""
    root = root or schema
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].rsplit("/", 1)[1]]
    out = []
    t = schema.get("type")
    kinds = {"object": dict, "array": list, "string": str, "boolean": bool}
    if t and not isinstance(doc, kinds[t]):
        return [f"{path or '.'}: must be a{'n' if t[0] in 'ao' else ''} {t}"]
    if "enum" in schema and doc not in schema["enum"]:
        out.append(f"{path}: must be one of {schema['enum']}")
    if "const" in schema and doc != schema["const"]:
        out.append(f"{path}: must be {schema['const']!r}")
    if isinstance(doc, str):
        if len(doc) < schema.get("minLength", 0):
            out.append(f"{path}: must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            out.append(f"{path}: {doc!r} does not match {schema['pattern']}")
    if isinstance(doc, list):
        for i, v in enumerate(doc):
            out += validate(v, schema.get("items", {}), root, f"{path}[{i}]")
    if isinstance(doc, dict):
        props = schema.get("properties", {})
        out += [f"{path + '.' if path else ''}{k}: required" for k in schema.get("required", []) if k not in doc]
        extra = schema.get("additionalProperties", True)
        for k, v in doc.items():
            p = f"{path}.{k}" if path else k
            if k in props:
                out += validate(v, props[k], root, p)
            elif extra is False:
                out.append(f"{p}: unknown field")
            elif isinstance(extra, dict):
                out += validate(v, extra, root, p)
    if "if" in schema and not _fails(doc, schema["if"], root):
        out += validate(doc, schema.get("then", {}), root, path)
    return out


def _fails(doc, schema, root):
    if "not" in schema:
        return not _fails(doc, schema["not"], root)
    return bool(validate(doc, schema, root))


# ── Reading ────────────────────────────────────────────────────────────


def load_apps(apps_dir=APPS):
    """{id: app} of every apps/<id>.toml; FileError lists every problem."""
    schema, apps, problems = _schema("app.schema.json"), {}, []
    for p in sorted(Path(apps_dir).glob("*.toml")):
        try:
            doc = tomllib.loads(p.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            problems.append(f"apps/{p.name}: {e}")
            continue
        problems += [f"apps/{p.name}: {m}" for m in validate(doc, schema)]
        if doc.get("id") != p.stem:
            problems.append(f"apps/{p.name}: id must be {p.stem!r}, the file name")
        apps[p.stem] = doc
    if problems:
        raise FileError("\n".join(problems))
    return apps


def load_collections(coll_dir=COLLECTIONS):
    """[collection] in COLLECTION_NAMES order (each file must exist)."""
    schema, out, problems = _schema("collection.schema.json"), [], []
    for i, name in enumerate(COLLECTION_NAMES):
        p = Path(coll_dir) / f"{name}.toml"
        if not p.exists():
            problems.append(f"collections/{name}.toml: missing")
            continue
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
        problems += [f"collections/{p.name}: {m}" for m in validate(doc, schema)]
        if doc.get("name") != name:
            problems.append(f"collections/{p.name}: name must be {name!r}")
        want = COLLECTION_NAMES[i - 1] if i else None
        if doc.get("includes") != want:
            problems.append(f"collections/{p.name}: includes must be {want!r}")
        out.append(doc)
    if problems:
        raise FileError("\n".join(problems))
    return out


# ── Writing ────────────────────────────────────────────────────────────


def _val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_key(k)} = {_val(x)}" for k, x in v.items()) + " }"
    raise TypeError(f"no TOML form for {v!r}")


def _key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k, ensure_ascii=False)


def _ordered(d, order):
    unknown = set(d) - set(order)
    if unknown:
        raise FileError(f"no place in the file layout for {sorted(unknown)}")
    return [(k, d[k]) for k in order if k in d]


def _table(name, d, order):
    """[name] with its plain keys, then its sub-tables."""
    plain = [(k, v) for k, v in _ordered(d, order) if not (isinstance(v, dict) and k in SUB)]
    subs = [(k, v) for k, v in _ordered(d, order) if isinstance(v, dict) and k in SUB]
    lines = [f"[{name}]"] + [f"{_key(k)} = {_val(v)}" for k, v in plain] if plain or not subs else []
    for k, v in subs:
        lines += ([""] if lines else []) + _table(f"{name}.{k}", v, SUB[k])
    return lines


def dump_app(app):
    """The text of apps/<id>.toml for app, in the fixed layout."""
    lines = [f"{_key(k)} = {_val(v)}" for k, v in _ordered({k: v for k, v in app.items() if k not in TABLES}, TOP)]
    for t in TABLES:
        if t not in app:
            continue
        if t == "variants":
            for v in app[t]:
                lines += ["", "[[variants]]"] + [f"{_key(k)} = {_val(x)}" for k, x in _ordered(v, SUB["variants"])]
        else:
            lines += [""] + _table(t, app[t], SUB[t])
    return "\n".join(lines) + "\n"


def dump_collection(c, why=None):
    """The text of collections/<name>.toml; why maps an id to its line comment."""
    why = why or {}
    lines = [f"name = {_val(c['name'])}", f"description = {_val(c['description'])}"]
    if c.get("includes"):
        lines.append(f"includes = {_val(c['includes'])}")
    lines.append("apps = [")
    for i in c["apps"]:
        lines.append(f"  {_val(i)},{'  # ' + why[i] if why.get(i) else ''}")
    return "\n".join(lines) + "\n]\n"


def write_app(app, apps_dir=APPS):
    (Path(apps_dir) / f"{app['id']}.toml").write_text(dump_app(app), encoding="utf-8")


# ── Recipe tools ───────────────────────────────────────────────────────


def catalog_recipes():
    """{name: recipe} from assets/catalog.json (for the recipe tools)."""
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {a["name"]: a["recipe"] for a in doc["apps"] if "recipe" in a}


def save_recipes(before, after, apps_dir=APPS):
    """Write every recipe in after that differs from before into its app
    file (requires_cwd and tip go to the app and its notes), then build the
    catalog again. Returns how many were written."""
    by_name = {a["name"]: a for a in load_apps(apps_dir).values()}
    n = 0
    for name, r in sorted(after.items()):
        if before.get(name) == r:
            continue
        app = by_name.get(name)
        if app is None:
            raise FileError(f"{name}: no app file")
        r = dict(r)
        if "requires_cwd" in r:
            app["requires_cwd"] = r.pop("requires_cwd")
        if "tip" in r:
            app.setdefault("notes", {})["tip"] = r.pop("tip")
        app.setdefault("install", {})["recipe"] = r
        write_app(app, apps_dir)
        n += 1
    if n:
        import build_catalog
        build_catalog.write()
    return n
