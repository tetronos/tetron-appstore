"""Gates reconcile.py enforces before a commit (CON-AS*)."""
from libspec import Constraint


class GeneratedFilesCurrent(Constraint):
    """CONSTRAINT-ID: CON-AS01

    `assets/catalog.json`, `assets/suite-apps.txt` and the recommends of
    `packaging/{essentials,recommended,extras}.toml` are what
    `scripts/build_catalog.py` makes from the app and collection files
    (ASCAT-009).
    ENFORCEMENT (reconcile.py): build.current is true.
    """
    constraint_id = "CON-AS01"
    enforcement_logic = "{{ build.current }}"


class FilesValid(Constraint):
    """CONSTRAINT-ID: CON-AS02

    Every app and collection file matches its schema, ids and aliases are
    unique, a command is used by one app unless shared (ASCAT-021), every
    collection id names an app file, and no app is in two collections
    (ASCAT-020, ASCAT-021, ASCAT-022).
    ENFORCEMENT (reconcile.py): files.problems is empty.
    """
    constraint_id = "CON-AS02"
    enforcement_logic = "{{ files.problems | length == 0 }}"


class NoPlanningNotes(Constraint):
    """CONSTRAINT-ID: CON-AS03

    Committed files explain the code, the data and the reason for them; who
    decided, when, and plans stay out (they belong in the CHANGELOG and in
    notes outside git). No committed file outside an allowlist names the
    private planning directory or the owner placeholder, or carries a date
    in a comment (dates in data, such as `[source]` tables, status files,
    the imported lists in `sources/` and the CHANGELOG, are fine).
    ENFORCEMENT (reconcile.py): planning_notes.count equals 0.
    """
    constraint_id = "CON-AS03"
    enforcement_logic = "{{ planning_notes.count == 0 }}"
