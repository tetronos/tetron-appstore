//! The Store screen: categories, the app list and the selected app's details,
//! with search, keys and clicks. The same layout as tetron-wm's built-in
//! Store; render and hit-test share the geometry functions at the bottom.

use crate::menu::Links;
use crate::screen::{Cell, Screen};
use crate::theme::Palette;
use tetron_catalog::{self as catalog, CatalogApp};

const SIDEBAR_W: i32 = 16;
const LIST_W: i32 = 30;
const CLI_BADGE: &str = "CLI";
const UPDATE_BTN: &str = "[ Update list ]";

/// What a click asks the program to do.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Click {
    None,
    /// Install or launch the selected app.
    Activate,
    /// Fetch the catalog.
    UpdateList,
    /// Open the menu of the selected app with these links.
    Menu(Links),
}

pub struct Store {
    categories: Vec<String>,
    cat_index: usize,
    query: String,
    selected: usize,
    scroll: usize,
    status: String,
}

impl Default for Store {
    fn default() -> Self {
        Self::new()
    }
}

impl Store {
    pub fn new() -> Self {
        Store { categories: category_list(), cat_index: 0, query: String::new(), selected: 0, scroll: 0, status: String::new() }
    }

    /// Show `msg` on row 0 instead of the app count.
    pub fn set_status(&mut self, msg: &str) {
        self.status = msg.to_string();
    }

    /// The catalog in use changed (Update list): re-read the categories,
    /// keeping the selected one when it still exists.
    pub fn catalog_changed(&mut self) {
        let cat = self.categories.get(self.cat_index).cloned();
        self.categories = category_list();
        self.cat_index = cat.and_then(|c| self.categories.iter().position(|x| *x == c)).unwrap_or(0);
        self.reset_list();
    }

