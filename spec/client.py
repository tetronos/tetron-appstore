"""Client library requirements (ASCLI-*): how `crates/tetron-catalog` finds,
updates and falls back between catalog copies."""
from libspec import Requirement


class LoadOrder(Requirement):
    """REQUIREMENT-ID: ASCLI-001

    The catalog in use is the first of these that parses, has a schema
    major this build knows and passes the trust step (ASCLI-004): the
    downloaded copy (`$XDG_DATA_HOME/tetron-wm/catalog.json`), the last
    good copy (`catalog.json.good` next to it), the packaged copy
    (`/usr/share/tetron/catalog.json`, ASPUB-002), the built-in copy
    compiled into the binary. The built-in copy always works, so a client
    without network, with a damaged download or with a too new catalog
    still has apps and collections.
    """


class SafeUpdate(Requirement):
    """REQUIREMENT-ID: ASCLI-002

    An update downloads the latest catalog release over HTTPS from the
    GitHub release (the newest `catalog-*` tag; catalog releases are not
    marked latest, which stays the Store binary's), else from GitHub Pages
    (ASPUB-001), else from the per-minor list of the tetronos apt
    repository while it is published, into a `.part` file, reads it back
    and checks it as ASCLI-001 does, keeps the current copy as `.good` when
    that copy is usable, then renames. A download that fails any check is
    dropped and the current copy stays in use. `TETRON_WM_LISTS_URL`
    replaces every source with that per-minor list (tests).
    """


class NewerSchemaKeptOut(Requirement):
    """REQUIREMENT-ID: ASCLI-005

    A downloaded catalog with a schema major this build does not know is
    not used; the current copy stays, and the Store and Settings say a
    newer tetron-wm shows newer apps.
    """


class UpdateSchedule(Requirement):
    """REQUIREMENT-ID: ASCLI-006

    Updates run on the manual Update (Store, Settings) and on their own at
    most once a day (a `catalog.json.checked` stamp next to the download,
    touched by every attempt, so a failing source is not retried at each
    start).
    """


class CollectionsApi(Requirement):
    """REQUIREMENT-ID: ASCLI-003

    The crate exposes the collections (`collections()`, in order, with what
    each includes) and an app's collection (`collection_of(id)`), read from
    the document's `collections`, so tetron-wm's Settings > App
    Collections, its assistant and the Store use the catalog's collections
    and no list of their own.
    """


class TrustStep(Requirement):
    """REQUIREMENT-ID: ASCLI-004

    Every copy passes one trust function before use. In this version it
    accepts copies fetched over HTTPS from the tetronos GitHub URLs of
    ASPUB-001 and the packaged and built-in copies; signature verification
    is added to this function later without a change to the catalog format.
    """
