//! Where the catalog in use comes from and how it is replaced (ASCLI-001,
//! ASCLI-002, ASCLI-004 to ASCLI-006).
//!
//! Load order: the downloaded copy ([`download_path`]), the last good copy
//! next to it (`catalog.json.good`), the packaged copy ([`PACKAGED`], the
//! tetron-catalog-data deb), the built-in copy. The first that parses, has
//! a schema major this build knows and passes [`trust`] is used.
//!
//! An update fetches the latest catalog release from GitHub, else GitHub
//! Pages, else the older per-minor list of the tetronos apt repository; it is
//! written to a `.part` file, read back and checked, the current copy becomes
//! `.good`, and the `.part` is renamed into place. A copy that fails any check
//! is dropped and the current one stays.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, SystemTime};

/// The packaged copy (ASPUB-002).
pub const PACKAGED: &str = "/usr/share/tetron/catalog.json";

const REPO: &str = "tetronos/tetron-appstore";
const RELEASES_API: &str = "https://api.github.com/repos/tetronos/tetron-appstore/releases?per_page=30";
const PAGES: &str = "https://tetronos.github.io/tetron-appstore/catalog.json";
/// The per-minor list the apt repository publishes (`<base>/0.15/catalog.json`),
/// used until every client reads the catalog releases.
pub const LISTS_BASE: &str = "https://tetronos.github.io/apt/lists";

/// Where the copies accepted by [`trust`] may be fetched from (ASCLI-004).
const TRUSTED: [&str; 3] = [
    "https://github.com/tetronos/tetron-appstore/releases/download/",
    "https://tetronos.github.io/tetron-appstore/",
    "https://tetronos.github.io/apt/lists/",
];

/// How often the automatic check runs (ASCLI-006).
pub const DAILY: Duration = Duration::from_secs(24 * 60 * 60);

/// Where a copy comes from, for [`trust`].
#[derive(Clone, Debug, PartialEq)]
pub enum Origin {
    /// Fetched now from this URL.
    Fetched(String),
    /// Fetched from `TETRON_WM_LISTS_URL`, which the user set.
    Override(String),
    /// A copy saved by an earlier update (the download or `.good`).
    Saved,
    /// The tetron-catalog-data deb.
    Packaged,
    /// Compiled into this binary.
    Builtin,
}

/// The one check every copy passes before use (ASCLI-004). This version
/// accepts copies fetched over HTTPS from the tetronos GitHub URLs, copies an
/// earlier update saved after passing it, and the packaged and built-in
/// copies. Signature verification goes here later, with no change to the
/// catalog format.
pub fn trust(origin: &Origin, _text: &str) -> Result<(), String> {
    match origin {
        Origin::Fetched(url) if !TRUSTED.iter().any(|t| url.starts_with(t)) => Err(format!("{url} is not a tetronos catalog URL")),
        _ => Ok(()),
    }
}

/// The downloaded copy: `$XDG_DATA_HOME/tetron-wm/catalog.json`.
pub fn download_path() -> Option<PathBuf> {
    crate::data_home_dir().map(|d| d.join("tetron-wm/catalog.json"))
}

/// The last good copy kept next to `download`.
pub fn good_path(download: &Path) -> PathBuf {
    download.with_extension("json.good")
}

fn part_path(download: &Path) -> PathBuf {
    download.with_extension("json.part")
}

fn stamp_path(download: &Path) -> PathBuf {
    download.with_extension("json.checked")
}

static NEWER: AtomicBool = AtomicBool::new(false);

/// Whether a catalog with a newer schema major was seen and left out
/// (ASCLI-005): the Store and Settings say so.
pub fn newer_seen() -> bool {
    NEWER.load(Ordering::Relaxed)
}

/// What the Store and Settings show while [`newer_seen`].
pub const NEWER_NOTE: &str = "A newer catalog needs a newer tetron-wm or tetron-appstore; update to see newer apps";

/// [`crate::parse`] and [`trust`], noting a newer schema major.
pub fn check(text: &str, origin: &Origin) -> Result<crate::Catalog, String> {
    if crate::schema_major(text).is_some_and(|m| m > crate::SCHEMA as u64) {
        NEWER.store(true, Ordering::Relaxed);
    }
    let c = crate::parse(text)?;
    trust(origin, text)?;
    Ok(c)
}

