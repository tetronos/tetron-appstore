//! The app menu (right-click, Alt+O, or a click on a link): Install or Launch,
//! Open and Copy for the project link and the releases link. A boxed list
//! kept inside the screen; render and hit-test share [`Menu::rect`].

use crate::screen::{Cell, Screen};
use crate::theme::Palette;
use tetron_catalog::CatalogApp;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Action {
    /// Install the app, or launch it when installed (true).
    Install(bool),
    /// Open a link (label, URL) in a terminal web browser.
    Open(String, String),
    /// Copy a link (label, URL) to the clipboard.
    Copy(String, String),
}

impl Action {
    pub fn label(&self) -> &str {
        match self {
            Action::Install(true) => "Launch",
            Action::Install(false) => "Install",
            Action::Open(l, _) | Action::Copy(l, _) => l,
        }
    }
}

/// Which links a menu offers.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Links {
    /// The whole app menu: install, the project link, the releases link.
    App,
    /// Only the project link (a click on it in the details).
    Project,
    /// Only the releases link (a click on the "Prebuilt" line).
    Releases,
}

/// The menu items for `app`; Open entries only when a `browser` is installed.
pub fn actions(app: &CatalogApp, links: Links, installed: bool, browser: bool) -> Vec<Action> {
    let mut v = Vec::new();
    if links == Links::App && !(installed && !app.launchable()) {
        v.push(Action::Install(installed));
    }
    let mut add = |what: &str, url: String| {
        if browser {
            v.push(Action::Open(format!("Open {what} page"), url.clone()));
        }
        v.push(Action::Copy(format!("Copy {what} link"), url));
    };
    if links != Links::Releases && !app.homepage.is_empty() {
        add("project", app.homepage.clone());
    }
    if links != Links::Project {
        if let Some(u) = tetron_catalog::releases_url(app) {
            add("releases", u);
        }
    }
    v
}

pub struct Menu {
    pub items: Vec<Action>,
    pub sel: usize,
    anchor: (i32, i32),
}

impl Menu {
    pub fn new(anchor: (i32, i32), items: Vec<Action>) -> Self {
        Menu { items, sel: 0, anchor }
    }

    /// The box (x, y, w, h), moved left and up as needed to stay on a
    /// `w × h` screen.
    pub fn rect(&self, w: i32, h: i32) -> (i32, i32, i32, i32) {
        let bw = self.items.iter().map(|a| a.label().chars().count() as i32).max().unwrap_or(0) + 4;
        let bh = self.items.len() as i32 + 2;
        let x = self.anchor.0.min(w - bw).max(0);
        let y = self.anchor.1.min(h - bh).max(0);
        (x, y, bw.min(w), bh.min(h))
    }

    /// The item under screen point `p`.
    pub fn index_at(&self, p: (i32, i32), w: i32, h: i32) -> Option<usize> {
        let (x, y, bw, bh) = self.rect(w, h);
        let i = p.1 - y - 1;
        (p.0 > x && p.0 < x + bw - 1 && p.1 > y && p.1 < y + bh - 1 && (i as usize) < self.items.len()).then_some(i as usize)
    }

    pub fn up(&mut self) {
        let n = self.items.len().max(1);
        self.sel = (self.sel + n - 1) % n;
    }

    pub fn down(&mut self) {
        self.sel = (self.sel + 1) % self.items.len().max(1);
    }

    pub fn render(&self, s: &mut Screen, pal: &Palette) {
        let (x, y, bw, bh) = self.rect(s.w, s.h);
        let bg = pal.panel.or(pal.sel);
        let line = |s: &mut Screen, xx: i32, yy: i32, ch: char| s.set(xx, yy, Cell { ch, fg: pal.dim, bg });
        s.fill(x, y, bw, bh, pal.fg, bg);
        for xx in x + 1..x + bw - 1 {
            line(s, xx, y, '\u{2500}');
            line(s, xx, y + bh - 1, '\u{2500}');
        }
        for yy in y + 1..y + bh - 1 {
            line(s, x, yy, '\u{2502}');
            line(s, x + bw - 1, yy, '\u{2502}');
        }
        line(s, x, y, '\u{250C}');
        line(s, x + bw - 1, y, '\u{2510}');
        line(s, x, y + bh - 1, '\u{2514}');
        line(s, x + bw - 1, y + bh - 1, '\u{2518}');
        for (i, a) in self.items.iter().enumerate() {
            let (fg, rbg) = if i == self.sel { (pal.accent, pal.sel) } else { (pal.fg, bg) };
            s.fill(x + 1, y + 1 + i as i32, bw - 2, 1, fg, rbg);
            s.text(x + 2, y + 1 + i as i32, a.label(), fg, rbg);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn demo() -> CatalogApp {
        serde_json::from_str(r#"{"name":"demo","bin":"demo","category":"X","description":"d","homepage":"https://github.com/o/demo","releases":true}"#).unwrap()
    }

    #[test]
    fn app_menu_and_link_menus() {
        let labels = |v: Vec<Action>| v.iter().map(|a| a.label().to_string()).collect::<Vec<_>>();
        assert_eq!(
            labels(actions(&demo(), Links::App, false, true)),
            ["Install", "Open project page", "Copy project link", "Open releases page", "Copy releases link"]
        );
        assert_eq!(labels(actions(&demo(), Links::Releases, true, false)), ["Copy releases link"]);
        assert_eq!(labels(actions(&demo(), Links::Project, true, true)), ["Open project page", "Copy project link"]);
    }

    #[test]
    fn menu_stays_on_screen_and_hit_tests_its_rows() {
        let m = Menu::new((78, 22), actions(&demo(), Links::App, false, true));
        let (x, y, w, h) = m.rect(80, 24);
        assert!(x + w <= 80 && y + h <= 24);
        assert_eq!(m.index_at((x + 2, y + 1), 80, 24), Some(0));
        assert_eq!(m.index_at((x + 2, y + h - 2), 80, 24), Some(4));
        assert_eq!(m.index_at((x, y + 1), 80, 24), None, "the border is not an item");
    }
}
