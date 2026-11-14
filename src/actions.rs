//! What the Store does with an app or a link. Inside tetron-wm (it sets
//! `TETRON_WM_SESSION` for its apps) installs, launches and browsers open in
//! tetron-wm windows through `tetron-wm msg`; elsewhere they run in this
//! terminal and the Store comes back when they end. Copy sets the clipboard
//! with OSC 52, which tetron-wm records and passes on to the real terminal.

use base64::Engine;
use std::process::Command;
use tetron_catalog::CatalogApp;

/// Terminal web browsers that open a URL given as their argument, first wins.
pub const WEB_BROWSERS: [&str; 5] = tetron_catalog::WEB_BROWSERS;

/// Whether this Store runs inside a tetron-wm window.
pub fn in_tetron_wm() -> bool {
    std::env::var_os("TETRON_WM_SESSION").is_some_and(|v| !v.is_empty()) && tetron_catalog::is_installed("tetron-wm")
}

/// The first installed terminal web browser.
pub fn browser() -> Option<&'static str> {
    WEB_BROWSERS.into_iter().find(|b| tetron_catalog::is_installed(b))
}

/// The JSON of a tetron-wm `Launch` message: a window called `name` running
/// `command args`; `cwd_prompt` asks for a working folder first (agents).
pub fn launch_msg(name: &str, command: &str, args: &[String], cwd_prompt: bool) -> String {
    serde_json::json!({ "Launch": { "name": name, "command": command, "args": args, "cwd_prompt": cwd_prompt } }).to_string()
}

fn tetron_wm_launch(name: &str, command: &str, args: &[String], cwd_prompt: bool) -> Result<(), String> {
    let st = Command::new("tetron-wm").args(["msg", &launch_msg(name, command, args, cwd_prompt)]).status();
    match st {
        Ok(s) if s.success() => Ok(()),
        Ok(s) => Err(format!("tetron-wm msg failed ({s})")),
        Err(e) => Err(format!("tetron-wm msg: {e}")),
    }
}

/// The install script for running in this terminal: the shared install
/// command, ending with a prompt to return to the Store instead of a shell.
pub fn install_script_here(app: &CatalogApp) -> String {
    tetron_catalog::install::install_command(app).replace(
        "exec \"$SHELL\"",
        "printf '\\nPress Enter to return to the Store '; read _",
    )
}

/// What [`run_here`] needs: leave the Store's screen, run, come back.
pub trait Suspend {
    fn suspend(&mut self);
    fn resume(&mut self);
}

fn run_here(t: &mut impl Suspend, command: &str, args: &[String]) -> Result<(), String> {
    t.suspend();
    let r = Command::new(command).args(args).status();
    t.resume();
    r.map(|_| ()).map_err(|e| format!("{command}: {e}"))
}

/// Install `app` (or launch it when installed). Returns the status line.
pub fn activate(t: &mut impl Suspend, app: &CatalogApp) -> String {
    let installed = tetron_catalog::is_installed(&app.bin);
    let inside = in_tetron_wm();
    let r = match (installed, inside) {
        (false, true) => {
            let script = format!(
                "{}; echo; echo '── install finished — close this window (x) to refresh ──'; exec \"$SHELL\"",
                tetron_catalog::install::install_command(app)
            );
            tetron_wm_launch(&format!("install: {}", app.name), "sh", &["-lc".into(), script], false)
        }
        (false, false) => {
            let r = run_here(t, "sh", &["-lc".into(), install_script_here(app)]);
            tetron_catalog::refresh_installed();
            r
        }
        (true, true) => {
            let cwd = tetron_catalog::recipe(&app.name).is_some_and(|r| r.requires_cwd) || app.category == "AI";
            tetron_wm_launch(&app.name, &app.bin, &[], cwd)
        }
        (true, false) if app.cli => {
            let script = format!("{} --help; printf '\\nPress Enter to return to the Store '; read _", sh_quote(&app.bin));
            run_here(t, "sh", &["-lc".into(), script])
        }
        (true, false) => run_here(t, &app.bin, &[]),
    };
    match (r, installed) {
        (Ok(()), false) if inside => format!("Installing {} in a new window", app.name),
        (Ok(()), false) if tetron_catalog::is_installed(&app.bin) => format!("{} installed", app.name),
        (Ok(()), false) => format!("{} is not installed yet", app.name),
        (Ok(()), true) => String::new(),
        (Err(e), _) => e,
    }
}

