"""App catalog requirements (ASCAT-*): one file per app, collections as
lists, the build that turns them into the published catalog, the checks on
every change, install tests and the importers.

tetron-appstore is the only owner of app data and collection membership.
Every program that needs either (tetron-wm, the Store, the suite installer,
the collection packages, the TetronOS ISO build) reads what this repository
publishes and keeps no list of its own."""
from libspec import Requirement


# ── App files ──────────────────────────────────────────────────────────


class OneFilePerApp(Requirement):
    """REQUIREMENT-ID: ASCAT-001

    Every app in the catalog is one TOML file `apps/<id>.toml`, imported
    apps included. What is in `apps/` is the catalog: no other input adds,
    removes or overrides an app. The format is `schema/app.schema.json`.
    """


class StableAppId(Requirement):
    """REQUIREMENT-ID: ASCAT-002

    `id` is a slug (`[a-z0-9-]`, starting with a letter or digit) equal to
    the file name. An id is never reused for another app. A renamed app
    keeps its id and lists its former ids and names in `aliases`.
    """


class AppDescriptionFields(Requirement):
    """REQUIREMENT-ID: ASCAT-003

    An app file describes the app with `name`, `bin` (the command it
    runs), `check` (how the suite installer tells it is present when that is
    not `bin`: a command on PATH, `a|b` for alternatives, `font=NAME` or
    `consolefonts`), `shares_bin` (ASCAT-021), `category`, `description`, `homepage`, `license`,
    `cli`, `requires_cwd`, `needs_url`, `group` (`apps`, `gui` or
    `services`), `store` (false for a collection member not shown as a Store
    app; such a file needs only `name`), `[notes]` (`tip`; `how`, what the
    suite installer's method does), `[variants]` and `[agent]`.
    """


class AppInstallTable(Requirement):
    """REQUIREMENT-ID: ASCAT-004

    An app file says how to install the app in one `[install]` table:
    `pkg` names per manager (apt, dnf, pacman, brew; `""` means none there,
    a missing manager is looked up in `sources/repology.json`), `release`
    (`repo`, and `amd64` and `arm64` asset patterns where `*` matches the
    version), `recipe` (`method`, `install`, `os`), `deb` (a Recommends
    relation that is not the apt name) and `script` (the name of the suite
    installer's own method for an app no distribution packages).
    """


class SourceTableForImporters(Requirement):
    """REQUIREMENT-ID: ASCAT-005

    An app file's `[source]` table records which upstream lists carry the
    app and when an importer last saw it there. Only importers write it
    (ASCAT-018); every other field is written by people.
    """


# ── Collections ────────────────────────────────────────────────────────


class CollectionFile(Requirement):
    """REQUIREMENT-ID: ASCAT-006

    A collection is one TOML file `collections/<name>.toml`: `name`,
    `description`, `includes` (the next smaller collection, absent for the
    smallest) and `apps`, an ordered list of app ids, each line with an
    optional comment saying why the app is there. Adding an app to a
    collection is one line in one file. The format is
    `schema/collection.schema.json`.
    """


class TheFourCollections(Requirement):
    """REQUIREMENT-ID: ASCAT-007

    The collections are `desktop` (the tools tetron-wm's own features
    call), `essentials` (includes desktop), `recommended` (includes
    essentials) and `extras` (includes recommended).
    """


class CollectionOrderAndMembership(Requirement):
    """REQUIREMENT-ID: ASCAT-008

    The order of `apps` in a collection file is the order shown to users. An
    app is in at most one collection; a larger collection reaches it through
    `includes`.
    """


# ── Build ──────────────────────────────────────────────────────────────


