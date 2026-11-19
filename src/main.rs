//! tetron-appstore: browse, search, install and launch terminal apps from the
//! tetron catalog, in any terminal. `tetron-appstore [SEARCH]` opens with the
//! apps matching SEARCH.

mod actions;
mod menu;
mod screen;
mod store;
mod theme;

use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers, MouseButton, MouseEventKind};
use crossterm::{cursor, execute, terminal};
use menu::{Action, Links, Menu};
use screen::Screen;
use std::io::{Stdout, Write};
use std::sync::mpsc;
use std::time::{Duration, Instant};
use store::{Click, Store};

const HELP: &str = "tetron-appstore: browse, install and launch terminal apps

Usage: tetron-appstore [SEARCH]

  Type to search (from:NAME shows one list: from:trove, from:awesome,
  from:tetron), arrows move, Left/Right change category, Enter installs or
  launches, Alt+O (or a right click) opens the app menu: open or copy the
  project and releases links. F5 or [ Update list ] downloads the newest
  catalog. Esc quits.

Inside tetron-wm, installs and apps open in tetron-wm windows.
";

struct Term {
    out: Stdout,
    prev: Option<Screen>,
}

impl Term {
    fn enter(&mut self) {
        let _ = terminal::enable_raw_mode();
        let _ = execute!(self.out, terminal::EnterAlternateScreen, cursor::Hide, event::EnableMouseCapture);
        self.prev = None;
    }
    fn leave(&mut self) {
        let _ = execute!(self.out, event::DisableMouseCapture, cursor::Show, terminal::LeaveAlternateScreen);
        let _ = terminal::disable_raw_mode();
    }
}

impl actions::Suspend for Term {
    fn suspend(&mut self) {
        self.leave();
    }
    fn resume(&mut self) {
        self.enter();
    }
}

struct App {
    store: Store,
    menu: Option<Menu>,
    theme: theme::Theme,
    update: Option<mpsc::Receiver<String>>,
    quit: bool,
}

impl App {
    fn open_menu(&mut self, links: Links, at: (i32, i32)) {
        let Some(app) = self.store.selected_app() else { return };
        let items = menu::actions(app, links, tetron_catalog::app_installed(app), actions::browser().is_some());
        if !items.is_empty() {
            self.menu = Some(Menu::new(at, items));
        }
    }

    fn run_action(&mut self, t: &mut Term, a: Action) {
        let msg = match a {
            Action::Install(_) => match self.store.selected_app() {
                Some(app) => actions::activate(t, app),
                None => String::new(),
            },
            Action::Open(label, url) => actions::open(t, &label, &url),
            Action::Copy(label, url) => {
                let _ = write!(t.out, "{}", actions::osc52(&url));
                let _ = t.out.flush();
                format!("{label}: copied")
            }
        };
        self.store.set_status(&msg);
    }

    fn start_update(&mut self) {
        if self.update.is_none() {
            self.store.set_status("Updating list\u{2026}");
            let (tx, rx) = mpsc::channel();
            std::thread::spawn(move || {
                let _ = tx.send(actions::update_list());
            });
            self.update = Some(rx);
        }
    }

    fn key(&mut self, t: &mut Term, k: KeyEvent, h: i32) {
        let alt = k.modifiers.contains(KeyModifiers::ALT);
        let ctrl = k.modifiers.contains(KeyModifiers::CONTROL);
        if let Some(m) = &mut self.menu {
            match k.code {
                KeyCode::Up | KeyCode::BackTab => m.up(),
                KeyCode::Down | KeyCode::Tab => m.down(),
                KeyCode::Esc => self.menu = None,
                KeyCode::Enter => {
                    if let Some(a) = self.menu.take().and_then(|m| m.items.get(m.sel).cloned()) {
                        self.run_action(t, a);
                    }
                }
                _ => {}
            }
            return;
        }
        match k.code {
            KeyCode::Esc => self.quit = true,
            KeyCode::Char('c') if ctrl => self.quit = true,
            KeyCode::Enter => self.run_action(t, Action::Install(false)),
            KeyCode::F(5) => self.start_update(),
            KeyCode::Char('o' | 'O') if alt => self.open_menu(Links::App, (store::details_x(), 3)),
            KeyCode::Up => self.store.move_up(),
            KeyCode::Down => self.store.move_down(),
            KeyCode::PageUp => self.store.page(h, false),
            KeyCode::PageDown => self.store.page(h, true),
            KeyCode::Left => self.store.prev_category(),
            KeyCode::Right => self.store.next_category(),
            KeyCode::Backspace => self.store.backspace(),
            KeyCode::Char(c) if !ctrl && !alt => self.store.type_char(c),
            _ => {}
        }
    }