/// Open `url` in the first installed terminal browser.
pub fn open(t: &mut impl Suspend, label: &str, url: &str) -> String {
    let Some(b) = browser() else { return format!("{label}: no terminal web browser installed") };
    let r = if in_tetron_wm() { tetron_wm_launch(url, b, &[url.to_string()], false) } else { run_here(t, b, &[url.to_string()]) };
    match r {
        Ok(()) => format!("{label}: opened in {b}"),
        Err(e) => e,
    }
}

/// The OSC 52 sequence that puts `text` on the clipboard.
pub fn osc52(text: &str) -> String {
    format!("\x1b]52;c;{}\x07", base64::engine::general_purpose::STANDARD.encode(text))
}

fn sh_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

/// The published lists, one directory per core minor (`<base>/0.15/`);
/// `TETRON_WM_LISTS_URL` overrides it, as in tetron-wm.
pub const LISTS_BASE: &str = "https://tetronos.github.io/apt/lists";

/// The catalog URL for this version: `<base>/<major.minor>/catalog.json`.
pub fn catalog_url(base: &str) -> String {
    let minor: Vec<&str> = env!("CARGO_PKG_VERSION").split('.').take(2).collect();
    format!("{}/{}/catalog.json", base.trim_end_matches('/'), minor.join("."))
}

/// Download, check and keep the catalog (the same file tetron-wm reads);
/// returns the status line. Run on a worker thread.
pub fn update_list() -> String {
    let base = std::env::var("TETRON_WM_LISTS_URL").ok().filter(|v| !v.is_empty()).unwrap_or_else(|| LISTS_BASE.into());
    let url = catalog_url(&base);
    let out = Command::new("curl").args(["-fsSL", "--max-time", "25", "-H", "User-Agent: tetron-appstore", &url]).output();
    match out {
        Ok(o) if o.status.success() => match tetron_catalog::install(&String::from_utf8_lossy(&o.stdout)) {
            Ok(n) => format!("List updated: {n} apps"),
            Err(e) => format!("Update list: not used ({e}); the list in use stays"),
        },
        _ => "Update list: download failed; the list in use stays".into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn demo() -> CatalogApp {
        serde_json::from_str(r#"{"name":"demo","bin":"demo","category":"X","description":"d","homepage":"https://github.com/o/demo"}"#).unwrap()
    }

    #[test]
    fn install_here_returns_to_the_store_not_a_shell() {
        let s = install_script_here(&demo());
        assert!(!s.contains("exec \"$SHELL\""), "{s}");
        assert!(s.contains("return to the Store"), "{s}");
        let ok = Command::new("sh").args(["-n", "-c", &s]).status().unwrap().success();
        assert!(ok, "valid sh: {s}");
    }

    #[test]
    fn launch_message_is_a_tetron_wm_launch() {
        let m: serde_json::Value = serde_json::from_str(&launch_msg("install: x", "sh", &["-lc".into(), "a 'b'".into()], true)).unwrap();
        assert_eq!(m["Launch"]["name"], "install: x");
        assert_eq!(m["Launch"]["args"][1], "a 'b'");
        assert_eq!(m["Launch"]["cwd_prompt"], true);
    }

    #[test]
    fn osc52_and_catalog_url() {
        assert_eq!(osc52("hi"), "\x1b]52;c;aGk=\x07");
        assert!(catalog_url("https://e.org/lists/").starts_with("https://e.org/lists/0."));
        assert!(catalog_url(LISTS_BASE).ends_with("/catalog.json"));
    }
}