class BuildFromFilesOnly(Requirement):
    """REQUIREMENT-ID: ASCAT-009

    `scripts/build_catalog.py` (stdlib, Python 3.11+) reads only `apps/`,
    `collections/`, `status/`, `sources/repology.json` (package names) and
    `sources/releases.json` (repositories with release binaries), and writes
    `assets/catalog.json`, `assets/suite-apps.txt` and the recommends of
    `packaging/{essentials,recommended,extras}.toml` (ASPUB-003).
    Generated files are committed and never edited by hand.
    """


class DeterministicBuild(Requirement):
    """REQUIREMENT-ID: ASCAT-010

    The same input files give the same output bytes: entries sorted by
    category, then name; keys in a fixed order; no time or machine in the
    output.
    """


class BuildCheckMode(Requirement):
    """REQUIREMENT-ID: ASCAT-011

    `build_catalog.py --check` writes nothing; it exits 1 and names each
    generated file that differs from what the inputs give, else exits 0.
    """


class CatalogDocument(Requirement):
    """REQUIREMENT-ID: ASCAT-012

    `assets/catalog.json` is one document: `schema` (`"MAJOR.MINOR"`),
    `version` (the catalog release, ASPUB-001), `apps` (one entry per app
    file shown in the Store, with `id`, its `collection` when it is in one,
    and its `status` from ASCAT-016), `collections` (name, description,
    includes, app ids in order, and the Debian Recommends of its
    metapackage, ASPUB-003) and `suite_apps` (ASCAT-014), so one fetch
    updates the Store and the collections together. Until the client of
    ASCLI-001 is released, `schema` stays the integer 1 the released clients
    parse, and the entries keep the fields they read (`tier` and `set` from
    the collection, `sources`, `releases`, `pkg`, `recipe`).
    """


class SchemaVersioning(Requirement):
    """REQUIREMENT-ID: ASCAT-013

    A new schema minor only adds optional fields that old clients can
    ignore. Anything else (a removed or renamed field, a changed meaning)
    raises the major, which old clients refuse (ASCLI-001).
    """


class SuiteListFormatUnchanged(Requirement):
    """REQUIREMENT-ID: ASCAT-014

    `assets/suite-apps.txt` keeps the format tetron-wm's suite installer
    reads (one `size:group:check:apt:dnf:pacman:brew`, `size:script:name`
    or `size:release:check:repo:amd64:arm64` line per member, `#`
    comments), generated from the collections and the app files, so a suite
    installer released before this change installs the same apps for each
    size.
    """


# ── Install tests and status ───────────────────────────────────────────


class ScheduledInstallTests(Requirement):
    """REQUIREMENT-ID: ASCAT-015

    A scheduled workflow (weekly, and on a pull request that changes a
    collection) installs every collection member, and a rotating sample of
    the other apps, in Debian 13 and Ubuntu 24.04 containers with the code
    path of the suite installer, then runs its check command. Each result
    per app and platform is `ok`, `fail` or `skipped`, with the date, the
    method used and the last lines of output on failure. `skipped` carries
    its reason: an app the platform can not install by the suite's own
    rules (a desktop app, a service, no apt package there and no release or
    script to fall back on) is skipped, not failed, so the status shows the
    gap per platform without blocking unrelated pull requests. The full result of
    each run is attached to the run as an artifact.
    """


class StatusChangesOnlyOnFlip(Requirement):
    """REQUIREMENT-ID: ASCAT-016

    `status/<id>.json` changes only when an app's result on a platform flips
    (ok to fail, fail to ok, or a first result). Those changes reach the
    repository by a bot pull request a maintainer merges, never by a direct
    commit. The Store shows the tested status. The hand-written `verified`
    of a recipe stays only until the released Store reads status instead;
    it is then removed.
    """


class UpstreamHealth(Requirement):
    """REQUIREMENT-ID: ASCAT-017

    The same run records upstream health in the status file: repository
    archived, no release for 18 months, homepage gone. A collection member
    that fails to install or is flagged opens or updates an issue.
    """


# ── Importers ──────────────────────────────────────────────────────────


