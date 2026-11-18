"""Publishing requirements (ASPUB-*): catalog releases, where they are served,
the offline data package and the collection packages."""
from libspec import Requirement


class CatalogRelease(Requirement):
    """REQUIREMENT-ID: ASPUB-001

    A catalog release is a tag `catalog-YYYY.MM.DD.N` on main. Its workflow
    runs the ASCAT-020 to ASCAT-025 checks and `build_catalog.py --check`, then attaches
    `catalog.json` and `suite-apps.txt` to the GitHub release and publishes
    the same two files on GitHub Pages
    (https://tetronos.github.io/tetron-appstore/). `version` in the
    document is the tag without its prefix. There is one channel (stable):
    the latest catalog release. Releases of the Store binary keep their own
    `vX.Y.Z` tags.
    """


class OfflineDataPackage(Requirement):
    """REQUIREMENT-ID: ASPUB-002

    Each catalog release also builds `tetron-catalog-data`, a Debian package
    (Architecture all) that installs the catalog at
    `/usr/share/tetron/catalog.json`, for machines without network and for
    the TetronOS ISO. Its version is the catalog version.
    """


class CollectionPackages(Requirement):
    """REQUIREMENT-ID: ASPUB-003

    The collection metapackages `tetron-wm-essentials`,
    `tetron-wm-recommended` and `tetron-wm-extras` are built here, from
    `packaging/{essentials,recommended,extras}.toml`, whose recommends
    `build_catalog.py` writes from the collections (an app's apt name, or
    its `deb` relation; members without an apt package are left to the
    suite installer). Each depends on the next smaller one and on
    `tetron-wm (>= MAJOR.MINOR)`. Version: tetron's MAJOR.MINOR with an
    independent patch number that rises with each catalog release that
    changes a collection and never goes down, so an upgrade from the
    packages tetron-wm built before never sees a downgrade. They are
    attached to the catalog release for tetronos/apt to pick up.
    """


class DesktopCollectionOwnedHere(Requirement):
    """REQUIREMENT-ID: ASPUB-004

    `collections/desktop.toml` lists the tools tetron-wm's own features
    call. tetron-wm builds `tetron-wm-desktop` itself, reading this file
    from the catalog release at its own release time, so data flows one way:
    from this repository to tetron-wm.
    """