/// The first usable copy of `files` (in order), else the built-in one
/// (ASCLI-001); with the origin it came from.
pub fn load(files: &[(PathBuf, Origin)], log: impl Fn(&str)) -> (crate::Catalog, Origin) {
    for (path, origin) in files {
        let Ok(text) = std::fs::read_to_string(path) else { continue };
        match check(&text, origin) {
            Ok(c) => return (c, origin.clone()),
            Err(e) => log(&format!("catalog: {} not used ({e})", path.display())),
        }
    }
    (crate::builtin(), Origin::Builtin)
}

/// The copies in load order on this machine.
pub fn load_order() -> Vec<(PathBuf, Origin)> {
    let mut v = Vec::new();
    if let Some(d) = download_path() {
        v.push((good_path(&d), Origin::Saved));
        v.insert(0, (d, Origin::Saved));
    }
    v.push((PathBuf::from(PACKAGED), Origin::Packaged));
    v
}

/// Check `text` and make it the downloaded copy at `download` (ASCLI-002):
/// written to `.part`, read back and checked, the current copy kept as
/// `.good` when it is usable, then renamed into place. Returns the catalog.
pub fn save(download: &Path, text: &str, origin: &Origin) -> Result<crate::Catalog, String> {
    check(text, origin)?;
    if let Some(d) = download.parent() {
        std::fs::create_dir_all(d).map_err(|e| format!("could not create {}: {e}", d.display()))?;
    }
    let part = part_path(download);
    let fail = |e: std::io::Error| format!("could not save {}: {e}", download.display());
    std::fs::write(&part, text).map_err(fail)?;
    let c = match std::fs::read_to_string(&part).map_err(fail).and_then(|t| check(&t, origin)) {
        Ok(c) => c,
        Err(e) => {
            let _ = std::fs::remove_file(&part);
            return Err(e);
        }
    };
    let current_ok = std::fs::read_to_string(download).is_ok_and(|t| check(&t, &Origin::Saved).is_ok());
    if current_ok {
        std::fs::rename(download, good_path(download)).map_err(fail)?;
    }
    std::fs::rename(&part, download).map_err(fail)?;
    Ok(c)
}

/// Fetch `url` with curl over HTTPS only; the body, or why not.
fn fetch(url: &str) -> Result<String, String> {
    let o = Command::new("curl")
        .args(["-fsSL", "--proto", "=https", "--proto-redir", "=https", "--max-time", "25", "-H", "User-Agent: tetron-catalog", url])
        .output()
        .map_err(|e| format!("curl: {e}"))?;
    if !o.status.success() {
        return Err(format!("{url}: download failed"));
    }
    String::from_utf8(o.stdout).map_err(|_| format!("{url}: not text"))
}

/// The tag of the newest published catalog release in a GitHub releases
/// listing (`catalog-YYYY.MM.DD.N`, not a draft or prerelease).
pub fn latest_catalog_tag(listing: &str) -> Option<String> {
    let v: serde_json::Value = serde_json::from_str(listing).ok()?;
    v.as_array()?
        .iter()
        .filter(|r| !r["draft"].as_bool().unwrap_or(true) && !r["prerelease"].as_bool().unwrap_or(true))
        .filter_map(|r| r["tag_name"].as_str())
        .filter(|t| t.strip_prefix("catalog-").is_some_and(|d| !d.is_empty() && d.chars().all(|c| c.is_ascii_digit() || c == '.')))
        .max_by_key(|t| t.trim_start_matches("catalog-").split('.').map(|n| n.parse::<u64>().unwrap_or(0)).collect::<Vec<_>>())
        .map(str::to_string)
}

/// The per-minor list URL: `<base>/<major.minor>/catalog.json`.
pub fn lists_url(base: &str) -> String {
    let minor: Vec<&str> = env!("CARGO_PKG_VERSION").split('.').take(2).collect();
    format!("{}/{}/catalog.json", base.trim_end_matches('/'), minor.join("."))
}