    /// Apps of the category matching the search. A `from:NAME` word keeps
    /// apps whose shown lists match NAME (WMCAT-010); the other words search
    /// names and descriptions.
    pub fn filtered(&self) -> Vec<&'static CatalogApp> {
        let cat = &self.categories[self.cat_index];
        let q = self.query.to_lowercase();
        let (from, words): (Vec<&str>, Vec<&str>) = q.split(' ').partition(|w| w.starts_with("from:"));
        let from: Vec<&str> = from.iter().map(|w| &w[5..]).filter(|w| !w.is_empty()).collect();
        let text = words.join(" ");
        let text = text.trim();
        catalog::catalog()
            .iter()
            .filter(|c| {
                catalog::runs_on_current_os(&c.name)
                    && (cat == "All" || &c.category == cat)
                    && (text.is_empty() || c.name.to_lowercase().contains(text) || c.description.to_lowercase().contains(text))
                    && from.iter().all(|f| catalog::listed_by(c).iter().any(|l| l.to_lowercase().replace(' ', "").contains(f)))
            })
            .collect()
    }

    pub fn selected_app(&self) -> Option<&'static CatalogApp> {
        self.filtered().into_iter().nth(self.selected)
    }

    pub fn move_up(&mut self) {
        self.selected = self.selected.saturating_sub(1);
    }
    pub fn move_down(&mut self) {
        if self.selected + 1 < self.filtered().len() {
            self.selected += 1;
        }
    }
    pub fn page(&mut self, rows: i32, down: bool) {
        let n = (rows - 3).max(1) as usize;
        if down {
            self.selected = (self.selected + n).min(self.filtered().len().saturating_sub(1));
        } else {
            self.selected = self.selected.saturating_sub(n);
        }
    }
    pub fn prev_category(&mut self) {
        if self.cat_index > 0 {
            self.cat_index -= 1;
            self.reset_list();
        }
    }
    pub fn next_category(&mut self) {
        if self.cat_index + 1 < self.categories.len() {
            self.cat_index += 1;
            self.reset_list();
        }
    }
    pub fn type_char(&mut self, c: char) {
        self.query.push(c);
        self.reset_list();
    }
    pub fn backspace(&mut self) {
        self.query.pop();
        self.reset_list();
    }
    /// Show the apps matching `q` in All (opened for one app).
    pub fn set_query(&mut self, q: &str) {
        self.cat_index = 0;
        self.query = q.to_string();
        self.reset_list();
    }

    fn reset_list(&mut self) {
        self.selected = 0;
        self.scroll = 0;
    }

    /// Keep the selection visible in `rows` rows (call before drawing).
    pub fn settle_scroll(&mut self, h: i32) {
        self.scroll = self.scroll_for(list_rows(h));
    }

    fn scroll_for(&self, rows: usize) -> usize {
        if rows == 0 {
            0
        } else if self.selected < self.scroll {
            self.selected
        } else if self.selected >= self.scroll + rows {
            self.selected + 1 - rows
        } else {
            self.scroll
        }
    }

    pub fn render(&self, s: &mut Screen, p: &Palette) {
        let (w, h) = (s.w, s.h);
        s.fill(0, 0, w, h, p.fg, p.bg);
        s.text(1, 0, &format!("Search: {}\u{2588}", self.query), p.accent, p.bg);
        let bx = update_btn_x(w);
        s.text(bx, 0, UPDATE_BTN, p.accent, p.bg);
        let meta = if self.status.is_empty() { format!("{} apps", self.filtered().len()) } else { self.status.clone() };
        let room = (bx - 2 - SIDEBAR_W - 10).max(0) as usize;
        let meta = truncate(&meta, room);
        s.text((bx - 2 - meta.chars().count() as i32).max(0), 0, meta, p.dim, p.bg);
        for x in 0..w {
            s.set(x, 1, Cell { ch: '\u{2500}', fg: p.dim, bg: p.bg });
        }

        for (i, cat) in self.categories.iter().enumerate() {
            let y = 2 + i as i32;
            if y >= h {
                break;
            }
            let (fg, bg) = if i == self.cat_index { (p.accent, p.sel) } else { (p.dim, p.bg) };
            s.fill(0, y, SIDEBAR_W, 1, fg, bg);
            s.text(1, y, truncate(cat, SIDEBAR_W as usize - 2), fg, bg);
        }
        vline(s, SIDEBAR_W, h, p);

        let list_x = SIDEBAR_W + 1;
        let apps = self.filtered();
        let scroll = self.scroll_for(list_rows(h));
        for (row, app) in apps.iter().skip(scroll).take(list_rows(h)).enumerate() {
            let y = 2 + row as i32;
            let sel = scroll + row == self.selected;
            let bg = if sel { p.sel } else { p.bg };
            s.fill(list_x, y, LIST_W, 1, p.fg, bg);
            if catalog::is_installed(&app.bin) {
                s.text(list_x, y, &p.check, p.success, bg);
            }
            let badge = if app.cli { CLI_BADGE.len() as i32 + 1 } else { 0 };
            s.text(list_x + 2, y, truncate(&app.name, (LIST_W - 3 - badge).max(1) as usize), p.fg, bg);
            if app.cli {
                s.text(list_x + LIST_W - CLI_BADGE.len() as i32, y, CLI_BADGE, p.accent, bg);
            }
        }
        vline(s, list_x + LIST_W, h, p);

        let dx = details_x();
        let dw = (w - dx - 1).max(2) as usize - 2;
        let Some(app) = self.selected_app() else { return };
        s.fill(dx, 2, w - dx, h - 2, p.fg, p.panel);
        s.text(dx + 1, 3, truncate(&app.name, dw), p.accent, p.panel);
        let cat = truncate(&app.category, dw);
        s.text(dx + 1, 4, cat, p.dim, p.panel);
        if app.cli {
            s.text(dx + 3 + cat.chars().count() as i32, 4, CLI_BADGE, p.accent, p.panel);
        }
        if let Some(set) = &app.set {
            s.text(dx + 1, 5, truncate(&format!("In the tetron {set} set"), dw), p.dim, p.panel);
        }
        let mut y = 6;
        for line in wrap(&app.description, dw) {
            if y >= listed_row(h) {
                break;
            }
            s.text(dx + 1, y, &line, p.fg, p.panel);
            y += 1;
        }
        if let Some(r) = catalog::recipe(&app.name).filter(|r| !r.tip.is_empty()) {
            y += 1;
            for line in wrap(&format!("Setup: {}", r.tip), dw) {
                if y >= listed_row(h) {
                    break;
                }
                s.text(dx + 1, y, &line, p.accent, p.panel);
                y += 1;
            }
        }
        let lists = catalog::listed_by(app);
        if !lists.is_empty() {
            s.text(dx + 1, listed_row(h), truncate(&format!("Listed by: {}", lists.join(", ")), dw), p.dim, p.panel);
        }
        if let Some(url) = catalog::releases_url(app) {
            s.text(dx + 1, prebuilt_row(h), truncate(&format!("Prebuilt: {url}"), dw), p.dim, p.panel);
        }
        s.text(dx + 1, homepage_row(h), truncate(&app.homepage, dw), p.dim, p.panel);
        if let Some(r) = catalog::recipe(&app.name).filter(|r| r.verified) {
            s.text(dx + 1, h - 3, &format!("{} verified \u{00B7} {}", p.check, r.method), p.success, p.panel);
        }
        let installed = catalog::is_installed(&app.bin);
        let action = if installed { "[ Enter: Launch ]  Alt+O: more" } else { "[ Enter: Install ]  Alt+O: more" };
        s.text(dx + 1, h - 2, action, if installed { p.success } else { p.accent }, p.panel);
    }

    /// A left click at `p` on a `w × h` screen.
    pub fn click(&mut self, p: (i32, i32), w: i32, h: i32) -> Click {
        let (x, y) = p;
        if y == 0 && x >= update_btn_x(w) && x < update_btn_x(w) + UPDATE_BTN.len() as i32 {
            return Click::UpdateList;
        }
        if y < 2 {
            return Click::None;
        }
        if x < SIDEBAR_W {
            let i = (y - 2) as usize;
            if i < self.categories.len() {
                self.cat_index = i;
                self.reset_list();
            }
            return Click::None;
        }
        let list_x = SIDEBAR_W + 1;
        if x >= list_x && x < list_x + LIST_W {
            let idx = self.scroll_for(list_rows(h)) + (y - 2) as usize;
            if idx < self.filtered().len() {
                if idx == self.selected {
                    return Click::Activate;
                }
                self.selected = idx;
            }
            return Click::None;
        }
        if x >= details_x() {
            if y == h - 2 {
                return Click::Activate;
            }
            if y == prebuilt_row(h) && self.selected_app().and_then(catalog::releases_url).is_some() {
                return Click::Menu(Links::Releases);
            }
            if y == homepage_row(h) && self.selected_app().is_some() {
                return Click::Menu(Links::Project);
            }
        }
        Click::None
    }

    /// A right click at `p`: on an app row it selects that app; on a row or
    /// the details the app menu opens (true).
    pub fn right_click(&mut self, p: (i32, i32), h: i32) -> bool {
        let (x, y) = p;
        let list_x = SIDEBAR_W + 1;
        if y < 2 || x < list_x {
            return false;
        }
        if x < list_x + LIST_W {
            let idx = self.scroll_for(list_rows(h)) + (y - 2) as usize;
            if idx >= self.filtered().len() {
                return false;
            }
            self.selected = idx;
        }
        self.selected_app().is_some()
    }
}

