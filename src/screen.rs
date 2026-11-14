//! A grid of cells drawn to the terminal with crossterm. Each frame is drawn
//! into a fresh [`Screen`]; [`flush`] writes only the cells that differ from
//! the previous frame.

use crossterm::style::{Color, Print, SetBackgroundColor, SetForegroundColor};
use crossterm::{cursor, queue};
use std::io::Write;

/// A colour: `None` is the terminal's own default.
pub type Rgb = Option<(u8, u8, u8)>;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Cell {
    pub ch: char,
    pub fg: Rgb,
    pub bg: Rgb,
}

impl Default for Cell {
    fn default() -> Self {
        Cell { ch: ' ', fg: None, bg: None }
    }
}

pub struct Screen {
    pub w: i32,
    pub h: i32,
    cells: Vec<Cell>,
}

impl Screen {
    pub fn new(w: i32, h: i32) -> Self {
        Screen { w, h, cells: vec![Cell::default(); (w.max(0) * h.max(0)) as usize] }
    }

    pub fn get(&self, x: i32, y: i32) -> Option<&Cell> {
        (x >= 0 && y >= 0 && x < self.w && y < self.h).then(|| &self.cells[(y * self.w + x) as usize])
    }

    pub fn set(&mut self, x: i32, y: i32, c: Cell) {
        if x >= 0 && y >= 0 && x < self.w && y < self.h {
            self.cells[(y * self.w + x) as usize] = c;
        }
    }

    /// Fill the rectangle `x, y, w, h` with blanks of colour `fg` on `bg`.
    pub fn fill(&mut self, x: i32, y: i32, w: i32, h: i32, fg: Rgb, bg: Rgb) {
        for yy in y..y + h {
            for xx in x..x + w {
                self.set(xx, yy, Cell { ch: ' ', fg, bg });
            }
        }
    }

    /// Write `s` from `x, y`, one char per cell, clipped at the right edge.
    pub fn text(&mut self, x: i32, y: i32, s: &str, fg: Rgb, bg: Rgb) {
        for (i, ch) in s.chars().enumerate() {
            self.set(x + i as i32, y, Cell { ch, fg, bg });
        }
    }

    /// The characters of row `y` (tests).
    #[cfg(test)]
    pub fn row(&self, y: i32) -> String {
        (0..self.w).map(|x| self.get(x, y).map(|c| c.ch).unwrap_or(' ')).collect()
    }
}

fn color(c: Rgb) -> Color {
    match c {
        Some((r, g, b)) => Color::Rgb { r, g, b },
        None => Color::Reset,
    }
}

/// Draw `next` over `prev` (all of it when the sizes differ).
pub fn flush(out: &mut impl Write, prev: Option<&Screen>, next: &Screen) -> std::io::Result<()> {
    let full = prev.is_none_or(|p| p.w != next.w || p.h != next.h);
    let (mut fg, mut bg): (Option<Rgb>, Option<Rgb>) = (None, None);
    for y in 0..next.h {
        let mut at: Option<i32> = None;
        for x in 0..next.w {
            let c = next.get(x, y).copied().unwrap_or_default();
            if !full && prev.and_then(|p| p.get(x, y)) == Some(&c) {
                at = None;
                continue;
            }
            if at != Some(x) {
                queue!(out, cursor::MoveTo(x as u16, y as u16))?;
            }
            if fg != Some(c.fg) {
                queue!(out, SetForegroundColor(color(c.fg)))?;
                fg = Some(c.fg);
            }
            if bg != Some(c.bg) {
                queue!(out, SetBackgroundColor(color(c.bg)))?;
                bg = Some(c.bg);
            }
            queue!(out, Print(c.ch))?;
            at = Some(x + 1);
        }
    }
    out.flush()
}