/// The sources an update tries, in order (ASCLI-002).
fn sources() -> Vec<Origin> {
    if let Some(base) = std::env::var("TETRON_WM_LISTS_URL").ok().filter(|v| !v.is_empty()) {
        return vec![Origin::Override(lists_url(&base))];
    }
    let mut v = Vec::new();
    if let Some(tag) = fetch(RELEASES_API).ok().as_deref().and_then(latest_catalog_tag) {
        v.push(Origin::Fetched(format!("https://github.com/{REPO}/releases/download/{tag}/catalog.json")));
    }
    v.push(Origin::Fetched(PAGES.into()));
    v.push(Origin::Fetched(lists_url(LISTS_BASE)));
    v
}

/// Download, check and keep the latest catalog, and use it from now on
/// (ASCLI-002). Returns the number of apps, or why the current copy stays.
pub fn update() -> Result<usize, String> {
    let download = download_path().ok_or("no data directory")?;
    if let Some(p) = std::fs::File::create(stamp_path(&download)).err() {
        crate::log(&format!("catalog: could not stamp the update check ({p})"));
    }
    let mut why = String::from("no source");
    for origin in sources() {
        let url = match &origin {
            Origin::Fetched(u) | Origin::Override(u) => u.clone(),
            _ => continue,
        };
        let r = fetch(&url).and_then(|t| save(&download, &t, &origin));
        match r {
            Ok(c) => {
                crate::log(&format!("catalog: updated from {url}, {} apps", c.apps.len()));
                return Ok(crate::use_catalog(c));
            }
            Err(e) => {
                crate::log(&format!("catalog: {url} not used ({e})"));
                why = e;
                if newer_seen() {
                    return Err(NEWER_NOTE.into());
                }
            }
        }
    }
    Err(why)
}

/// Whether the automatic update is due: no check in the last day
/// (ASCLI-006). Off in tests and with the builtin-only feature.
pub fn due() -> bool {
    if cfg!(any(test, feature = "builtin-only")) {
        return false;
    }
    let Some(d) = download_path() else { return false };
    let last = std::fs::metadata(stamp_path(&d)).and_then(|m| m.modified()).ok();
    last.is_none_or(|t| SystemTime::now().duration_since(t).map_or(true, |a| a >= DAILY))
}

#[cfg(test)]
mod tests {
    use super::*;

    const APP: &str = r#"{"name":"x","bin":"x","category":"c","description":"d","homepage":"h"}"#;