class ImportersProposeOnly(Requirement):
    """REQUIREMENT-ID: ASCAT-018

    The import scripts (awesome-tuis, Terminal Trove, Repology, GitHub
    releases) refresh `sources/*.json`, write new app files and update only
    the `[source]` table of existing ones, on a branch, and open or update
    one pull request. They never commit to main and never change a field
    outside `[source]`.
    """


class ImportsNeverDelete(Requirement):
    """REQUIREMENT-ID: ASCAT-019

    An app that left every upstream list is marked in its `[source]` table
    and kept. No import deletes an app file.
    """


# ── Checks on every change ─────────────────────────────────────────────


class CheckSchemas(Requirement):
    """REQUIREMENT-ID: ASCAT-020

    CI fails, naming the file and the field, when an app or collection file
    does not match its schema.
    """


class CheckUniqueness(Requirement):
    """REQUIREMENT-ID: ASCAT-021

    CI fails when an id or alias is used by two apps, or a command (`bin`
    or a `check` alternative) by two apps that do not both name the other in
    `shares_bin` (different apps that install the same command; the Store
    can not tell which one is installed).
    """


class CheckCollectionReferences(Requirement):
    """REQUIREMENT-ID: ASCAT-022

    CI fails when a collection names an id that has no app file, or an app
    sits in two collections.
    """


class CheckReleaseAssets(Requirement):
    """REQUIREMENT-ID: ASCAT-023

    CI fails when an `[install.release]` repository has no asset matching
    the amd64 or arm64 pattern in its latest release. Only app files the
    pull request changes are checked, and results are cached, to stay
    within the GitHub API limits.
    """


class CheckGeneratedFiles(Requirement):
    """REQUIREMENT-ID: ASCAT-024

    CI fails when `build_catalog.py --check` fails (ASCAT-011).
    """


class ScriptRecipesNeedReview(Requirement):
    """REQUIREMENT-ID: ASCAT-025

    A recipe with `method = "script"` (a downloaded script run by a shell)
    runs code no checksum covers. CI fails when a pull request adds or
    changes one without the `reviewed-script` label. A change means a
    different command or method; other recipe fields (os, notes) do not need
    the label. A recipe the catalog already carried before the one-file-per-app
    migration, unchanged, is not new.
    """


# ── Contributing ───────────────────────────────────────────────────────


class NewAppHelper(Requirement):
    """REQUIREMENT-ID: ASCAT-026

    `scripts/tetron-app new <github-url>` writes `apps/<id>.toml` from the
    repository's metadata (name, description, license, homepage) and its
    latest release assets (amd64 and arm64 patterns), leaving `category` and
    `tip` for the contributor to fill in.
    """


class AddToCollectionHelper(Requirement):
    """REQUIREMENT-ID: ASCAT-027

    `scripts/tetron-app add-to <collection> <id>` appends the id to the
    collection file; `scripts/tetron-app check` runs the ASCAT-020 to
    ASCAT-025 checks locally.
    """


# ── Migration ──────────────────────────────────────────────────────────


class MigrationScript(Requirement):
    """REQUIREMENT-ID: ASCAT-028

    A one-time script writes `apps/` and `collections/` from the merged
    catalog and tetron-wm's app sets. The old merge inputs
    (`lists/tetron.toml`, `scripts/merge_catalog.py`,
    `scripts/sync_suite_list.sh`) leave the build in the same change; the
    imported lists move to `sources/`.
    """


class MigrationKeepsTheCatalog(Requirement):
    """REQUIREMENT-ID: ASCAT-029

    A test proves the first catalog built from the files equals the catalog
    before the move: every app and field, and the same `suite_apps` lines
    per size, apart from the fields this spec adds (`id`, `collection`,
    `collections`) and a short list of named changes the test carries, each
    with its reason: a collection member's package names are the ones its
    suite line used (checked in containers), `tier` follows the collection,
    `sources` names each list once, and the order and header of the suite
    lines.
    """