fn category_list() -> Vec<String> {
    let mut cats: Vec<String> = Vec::new();
    for c in catalog::catalog() {
        if !cats.contains(&c.category) {
            cats.push(c.category.clone());
        }
    }
    cats.sort();
    cats.insert(0, "All".to_string());
    cats
}

fn list_rows(h: i32) -> usize {
    (h - 2).max(0) as usize
}
fn update_btn_x(w: i32) -> i32 {
    (w - UPDATE_BTN.len() as i32 - 1).max(0)
}
/// The column where the details start.
pub fn details_x() -> i32 {
    SIDEBAR_W + 1 + LIST_W + 1
}
fn listed_row(h: i32) -> i32 {
    h - 6
}
fn prebuilt_row(h: i32) -> i32 {
    h - 5
}
fn homepage_row(h: i32) -> i32 {
    h - 4
}

fn vline(s: &mut Screen, x: i32, h: i32, p: &Palette) {
    for y in 2..h {
        s.set(x, y, Cell { ch: '\u{2502}', fg: p.dim, bg: p.bg });
    }
}

fn truncate(s: &str, max: usize) -> &str {
    match s.char_indices().nth(max) {
        Some((i, _)) => &s[..i],
        None => s,
    }
}

fn wrap(s: &str, width: usize) -> Vec<String> {
    let mut lines = Vec::new();
    let mut line = String::new();
    for word in s.split_whitespace() {
        if !line.is_empty() && line.chars().count() + 1 + word.chars().count() > width {
            lines.push(std::mem::take(&mut line));
        }
        if !line.is_empty() {
            line.push(' ');
        }
        line.push_str(word);
    }
    if !line.is_empty() {
        lines.push(line);
    }
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    fn with_releases() -> &'static CatalogApp {
        catalog::catalog().iter().find(|a| catalog::releases_url(a).is_some() && a.name.len() > 5).unwrap()
    }

    #[test]
    fn search_filters_and_clicks_hit_what_is_drawn() {
        let (w, h) = (110, 30);
        let app = with_releases();
        let mut st = Store::new();
        assert!(st.filtered().len() > 600);
        for c in app.name.chars() {
            st.type_char(c);
        }
        assert_eq!(st.selected_app().map(|a| a.name.as_str()), Some(app.name.as_str()));
        let mut s = Screen::new(w, h);
        st.render(&mut s, &Palette::default());
        let dx = details_x() + 2;
        let y = (0..h).find(|&y| s.row(y).contains("Prebuilt: https://github.com/")).expect("prebuilt line");
        assert_eq!(st.click((dx, y), w, h), Click::Menu(Links::Releases));
        let y = (0..h).find(|&y| s.row(y).trim_end().ends_with(&app.homepage)).expect("homepage line");
        assert_eq!(st.click((dx, y), w, h), Click::Menu(Links::Project));
        assert!(s.row(h - 2).contains("Alt+O: more"));
        assert_eq!(st.click((w - 5, 0), w, h), Click::UpdateList);
    }

    #[test]
    fn rows_select_then_activate_and_right_click_selects() {
        let (w, h) = (110, 30);
        let mut st = Store::new();
        assert_eq!(st.click((20, 3), w, h), Click::None);
        assert_eq!(st.click((20, 3), w, h), Click::Activate, "second click on the selected row");
        assert!(st.right_click((20, 4), h));
        assert_eq!(st.selected_app().map(|a| a.name.clone()), st.filtered().get(2).map(|a| a.name.clone()));
        assert!(!st.right_click((2, 4), h), "the sidebar has no menu");
        st.click((2, 3), w, h);
        assert!(st.filtered().len() < Store::new().filtered().len(), "a category narrows the list");
    }

    /// WMCAT-010: the details name the lists, and from: narrows to one list,
    /// combined with the other words.
    #[test]
    fn listed_by_line_and_from_filter() {
        let mut st = Store::new();
        let all = st.filtered().len();
        for c in "from:trove".chars() {
            st.type_char(c);
        }
        let trove = st.filtered();
        assert!(!trove.is_empty() && trove.len() < all);
        assert!(trove.iter().all(|a| catalog::listed_by(a).contains(&"Terminal Trove")));
        let mut s = Screen::new(110, 30);
        st.render(&mut s, &Palette::default());
        assert!((0..30).any(|y| s.row(y).contains("Listed by: ") && s.row(y).contains("Terminal Trove")));
        for c in " git".chars() {
            st.type_char(c);
        }
        let both = st.filtered();
        assert!(!both.is_empty() && both.len() < trove.len());
        assert!(both.iter().all(|a| (a.name.to_lowercase() + &a.description.to_lowercase()).contains("git")));
        st.set_query("from:tetron");
        assert!(st.filtered().iter().all(|a| catalog::listed_by(a) == ["tetron"]));
    }
}