    fn doc(schema: &str, n: usize) -> String {
        let apps = vec![APP; n].join(",");
        format!(r#"{{"schema":{schema},"apps":[{apps}],"suite_apps":"desktop:apps:x:x:x:x:x\n"}}"#).replace('\n', "\\n")
    }

    fn dir(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("tetron-catalog-test-{}-{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    fn files(d: &Path) -> Vec<(PathBuf, Origin)> {
        let dl = d.join("catalog.json");
        vec![(dl.clone(), Origin::Saved), (good_path(&dl), Origin::Saved), (d.join("packaged.json"), Origin::Packaged)]
    }

    /// ASCLI-001: the download, else `.good`, else the packaged copy, else
    /// the built-in one; a damaged or too new copy is passed over.
    #[test]
    fn load_order_passes_over_bad_and_newer_copies() {
        let d = dir("order");
        let n = |d: &Path| load(&files(d), |_| {}).0.apps.len();
        assert!(n(&d) > 600, "nothing on disk: built-in");
        std::fs::write(d.join("packaged.json"), doc("1", 3)).unwrap();
        assert_eq!(n(&d), 3);
        std::fs::write(d.join("catalog.json.good"), doc("1", 2)).unwrap();
        assert_eq!(n(&d), 2);
        std::fs::write(d.join("catalog.json"), doc("1", 1)).unwrap();
        assert_eq!(load(&files(&d), |_| {}).1, Origin::Saved);
        assert_eq!(n(&d), 1);
        std::fs::write(d.join("catalog.json"), "<html>").unwrap();
        assert_eq!(n(&d), 2);
        std::fs::write(d.join("catalog.json"), doc("\"2.0\"", 1)).unwrap();
        assert_eq!(n(&d), 2);
        assert!(newer_seen());
        std::fs::write(d.join("catalog.json"), doc("\"1.4\"", 1)).unwrap();
        assert_eq!(n(&d), 1, "a newer minor is read");
        std::fs::remove_dir_all(&d).unwrap();
    }

    /// ASCLI-002: a good download replaces the current copy, which becomes
    /// `.good`; a bad one changes nothing and leaves no `.part`.
    #[test]
    fn save_keeps_the_old_copy_and_drops_a_bad_one() {
        let d = dir("save");
        let dl = d.join("t/catalog.json");
        let url = Origin::Fetched(PAGES.into());
        assert_eq!(save(&dl, &doc("1", 1), &url).unwrap().apps.len(), 1);
        assert!(!good_path(&dl).exists(), "nothing to keep yet");
        save(&dl, &doc("1", 2), &url).unwrap();
        assert_eq!(std::fs::read_to_string(good_path(&dl)).unwrap(), doc("1", 1));
        assert!(save(&dl, "{}", &url).is_err());
        assert!(save(&dl, &doc("2", 5), &url).is_err());
        assert!(save(&dl, &doc("1", 5), &Origin::Fetched("https://example.org/catalog.json".into())).unwrap_err().contains("not a tetronos"));
        assert_eq!(std::fs::read_to_string(&dl).unwrap(), doc("1", 2));
        assert_eq!(std::fs::read_to_string(good_path(&dl)).unwrap(), doc("1", 1));
        assert!(!part_path(&dl).exists());
        std::fs::write(&dl, "damaged").unwrap();
        save(&dl, &doc("1", 3), &url).unwrap();
        assert_eq!(std::fs::read_to_string(good_path(&dl)).unwrap(), doc("1", 1), "a damaged copy never becomes .good");
        std::fs::remove_dir_all(&d).unwrap();
    }

    /// ASCLI-004: fetched copies only from the tetronos URLs.
    #[test]
    fn trust_accepts_the_tetronos_urls_only() {
        let ok = |u: &str| trust(&Origin::Fetched(u.into()), "").is_ok();
        assert!(ok("https://github.com/tetronos/tetron-appstore/releases/download/catalog-2026.11.17.1/catalog.json"));
        assert!(ok(PAGES) && ok(&lists_url(LISTS_BASE)));
        assert!(!ok("http://tetronos.github.io/tetron-appstore/catalog.json"));
        assert!(!ok("https://github.com/someone/tetron-appstore/releases/download/x/catalog.json"));
        assert!(!ok("https://tetronos.github.io.evil.org/tetron-appstore/catalog.json"));
        assert!([Origin::Saved, Origin::Packaged, Origin::Builtin, Origin::Override("http://localhost/x".into())].iter().all(|o| trust(o, "").is_ok()));
    }

    #[test]
    fn latest_catalog_tag_skips_store_releases_drafts_and_prereleases() {
        let r = |t: &str, draft: bool, pre: bool| format!(r#"{{"tag_name":"{t}","draft":{draft},"prerelease":{pre}}}"#);
        let listing = format!(
            "[{}]",
            [r("v0.15.9", false, false), r("catalog-2026.11.9.1", false, false), r("catalog-2026.11.17.2", false, false), r("catalog-2026.11.17.10", false, false), r("catalog-2026.12.1.1", true, false), r("catalog-2026.12.2.1", false, true), r("catalog-x/../y", false, false)].join(",")
        );
        assert_eq!(latest_catalog_tag(&listing).as_deref(), Some("catalog-2026.11.17.10"));
        assert_eq!(latest_catalog_tag("[]"), None);
        assert_eq!(latest_catalog_tag("rate limited"), None);
    }

    #[test]
    fn lists_url_is_per_minor() {
        assert!(lists_url("https://e.org/lists/").starts_with("https://e.org/lists/0."));
        assert!(lists_url(LISTS_BASE).ends_with("/catalog.json"));
    }

    /// A real update over the network into `$TETRON_TEST_DATA`:
    /// `TETRON_TEST_DATA=DIR cargo test -p tetron-catalog -- --ignored network`.
    #[test]
    #[ignore]
    fn network_update() {
        let d = PathBuf::from(std::env::var("TETRON_TEST_DATA").expect("TETRON_TEST_DATA"));
        std::env::set_var("XDG_DATA_HOME", &d);
        for o in sources() {
            println!("source {o:?}");
        }
        let n = update().expect("update");
        println!("updated: {n} apps");
        let n2 = update().expect("second update");
        assert_eq!(n, n2);
        assert!(good_path(&download_path().unwrap()).exists());
    }
}

