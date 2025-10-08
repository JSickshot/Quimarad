# ui/theme.py
import os
import colorsys
from dataclasses import dataclass
from typing import Tuple, Optional

import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image
except Exception:
    Image = None  # PIL opcional (recomendado)


@dataclass
class Palette:
    primary: str
    primary_dark: str
    primary_light: str
    bg: str
    panel_bg: str
    text: str
    text_muted: str
    border: str
    focus: str


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _mix(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return tuple(int(round((1 - t) * a + t * b)) for a, b in zip(rgb1, rgb2))


def _rel_lum(rgb: Tuple[int, int, int]) -> float:
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _text_on(bg_rgb: Tuple[int, int, int]) -> str:
    white, black = (255, 255, 255), (0, 0, 0)
    lw = abs(_rel_lum(white) - _rel_lum(bg_rgb))
    lb = abs(_rel_lum(black) - _rel_lum(bg_rgb))
    return _rgb_to_hex(white if lw >= lb else black)


def _dominant_color(path: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not path or not Image or not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA").resize((96, 96))
        counts = {}
        for r, g, b, a in img.getdata():
            if a < 8:
                continue
            # ignorar blancos muy puros
            if r > 245 and g > 245 and b > 245:
                continue
            counts[(r, g, b)] = counts.get((r, g, b), 0) + 1
        if not counts:
            return None

        def weight(item):
            (r, g, b), cnt = item
            # favorecer un poco saturación, pero permitir monocromos (logo negro)
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            return cnt * (0.6 + 0.5 * s) + (1.0 - v) * 5  # leve sesgo a tonos oscuros
        (r, g, b), _ = max(counts.items(), key=weight)
        return (r, g, b)
    except Exception:
        return None


def _build_palette(logo_path: Optional[str]) -> Palette:
    dom = _dominant_color(logo_path)

    if dom is None:
        # Fallback MONOCROMO elegante (negro/grises) cuando no hay logo
        dom = (17, 17, 17)  # #111

    # Si el color es muy poco saturado, lo tratamos como MONOCROMO (ideal para tu logo negro)
    r, g, b = dom
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    is_monochrome = s < 0.12  # baja saturación ~ escala de grises

    if is_monochrome:
        primary = (17, 17, 17)         # #111
        primary_dark = (8, 8, 8)       # #080808
        primary_light = (230, 230, 230)  # usado para hovers claros
        bg = (246, 248, 250)           # gris muy claro
        panel_bg = (255, 255, 255)
        border = (214, 218, 223)
        text = (16, 18, 22)
        text_muted = (102, 109, 117)
        focus = (0, 120, 215)          # azul accesible para focus (Windows-like)
    else:
        # Paleta derivada del color dominante (cuando el logo tiene color)
        primary = (r, g, b)
        primary_dark = _mix(primary, (0, 0, 0), 0.35)
        primary_light = _mix(primary, (255, 255, 255), 0.80)
        bg = (248, 250, 252)
        panel_bg = (255, 255, 255)
        border = _mix(primary, (0, 0, 0), 0.80)
        text = (25, 28, 33)
        text_muted = (95, 105, 115)
        focus = _mix(primary, (255, 255, 255), 0.35)

    return Palette(
        primary=_rgb_to_hex(primary),
        primary_dark=_rgb_to_hex(primary_dark),
        primary_light=_rgb_to_hex(primary_light),
        bg=_rgb_to_hex(bg),
        panel_bg=_rgb_to_hex(panel_bg),
        text=_rgb_to_hex(text),
        text_muted=_rgb_to_hex(text_muted),
        border=_rgb_to_hex(border),
        focus=_rgb_to_hex(focus),
    )


def apply_theme(root: tk.Tk, logo_path: Optional[str] = None):
    if logo_path is None:
        try:
            from settings import QCG_LOGO_PATH as _LOGO
            logo_path = _LOGO
        except Exception:
            logo_path = None

    pal = _build_palette(logo_path)

    root.configure(bg=pal.bg)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    base_font = ("Segoe UI", 10)
    base_font_bold = ("Segoe UI Semibold", 10)

    # Base
    style.configure(".", background=pal.bg, foreground=pal.text, font=base_font)
    style.configure("TFrame", background=pal.bg)
    style.configure("TLabel", background=pal.bg, foreground=pal.text)
    style.configure("Header.TLabel", background=pal.bg, foreground=pal.text, font=("Segoe UI Semibold", 16))

    # Card
    style.configure("Card.TFrame", background=pal.panel_bg, relief="groove", borderwidth=1)
    style.map("Card.TFrame", background=[("focus", pal.panel_bg)])

    # Botones
    style.configure(
        "TButton",
        padding=(12, 8),
        background=pal.panel_bg,
        foreground=pal.text,
        borderwidth=1,
        focusthickness=1,
        focuscolor=pal.focus,
        font=base_font_bold,
    )
    style.map(
        "TButton",
        background=[("active", pal.primary_light)],
        foreground=[("disabled", pal.text_muted)],
    )

    style.configure(
        "Accent.TButton",
        padding=(14, 10),
        background=pal.primary,
        foreground=_text_on(tuple(int(pal.primary[i:i+2], 16) for i in (1, 3, 5))),
        borderwidth=1,
        font=("Segoe UI Semibold", 11),
    )
    style.map(
        "Accent.TButton",
        background=[("active", pal.primary_dark), ("pressed", pal.primary_dark)],
    )

    # Entry / Combobox
    style.configure("TEntry", fieldbackground=pal.panel_bg, foreground=pal.text, padding=6)
    style.configure("TCombobox", fieldbackground=pal.panel_bg, foreground=pal.text, arrowsize=14, padding=4)

    # Notebook
    style.configure("TNotebook", background=pal.panel_bg)
    style.configure("TNotebook.Tab", background=pal.panel_bg, foreground=pal.text, padding=(14, 8), font=base_font_bold)
    style.map("TNotebook.Tab", background=[("selected", pal.primary_light), ("active", pal.primary_light)])

    style.configure("TCheckbutton", background=pal.bg, foreground=pal.text, padding=4)
    style.configure("TSeparator", background=pal.border)

    # Defaults Tk (no-ttk)
    root.option_add("*Font", base_font)
    root.option_add("*Entry.Background", pal.panel_bg)
    root.option_add("*Entry.Foreground", pal.text)
    root.option_add("*Text.Background", pal.panel_bg)
    root.option_add("*Text.Foreground", pal.text)
    root.option_add("*Button.Font", base_font_bold)

    # Exponer paleta si la quieres usar
    root._theme_palette = pal  # type: ignore[attr-defined]