    fn mouse(&mut self, t: &mut Term, kind: MouseEventKind, p: (i32, i32), w: i32, h: i32) {
        if let Some(m) = &mut self.menu {
            match kind {
                MouseEventKind::Moved => {
                    if let Some(i) = m.index_at(p, w, h) {
                        m.sel = i;
                    }
                }
                MouseEventKind::Down(_) => {
                    let hit = m.index_at(p, w, h).and_then(|i| m.items.get(i).cloned());
                    self.menu = None;
                    if let Some(a) = hit {
                        self.run_action(t, a);
                    }
                }
                _ => {}
            }
            return;
        }
        match kind {
            MouseEventKind::Down(MouseButton::Left) => match self.store.click(p, w, h) {
                Click::Activate => self.run_action(t, Action::Install(false)),
                Click::UpdateList => self.start_update(),
                Click::Menu(links) => self.open_menu(links, p),
                Click::None => {}
            },
            MouseEventKind::Down(MouseButton::Right) => {
                if self.store.right_click(p, h) {
                    self.open_menu(Links::App, p);
                }
            }
            MouseEventKind::ScrollUp => self.store.move_up(),
            MouseEventKind::ScrollDown => self.store.move_down(),
            _ => {}
        }
    }
}

fn main() -> std::io::Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{HELP}");
        return Ok(());
    }
    if args.iter().any(|a| a == "--version" || a == "-V") {
        println!("tetron-appstore {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    let mut app = App { store: Store::new(), menu: None, theme: theme::Theme::load(), update: None, quit: false };
    if !args.is_empty() {
        app.store.set_query(&args.join(" "));
    }
    // The automatic update, at most once a day (ASCLI-006).
    if tetron_catalog::update::due() {
        app.start_update();
    } else if tetron_catalog::update::newer_seen() {
        app.store.set_status(tetron_catalog::update::NEWER_NOTE);
    }
    let mut t = Term { out: std::io::stdout(), prev: None };
    t.enter();
    let mut last_poll = Instant::now();
    let r = (|| -> std::io::Result<()> {
        while !app.quit {
            let (w, h) = terminal::size().map(|(w, h)| (w as i32, h as i32))?;
            app.store.settle_scroll(h);
            let mut s = Screen::new(w, h);
            app.store.render(&mut s, &app.theme.pal);
            if let Some(m) = &app.menu {
                m.render(&mut s, &app.theme.pal);
            }
            screen::flush(&mut t.out, t.prev.as_ref(), &s)?;
            t.prev = Some(s);
            if event::poll(Duration::from_millis(250))? {
                match event::read()? {
                    Event::Key(k) if k.kind != KeyEventKind::Release => app.key(&mut t, k, h),
                    Event::Mouse(m) => app.mouse(&mut t, m.kind, (m.column as i32, m.row as i32), w, h),
                    Event::Resize(..) => t.prev = None,
                    _ => {}
                }
            }
            if let Some(msg) = app.update.as_ref().and_then(|rx| rx.try_recv().ok()) {
                app.update = None;
                app.store.set_status(&msg);
                app.store.catalog_changed();
            }
            if last_poll.elapsed() >= Duration::from_secs(1) {
                last_poll = Instant::now();
                if app.theme.poll() {
                    t.prev = None;
                }
            }
        }
        Ok(())
    })();
    t.leave();
    r
}
