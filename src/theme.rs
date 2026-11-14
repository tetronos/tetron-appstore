//! Colours. Inside tetron-wm the Store follows its theme: tetron-wm writes the
//! active theme's colours to `$XDG_STATE_HOME/tetron-wm/theme-colors.json`
//! (default `~/.local/state`) and this module re-reads that file when it
//! changes. Elsewhere, or without the file, the terminal's own colours are used
//! with a few accents.

use crate::screen::Rgb;
use std::path::PathBuf;
use std::time::SystemTime;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Palette {
    pub bg: Rgb,
    pub fg: Rgb,
    pub dim: Rgb,
    pub sel: Rgb,
    pub accent: Rgb,
    pub panel: Rgb,
    pub success: Rgb,
}

impl Default for Palette {
    /// The terminal's own background and text, with readable accents.
    fn default() -> Self {
        Palette {
            bg: None,
            fg: None,
            dim: Some((140, 140, 150)),
            sel: Some((60, 70, 100)),
            accent: Some((120, 170, 255)),
            panel: None,
            success: Some((110, 200, 120)),
        }
    }
}

pub fn colors_path() -> Option<PathBuf> {
    let xdg = std::env::var_os("XDG_STATE_HOME").filter(|v| !v.is_empty()).map(PathBuf::from).filter(|p| p.is_absolute());
    xdg.or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/state"))).map(|d| d.join("tetron-wm/theme-colors.json"))
}

fn hex(v: Option<&serde_json::Value>) -> Option<Rgb> {
    let s = v?.as_str()?.trim_start_matches('#');
    if s.len() != 6 {
        return None;
    }
    let n = u32::from_str_radix(s, 16).ok()?;
    Some(Some(((n >> 16) as u8, (n >> 8) as u8, n as u8)))
}

/// A palette from the theme file's JSON (`{"bg": "#rrggbb", ...}`); a role
/// missing or unreadable keeps its default.
pub fn parse(text: &str) -> Palette {
    let mut p = Palette::default();
    let Ok(v) = serde_json::from_str::<serde_json::Value>(text) else { return p };
    for (k, slot) in [
        ("bg", &mut p.bg),
        ("fg", &mut p.fg),
        ("dim", &mut p.dim),
        ("sel", &mut p.sel),
        ("accent", &mut p.accent),
        ("panel", &mut p.panel),
        ("success", &mut p.success),
    ] {
        if let Some(c) = hex(v.get(k)) {
            *slot = c;
        }
    }
    p
}

/// The palette in use, re-read when the theme file changes.
pub struct Theme {
    pub pal: Palette,
    seen: Option<SystemTime>,
}

impl Theme {
    pub fn load() -> Self {
        let mut t = Theme { pal: Palette::default(), seen: None };
        t.poll();
        t
    }

    /// Re-read the theme file when its modification time changed; true when
    /// the palette changed.
    pub fn poll(&mut self) -> bool {
        let Some(path) = colors_path() else { return false };
        let m = std::fs::metadata(&path).and_then(|m| m.modified()).ok();
        if m == self.seen {
            return false;
        }
        self.seen = m;
        let pal = std::fs::read_to_string(&path).map(|t| parse(&t)).unwrap_or_default();
        let changed = pal != self.pal;
        self.pal = pal;
        changed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_takes_known_roles_and_keeps_defaults() {
        let p = parse(r##"{"bg":"#101820","accent":"#FFAA00","dim":"nope","extra":"#000000"}"##);
        assert_eq!(p.bg, Some((0x10, 0x18, 0x20)));
        assert_eq!(p.accent, Some((0xff, 0xaa, 0x00)));
        assert_eq!(p.dim, Palette::default().dim);
        assert_eq!(parse("garbage"), Palette::default());
    }
}
