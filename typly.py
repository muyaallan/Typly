"""
Typly — Human Typing Simulator  (Rebuilt Edition)
Copyright © 2025 Typly. All rights reserved.

pip install customtkinter pynput python-docx PyMuPDF Pillow
"""

import customtkinter as ctk
import threading
import time
import random
import math
import os
import sys
import json
from tkinter import filedialog
from pynput.keyboard import Controller, Key, Listener
from PIL import Image, ImageTk

def _resource_path(filename):
    """Get absolute path to resource — works for dev and PyInstaller bundle."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    import docx as _docx; HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import fitz as _fitz; HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ── Palette ───────────────────────────────────────────────────────────────────
# Windows 11 Fluent Dark — Mica-inspired neutral layers + system accent blue
C_BG         = "#202020"   # Mica app background
C_PANEL      = "#282828"   # elevated surface (layer 1)
C_CARD       = "#2f2f2f"   # elevated surface (layer 2 / cards)
C_SIDEBAR    = "#242424"   # NavigationView flyout backdrop
C_SCRIM      = "#0c0c0c"   # dismiss-layer behind the flyout (dimmed backdrop)
C_ACCENT     = "#60cdff"   # Windows 11 default system accent (light)
C_ACCENT2    = "#99e0ff"   # accent, lighter tint (secondary text/icons)
C_ACCENT_GRN = "#6ccb5f"   # success (Fluent green)
C_MID        = "#a3a3a3"   # secondary text
C_DARK       = "#3a3a3a"   # control fill (rest state)
C_TEXT       = "#f2f2f2"   # primary text
C_TEXT_DIM   = "#7a7a7a"   # tertiary / disabled text
C_BTN_HOV    = "#0f7dc7"   # accent hover (darker system blue)
C_STOP       = "#ff6259"   # Fluent red
C_STOP_HOV   = "#c42b1c"   # Fluent red, pressed
C_BORDER     = "#3d3d3d"   # hairline card/control border

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

keyboard = Controller()

# ── Keyboard maps ─────────────────────────────────────────────────────────────
SHIFT_MAP = {
    'A':'a','B':'b','C':'c','D':'d','E':'e','F':'f','G':'g','H':'h',
    'I':'i','J':'j','K':'k','L':'l','M':'m','N':'n','O':'o','P':'p',
    'Q':'q','R':'r','S':'s','T':'t','U':'u','V':'v','W':'w','X':'x',
    'Y':'y','Z':'z','!':'1','@':'2','#':'3','$':'4','%':'5','^':'6',
    '&':'7','*':'8','(':'9',')':'0','_':'-','+':'=','{':'[','}':']',
    '|':'\\',':':';','"':"'",'<':',','>':'.','?':'/','~':'`',
}

NEIGHBORS = {
    'a':'sqwz','b':'vghn','c':'xdfv','d':'serfcx','e':'wsdr','f':'drtgvc',
    'g':'ftyhbv','h':'gyujnb','i':'ujko','j':'huikmn','k':'jiolm','l':'kop',
    'm':'njk','n':'bhjm','o':'iklp','p':'ol','q':'wa','r':'edft','s':'awedxz',
    't':'rfgy','u':'yhji','v':'cfgb','w':'qase','x':'zsdc','y':'tghu','z':'asx',
}

PROFILES = {
    "Casual":      dict(wpm=45,  typo=0.05, variance=0.5,  burst=True,  fatigue=True),
    "Office":      dict(wpm=65,  typo=0.03, variance=0.35, burst=True,  fatigue=True),
    "Fast Typist": dict(wpm=95,  typo=0.02, variance=0.25, burst=True,  fatigue=False),
    "Hunt & Peck": dict(wpm=22,  typo=0.08, variance=0.7,  burst=False, fatigue=True),
    "Code Mode":   dict(wpm=55,  typo=0.0,  variance=0.2,  burst=False, fatigue=False),
    "Custom":      None,
}

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".typly_settings.json")


# ── KeyPresser ────────────────────────────────────────────────────────────────
class KeyPresser:
    def __init__(self):
        self._timers = []

    def press(self, key, hold=None):
        hold = hold or random.uniform(0.040, 0.110)
        keyboard.press(key)
        t = threading.Timer(hold, self._release, args=[key])
        t.daemon = True; t.start()
        self._timers.append(t)

    def _release(self, key):
        try: keyboard.release(key)
        except: pass

    def flush(self):
        for t in self._timers: t.join(timeout=0.3)
        self._timers.clear()


presser = KeyPresser()


def press_char(char):
    if char in SHIFT_MAP:
        base = SHIFT_MAP[char]
        hold = random.uniform(0.035, 0.090)
        keyboard.press(Key.shift)
        time.sleep(random.uniform(0.010, 0.030))
        presser.press(base, hold)
        t = threading.Timer(max(0.01, hold + random.uniform(-0.010, 0.025)),
                            keyboard.release, args=[Key.shift])
        t.daemon = True; t.start()
    elif char == ' ':  presser.press(Key.space)
    elif char == '\n': presser.press(Key.enter)
    elif char == '\t': presser.press(Key.tab)
    else:              presser.press(char)


def do_backspace():
    presser.press(Key.backspace, random.uniform(0.04, 0.09))
    time.sleep(random.uniform(0.04, 0.09))


# ── Typing engine ─────────────────────────────────────────────────────────────
def human_type(text, wpm, typo_chance, variance, burst, fatigue,
               stop_evt, status_cb, zero_errors=False):
    """
    zero_errors=True  →  used automatically when typo_chance == 0.0
                          (Code Mode). No typos, no accidental caps, no doubles.
    """
    base  = 60.0 / (wpm * 5)
    n     = len(text)
    drift = 0.0

    for i, char in enumerate(text):
        if stop_evt.is_set():
            break

        cl = char.lower()

        fat = 1.0
        if fatigue:
            fat = 1.0 + 0.20 * (1 / (1 + math.exp(-0.01 * (i - 300))))

        drift = drift * 0.95 + random.gauss(0, 0.015)
        drift = max(-0.3, min(0.3, drift))
        delay = max(0.025, random.gauss(base, base * variance) * fat * (1 + drift))

        if burst and random.random() < 0.12:
            delay *= random.uniform(0.35, 0.65)

        if char in '.!?':
            delay *= random.uniform(1.4, 2.2)
        elif char in ',;:':
            delay *= random.uniform(1.1, 1.5)
        elif char == ' ':
            delay *= random.uniform(1.1, 1.8)

        if i > 0 and text[i-1] in '.!?' and char == ' ':
            time.sleep(random.uniform(0.15, 0.55))

        if random.random() < 0.018:
            time.sleep(random.uniform(0.25, 1.1))

        if char == ' ' and i + 1 < n:
            nxt = text[i+1:].split(' ')[0].rstrip('.,!?;:')
            if len(nxt) >= 8:
                time.sleep(random.uniform(0.05, 0.25))

        # ── Error injection (skipped in zero_errors / code mode) ──
        if not zero_errors and typo_chance > 0:
            if char.isupper() and random.random() < 0.008:
                press_char(cl); time.sleep(random.uniform(0.07, 0.20))
                do_backspace(); time.sleep(random.uniform(0.04, 0.12))
            elif char.islower() and cl.isalpha() and random.random() < 0.005:
                press_char(char.upper()); time.sleep(random.uniform(0.06, 0.18))
                do_backspace(); time.sleep(random.uniform(0.04, 0.10))
            elif char in SHIFT_MAP and i+1 < n and text[i+1].isalpha() \
                    and random.random() < 0.006:
                press_char(char); time.sleep(delay)
                press_char(text[i+1].upper()); time.sleep(random.uniform(0.06, 0.16))
                do_backspace(); time.sleep(random.uniform(0.04, 0.10)); continue
            elif cl in NEIGHBORS and random.random() < typo_chance:
                wrong = random.choice(NEIGHBORS[cl])
                if char.isupper(): wrong = wrong.upper()
                press_char(wrong); time.sleep(delay * random.uniform(0.5, 1.2))
                do_backspace(); time.sleep(random.uniform(0.04, 0.14))
            elif cl.isalpha() and random.random() < 0.007:
                press_char(char); time.sleep(random.uniform(0.03, 0.09))
                press_char(char); time.sleep(random.uniform(0.08, 0.22))
                do_backspace(); time.sleep(random.uniform(0.04, 0.10))

        press_char(char)
        time.sleep(delay)

        if status_cb and i % 8 == 0:
            status_cb(min((i+1)/n, 1.0))

    presser.flush()
    stop_evt.set()


# ── File reading ──────────────────────────────────────────────────────────────
def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        if not HAS_PDF: return "[ERROR] PyMuPDF not installed."
        doc = _fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    if ext in (".docx", ".doc"):
        if not HAS_DOCX: return "[ERROR] python-docx not installed."
        d = _docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR] {e}"


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    NAV_ITEMS = [
        "Dashboard",
        "Editor",
        "Automations",
        "Triggers",
        "Logs",
        "Templates",
        "Devices",
        "Settings",
        "Help",
    ]

    def __init__(self):
        super().__init__()
        self.title("Typly")
        self.geometry("960x640")
        self.minsize(860, 580)
        self.resizable(False, False)
        self.configure(fg_color=C_BG)

        # App icon — applied after mainloop starts to override CTk defaults
        def _apply_icon():
            _ico_path = _resource_path("icon.ico")
            _png_path = _resource_path("icon.png")
            if os.path.exists(_ico_path):
                self.iconbitmap(default=_ico_path)
            if os.path.exists(_png_path):
                _img = Image.open(_png_path)
                _ico = ImageTk.PhotoImage(_img)
                self.wm_iconphoto(True, _ico)
                self._icon_ref = _ico
        self.after(50, _apply_icon)

        self._sidebar_visible = False

        self._stop_evt = threading.Event()
        self._stop_evt.set()

        self._wpm       = ctk.IntVar(value=65)
        self._typo      = ctk.DoubleVar(value=0.03)
        self._variance  = ctk.DoubleVar(value=0.35)
        self._burst     = ctk.BooleanVar(value=True)
        self._fatigue   = ctk.BooleanVar(value=True)
        self._preview   = ctk.BooleanVar(value=False)
        self._countdown = ctk.IntVar(value=5)
        self._progress  = ctk.DoubleVar(value=0)
        self._active_profile = ctk.StringVar(value="Office")

        # Settings vars
        self._theme     = ctk.StringVar(value="Dark")
        self._font_size = ctk.IntVar(value=12)
        self._always_top= ctk.BooleanVar(value=False)
        self._save_last = ctk.BooleanVar(value=True)

        # ── Session stats (Devices page) ──────────────────────────────────────
        self._session_start   = time.time()
        self._session_chars   = 0
        self._session_actions = 0

        # ── Automations ───────────────────────────────────────────────────────
        self._AUTOMATIONS_FILE = os.path.join(
            os.path.expanduser("~"), ".typly_automations.json")
        self._automations       = []
        self._auto_selected_idx = None

        # ── Activity log ──────────────────────────────────────────────────────
        self._log_entries = []

        # ── Triggers ──────────────────────────────────────────────────────────
        self._registered_triggers = []

        self._load_automations()
        self._load_settings()
        self._build()
        self._apply_profile("Office")
        self._start_esc_listener()
        self._show_page("Dashboard")

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load_settings(self):
        try:
            with open(SETTINGS_FILE) as f:
                d = json.load(f)
            self._theme.set(d.get("theme", "Dark"))
            self._font_size.set(d.get("font_size", 12))
            self._always_top.set(d.get("always_top", False))
            self._save_last.set(d.get("save_last", True))
        except: pass

    def _save_settings(self):
        d = dict(theme=self._theme.get(), font_size=self._font_size.get(),
                 always_top=self._always_top.get(), save_last=self._save_last.get())
        try:
            with open(SETTINGS_FILE, "w") as f: json.dump(d, f)
        except: pass

    # ── Build shell ───────────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Content area — now spans the full window; the sidebar floats on top
        # as a NavigationView-style flyout instead of pushing content aside.
        self._content = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self._content.grid(row=0, column=0, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # Scrim — dims/dismisses the flyout when clicked outside it
        self._sidebar_w = 220
        self._scrim = ctk.CTkFrame(self, fg_color=C_SCRIM, corner_radius=0)
        self._scrim.bind("<Button-1>", lambda e: self._toggle_sidebar())

        # Sidebar flyout — hidden off-screen (left) by default, slides in
        self._sidebar = ctk.CTkFrame(self, fg_color=C_SIDEBAR, corner_radius=0,
                                     width=self._sidebar_w, border_width=1,
                                     border_color=C_BORDER)
        self._sidebar.place(x=-self._sidebar_w, y=0, relheight=1)
        self._sidebar.pack_propagate(False)
        self._build_sidebar()
        self._sidebar_anim_job = None

        # Pages
        self._pages = {}
        self._pages["Dashboard"]   = self._build_dashboard_page()
        self._pages["Editor"]      = self._build_editor_page()
        self._pages["Automations"] = self._build_automations_page()
        self._pages["Triggers"]    = self._build_triggers_page()
        self._pages["Logs"]        = self._build_logs_page()
        self._pages["Templates"]   = self._build_templates_page()
        self._pages["Devices"]     = self._build_devices_page()
        self._pages["Settings"]    = self._build_settings_page()
        self._pages["Help"]        = self._build_help_page()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        # Logo area
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=64)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)
        _png = _resource_path("icon.png")
        if os.path.exists(_png):
            _pil = Image.open(_png).resize((26, 26), Image.LANCZOS)
            self._nav_logo_img = ctk.CTkImage(light_image=_pil, dark_image=_pil, size=(26, 26))
            ctk.CTkLabel(logo_frame, image=self._nav_logo_img, text=" Typly",
                         compound="left",
                         font=ctk.CTkFont("Segoe UI", 15, "bold"),
                         text_color=C_TEXT).place(relx=0.07, rely=0.5, anchor="w")
        else:
            ctk.CTkLabel(logo_frame, text="Typly",
                         font=ctk.CTkFont("Segoe UI", 15, "bold"),
                         text_color=C_TEXT).place(relx=0.07, rely=0.5, anchor="w")
        ctk.CTkButton(logo_frame, text="✕", width=28, height=28,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="transparent", hover_color=C_DARK,
                      text_color=C_MID, corner_radius=6,
                      command=self._toggle_sidebar
                      ).place(relx=0.93, rely=0.5, anchor="e")

        ctk.CTkFrame(self._sidebar, fg_color=C_BORDER, height=1).pack(fill="x")

        # Nav buttons — each paired with a thin accent indicator bar (Fluent
        # NavigationView selection style) that lights up for the active page.
        self._nav_btns = {}
        self._nav_indicators = {}
        for name in self.NAV_ITEMS:
            row = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=38)
            row.pack(fill="x", padx=10, pady=2)
            row.pack_propagate(False)
            indicator = ctk.CTkFrame(row, fg_color="transparent", width=3, corner_radius=2)
            indicator.place(relx=0, rely=0.5, anchor="w", relheight=0.6)
            btn = ctk.CTkButton(
                row, text=name, anchor="w",
                height=36,
                font=ctk.CTkFont("Segoe UI", 12),
                fg_color="transparent", hover_color=C_DARK,
                text_color=C_MID, corner_radius=6,
                command=lambda n=name: [self._show_page(n), self._toggle_sidebar()]
            )
            btn.place(relx=0, rely=0, relwidth=1, relheight=1, x=10)
            self._nav_btns[name] = btn
            self._nav_indicators[name] = indicator

        # Version at bottom
        ctk.CTkLabel(self._sidebar, text="v2.0",
                     font=ctk.CTkFont("Segoe UI", 8),
                     text_color=C_TEXT_DIM).pack(side="bottom", pady=10)

    def _show_page(self, name):
        for n, frame in self._pages.items():
            frame.grid_remove()
        self._pages[name].grid(row=0, column=0, sticky="nsew")
        for n, btn in self._nav_btns.items():
            if n == name:
                btn.configure(fg_color=C_DARK, text_color=C_TEXT)
                self._nav_indicators[n].configure(fg_color=C_ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=C_MID)
                self._nav_indicators[n].configure(fg_color="transparent")

    def _toggle_sidebar(self):
        opening = not self._sidebar_visible
        self._sidebar_visible = opening
        if self._sidebar_anim_job:
            self.after_cancel(self._sidebar_anim_job)
            self._sidebar_anim_job = None

        if opening:
            self._scrim.place(x=0, y=0, relwidth=1, relheight=1)
            self._scrim.lift()
            self._sidebar.lift()
        self._animate_sidebar(opening, step=0, total=12)

    def _animate_sidebar(self, opening, step, total):
        # Ease-out cubic for a smooth, native-feeling Fluent slide
        t = min(step / total, 1.0)
        eased = 1 - (1 - t) ** 3
        w = self._sidebar_w
        x = int(-w + w * eased) if opening else int(-eased * w)
        self._sidebar.place_configure(x=x)
        if step >= total:
            self._sidebar_anim_job = None
            if not opening:
                self._scrim.place_forget()
            return
        self._sidebar_anim_job = self.after(
            10, self._animate_sidebar, opening, step + 1, total)

    def _topbar(self, parent, title):
        """Shared topbar with hamburger, icon and title."""
        bar = ctk.CTkFrame(parent, fg_color=C_PANEL, corner_radius=0, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkButton(bar, text="☰", width=38, height=38,
                      font=ctk.CTkFont("Segoe UI", 18),
                      fg_color="transparent", hover_color=C_DARK,
                      text_color=C_TEXT, corner_radius=8,
                      command=self._toggle_sidebar).pack(side="left", padx=(8, 2))
        _png = _resource_path("icon.png")
        if os.path.exists(_png):
            _pil = Image.open(_png).resize((26, 26), Image.LANCZOS)
            _img = ctk.CTkImage(light_image=_pil, dark_image=_pil, size=(26, 26))
            lbl = ctk.CTkLabel(bar, image=_img, text="", width=26)
            lbl.image = _img
            lbl.pack(side="left", padx=(2, 4))
        ctk.CTkLabel(bar, text=title,
                     font=ctk.CTkFont("Segoe UI", 16, "bold"),
                     text_color=C_ACCENT2).pack(side="left", padx=(0, 8))
        return bar

    def _stub_page(self, title, items):
        """Generic coming-soon page with feature list."""
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        self._topbar(page, title)
        inner = ctk.CTkFrame(page, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        for item in items:
            row = ctk.CTkFrame(inner, fg_color=C_CARD, corner_radius=10,
                               border_width=1, border_color=C_BORDER)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=item,
                         font=ctk.CTkFont("Segoe UI", 12),
                         text_color=C_TEXT, anchor="w"
                         ).pack(padx=16, pady=12, anchor="w")
        ctk.CTkLabel(inner, text="Coming soon",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C_TEXT_DIM).pack(pady=(12, 0))
        return page

    # ══════════════════════════════════════════════════════════════════════════
    #  DASHBOARD PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_dashboard_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        bar = self._topbar(page, "Dashboard")

        # Status pill on right of topbar
        self._status_lbl = ctk.CTkLabel(bar, text="● READY",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=C_TEXT_DIM)
        self._status_lbl.pack(side="right", padx=14)

        # Progress bar
        self._prog_bar = ctk.CTkProgressBar(page, variable=self._progress,
                                             progress_color=C_ACCENT,
                                             fg_color=C_BORDER, height=3,
                                             corner_radius=0)
        self._prog_bar.pack(fill="x")
        self._progress.set(0)

        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        # ── LEFT: Text to type ──
        left = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=10,
                            border_width=1, border_color=C_BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="TEXT TO TYPE",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).grid(row=0, column=0, sticky="w", padx=12, pady=(10,2))
        self._text = ctk.CTkTextbox(left,
                                    font=ctk.CTkFont("Cascadia Mono", 11),
                                    fg_color=C_BG, text_color=C_TEXT,
                                    border_color=C_BORDER, border_width=1,
                                    scrollbar_button_color=C_ACCENT,
                                    corner_radius=6)
        self._text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        imp_row = ctk.CTkFrame(left, fg_color="transparent")
        imp_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        ctk.CTkButton(imp_row, text="📂  Import File", width=120, height=28,
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color=C_DARK, hover_color=C_ACCENT,
                      text_color=C_ACCENT2, corner_radius=8,
                      command=self._import_file).pack(side="left")
        self._file_lbl = ctk.CTkLabel(imp_row, text="",
                     font=ctk.CTkFont("Segoe UI", 8),
                     text_color=C_MID, anchor="w")
        self._file_lbl.pack(side="left", padx=8, fill="x", expand=True)

        # ── RIGHT: Controls ──
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        prof = ctk.CTkFrame(right, fg_color=C_PANEL, corner_radius=10,
                             border_width=1, border_color=C_BORDER)
        prof.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(prof, text="PROFILE",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(anchor="w", padx=12, pady=(8, 4))
        pf = ctk.CTkFrame(prof, fg_color="transparent")
        pf.pack(fill="x", padx=8, pady=(0, 8))
        self._profile_pill_btns = {}
        for name in PROFILES:
            pill = ctk.CTkButton(pf, text=name, height=26, width=0,
                                 font=ctk.CTkFont("Segoe UI", 10),
                                 fg_color=C_DARK, hover_color=C_BTN_HOV,
                                 text_color=C_ACCENT2, corner_radius=20,
                                 command=lambda n=name: self._apply_profile(n))
            pill.pack(side="left", padx=2)
            self._profile_pill_btns[name] = pill

        sl = ctk.CTkFrame(right, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        sl.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        sl.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sl, text="PARAMETERS",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).grid(row=0, column=0, sticky="w", padx=12, pady=(8,2))
        sf = ctk.CTkFrame(sl, fg_color="transparent")
        sf.grid(row=1, column=0, sticky="ew", padx=8, pady=(0,8))
        sf.columnconfigure(0, weight=1)
        self._wpm_lbl  = self._slider_row(sf, "SPEED",    self._wpm,      20,  200, 0, unit="WPM")
        self._typo_lbl = self._slider_row(sf, "TYPO %",   self._typo,     0,   0.2, 1, unit="%", scale=100, fmt=".1f")
        self._var_lbl  = self._slider_row(sf, "VARIANCE", self._variance, 0,   1.0, 2, fmt=".2f")

        tog = ctk.CTkFrame(right, fg_color=C_PANEL, corner_radius=10,
                            border_width=1, border_color=C_BORDER)
        tog.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(tog, text="MODE",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(anchor="w", padx=12, pady=(8,4))
        tgl = ctk.CTkFrame(tog, fg_color="transparent")
        tgl.pack(fill="x", padx=10, pady=(0,8))
        for label, var in [("Burst", self._burst), ("Fatigue", self._fatigue), ("Preview", self._preview)]:
            ctk.CTkSwitch(tgl, text=label, variable=var,
                          font=ctk.CTkFont("Segoe UI", 10),
                          text_color=C_ACCENT2,
                          progress_color=C_ACCENT, button_color=C_ACCENT2
                          ).pack(side="left", padx=(0, 10), pady=2)

        cd_frm = ctk.CTkFrame(right, fg_color=C_PANEL, corner_radius=10,
                               border_width=1, border_color=C_BORDER)
        cd_frm.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(cd_frm, text="COUNTDOWN",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(anchor="w", padx=12, pady=(8,2))
        cd = ctk.CTkFrame(cd_frm, fg_color="transparent")
        cd.pack(fill="x", padx=10, pady=(0,8))
        ctk.CTkSlider(cd, from_=2, to=30, variable=self._countdown,
                      number_of_steps=28, progress_color=C_DARK,
                      button_color=C_ACCENT, button_hover_color=C_BTN_HOV
                      ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._cd_lbl = ctk.CTkLabel(cd, text="5s", width=32,
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=C_ACCENT)
        self._cd_lbl.pack(side="left")
        self._countdown.trace_add("write",
            lambda *_: self._cd_lbl.configure(text=f"{self._countdown.get()}s"))

        act = ctk.CTkFrame(right, fg_color="transparent")
        act.grid(row=4, column=0, sticky="ew")
        self._start_btn = ctk.CTkButton(
            act, text="▶  START", height=42,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=C_ACCENT, text_color="#ffffff",
            hover_color=C_BTN_HOV, corner_radius=10,
            command=self._on_start)
        self._start_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._stop_btn = ctk.CTkButton(
            act, text="■  STOP", height=42, width=90,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=C_DARK, text_color=C_STOP,
            hover_color=C_STOP_HOV, corner_radius=10,
            state="disabled", command=self._on_stop)
        self._stop_btn.pack(side="left")

        self._preview_box = ctk.CTkTextbox(left, height=60,
                                           font=ctk.CTkFont("Cascadia Mono", 10),
                                           fg_color=C_BG, text_color=C_ACCENT2,
                                           border_color=C_BORDER, border_width=1,
                                           state="disabled", corner_radius=6)

        footer = ctk.CTkFrame(page, fg_color=C_PANEL, corner_radius=0, height=24)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkLabel(footer, text="ESC = emergency stop  ·  © 2025 Typly",
                     font=ctk.CTkFont("Segoe UI", 8),
                     text_color=C_TEXT_DIM).pack(expand=True)
        return page

    # ══════════════════════════════════════════════════════════════════════════
    #  EDITOR PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_editor_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self._topbar(page, "Editor")

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(page, fg_color=C_PANEL, corner_radius=0, height=44)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        ctk.CTkLabel(toolbar, text="INSERT VAR :",
                     font=ctk.CTkFont("Segoe UI", 8, "bold"),
                     text_color=C_MID).pack(side="left", padx=(12, 4))
        for tok in ["{name}", "{date}", "{time}", "{clipboard}", "{tab}", "{enter}"]:
            ctk.CTkButton(toolbar, text=tok, width=76, height=26,
                          font=ctk.CTkFont("Cascadia Mono", 9),
                          fg_color=C_DARK, hover_color=C_BTN_HOV,
                          text_color=C_ACCENT2, corner_radius=6,
                          command=lambda t=tok: self._ed_insert(t)
                          ).pack(side="left", padx=2, pady=8)
        self._ed_stats_lbl = ctk.CTkLabel(toolbar, text="0 words · 0 chars",
                                           font=ctk.CTkFont("Segoe UI", 9),
                                           text_color=C_MID)
        self._ed_stats_lbl.pack(side="right", padx=14)

        # ── Body ─────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: composition textbox
        ec = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        ec.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ec.grid_rowconfigure(1, weight=1)
        ec.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ec, text="COMPOSITION",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        self._ed_box = ctk.CTkTextbox(ec, font=ctk.CTkFont("Cascadia Mono", 12),
                                       fg_color=C_BG, text_color=C_TEXT,
                                       border_color=C_BORDER, border_width=1,
                                       wrap="word", corner_radius=6)
        self._ed_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self._ed_box.bind("<KeyRelease>", lambda e: self._ed_update_stats())

        # Find & Replace row
        fnr = ctk.CTkFrame(ec, fg_color=C_CARD, corner_radius=8,
                            border_width=1, border_color=C_BORDER)
        fnr.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        fnr.grid_columnconfigure(1, weight=1)
        fnr.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(fnr, text="FIND", font=ctk.CTkFont("Segoe UI", 8, "bold"),
                     text_color=C_MID).grid(row=0, column=0, padx=(10, 4), pady=8)
        self._ed_find = ctk.CTkEntry(fnr, placeholder_text="search…",
                                      fg_color=C_BG, border_color=C_BORDER,
                                      text_color=C_TEXT, height=28, corner_radius=6)
        self._ed_find.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=8)
        ctk.CTkLabel(fnr, text="REPLACE", font=ctk.CTkFont("Segoe UI", 8, "bold"),
                     text_color=C_MID).grid(row=0, column=2, padx=(0, 4), pady=8)
        self._ed_replace = ctk.CTkEntry(fnr, placeholder_text="replace with…",
                                         fg_color=C_BG, border_color=C_BORDER,
                                         text_color=C_TEXT, height=28, corner_radius=6)
        self._ed_replace.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=8)
        ctk.CTkButton(fnr, text="Replace All", width=90, height=28,
                      font=ctk.CTkFont("Segoe UI", 9),
                      fg_color=C_ACCENT, hover_color=C_BTN_HOV,
                      text_color="#fff", corner_radius=6,
                      command=self._ed_replace_all
                      ).grid(row=0, column=4, padx=(0, 10), pady=8)

        # Right panel
        rp = ctk.CTkFrame(body, fg_color="transparent")
        rp.grid(row=0, column=1, sticky="nsew")
        rp.grid_columnconfigure(0, weight=1)

        nc = ctk.CTkFrame(rp, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        nc.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(nc, text="SCRIPT NAME",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(anchor="w", padx=12, pady=(10, 2))
        self._ed_name = ctk.CTkEntry(nc, placeholder_text="My Script",
                                      fg_color=C_BG, border_color=C_BORDER,
                                      text_color=C_TEXT, height=32, corner_radius=6)
        self._ed_name.pack(fill="x", padx=10, pady=(0, 10))

        ac = ctk.CTkFrame(rp, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        ac.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(ac, text="ACTIONS",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(anchor="w", padx=12, pady=(10, 6))
        for txt, fg, hov, cmd in [
            ("▶  Send to Dashboard",   C_ACCENT, C_BTN_HOV,   self._ed_send_to_dash),
            ("💾  Save as Automation", C_DARK,   C_BTN_HOV,   self._ed_save_automation),
            ("🗑  Clear Editor",       C_DARK,   C_STOP_HOV,  self._ed_clear),
        ]:
            ctk.CTkButton(ac, text=txt, height=34,
                          font=ctk.CTkFont("Segoe UI", 10),
                          fg_color=fg, hover_color=hov,
                          text_color="#fff" if fg == C_ACCENT else C_ACCENT2,
                          corner_radius=8, command=cmd
                          ).pack(fill="x", padx=10, pady=(0, 6))

        vc = ctk.CTkFrame(rp, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        vc.grid(row=2, column=0, sticky="new")
        ctk.CTkLabel(vc, text="VARIABLE REFERENCE",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(anchor="w", padx=12, pady=(10, 6))
        for tok, desc in [
            ("{name}",      "Prompts for a name"),
            ("{date}",      "Today's date"),
            ("{time}",      "Current time"),
            ("{clipboard}", "Pastes clipboard"),
            ("{tab}",       "Tab character"),
            ("{enter}",     "Newline"),
        ]:
            r = ctk.CTkFrame(vc, fg_color="transparent")
            r.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(r, text=tok, width=84,
                         font=ctk.CTkFont("Cascadia Mono", 9),
                         text_color=C_ACCENT2, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=desc,
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=C_MID, anchor="w").pack(side="left")
        ctk.CTkFrame(vc, fg_color="transparent", height=6).pack()

        return page

    # ── Editor helpers ────────────────────────────────────────────────────────
    def _ed_insert(self, token):
        self._ed_box.insert("insert", token)
        self._ed_update_stats()

    def _ed_update_stats(self):
        text  = self._ed_box.get("1.0", "end-1c")
        words = len(text.split()) if text.strip() else 0
        self._ed_stats_lbl.configure(text=f"{words} words · {len(text)} chars")

    def _ed_replace_all(self):
        find = self._ed_find.get()
        rep  = self._ed_replace.get()
        if not find: return
        content = self._ed_box.get("1.0", "end-1c")
        self._ed_box.delete("1.0", "end")
        self._ed_box.insert("1.0", content.replace(find, rep))
        self._ed_update_stats()

    def _ed_send_to_dash(self):
        text = self._ed_box.get("1.0", "end-1c")
        if not text.strip(): return
        text = self._resolve_variables(text)
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._show_page("Dashboard")
        self._set_status("✓ LOADED FROM EDITOR", C_ACCENT_GRN)
        self._log("EDITOR", "Text loaded to Dashboard")
        self.after(2000, lambda: self._set_status("● READY", C_TEXT_DIM))

    def _ed_save_automation(self):
        name = self._ed_name.get().strip() or "Untitled Script"
        text = self._ed_box.get("1.0", "end-1c")
        if not text.strip(): return
        auto = {"name": name, "text": text, "created": time.strftime("%Y-%m-%d %H:%M")}
        self._automations.append(auto)
        self._save_automations()
        self._refresh_automations_list()
        self._refresh_snippets()
        self._log("AUTOMATION", f"Saved from Editor: {name}")

    def _ed_clear(self):
        self._ed_box.delete("1.0", "end")
        self._ed_name.delete(0, "end")
        self._ed_update_stats()

    def _resolve_variables(self, text):
        import datetime
        try:
            import pyperclip; clip = pyperclip.paste()
        except Exception:
            clip = ""
        for tok, val in {
            "{date}":      datetime.date.today().strftime("%B %d, %Y"),
            "{time}":      datetime.datetime.now().strftime("%I:%M %p"),
            "{clipboard}": clip,
            "{tab}":       "\t",
            "{enter}":     "\n",
        }.items():
            text = text.replace(tok, val)
        text = text.replace("{name}", "")
        return text

    # ══════════════════════════════════════════════════════════════════════════
    #  AUTOMATIONS PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_automations_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self._topbar(page, "Automations")

        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        # Left: list
        lc = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        lc.grid_rowconfigure(1, weight=1)
        lc.grid_columnconfigure(0, weight=1)
        lhdr = ctk.CTkFrame(lc, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        ctk.CTkLabel(lhdr, text="SAVED SCRIPTS",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(side="left")
        ctk.CTkButton(lhdr, text="+ New", width=56, height=24,
                      font=ctk.CTkFont("Segoe UI", 9),
                      fg_color=C_ACCENT, hover_color=C_BTN_HOV,
                      text_color="#fff", corner_radius=6,
                      command=self._auto_new).pack(side="right")
        self._auto_list_frame = ctk.CTkScrollableFrame(lc, fg_color="transparent",
                                                        scrollbar_button_color=C_DARK)
        self._auto_list_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
        self._auto_list_frame.grid_columnconfigure(0, weight=1)

        # Right: detail editor
        dc = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        dc.grid(row=0, column=1, sticky="nsew")
        dc.grid_rowconfigure(2, weight=1)
        dc.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(dc, text="SCRIPT DETAIL",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        nrow = ctk.CTkFrame(dc, fg_color="transparent")
        nrow.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        nrow.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(nrow, text="Name", width=50,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_TEXT).grid(row=0, column=0, sticky="w")
        self._auto_name_var   = ctk.StringVar()
        self._auto_name_entry = ctk.CTkEntry(nrow, textvariable=self._auto_name_var,
                                              fg_color=C_BG, border_color=C_BORDER,
                                              text_color=C_TEXT, height=30, corner_radius=6)
        self._auto_name_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self._auto_text_box = ctk.CTkTextbox(dc, font=ctk.CTkFont("Cascadia Mono", 11),
                                              fg_color=C_BG, text_color=C_TEXT,
                                              border_color=C_BORDER, border_width=1,
                                              corner_radius=6)
        self._auto_text_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))

        arow = ctk.CTkFrame(dc, fg_color="transparent")
        arow.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 12))
        for txt, fg, hov, cmd in [
            ("▶ Run Now",        C_ACCENT, C_BTN_HOV,  self._auto_run_selected),
            ("💾 Save",          C_DARK,   C_BTN_HOV,  self._auto_save_selected),
            ("✏ Edit in Editor", C_DARK,   C_BTN_HOV,  self._auto_open_in_editor),
        ]:
            ctk.CTkButton(arow, text=txt, height=34,
                          font=ctk.CTkFont("Segoe UI", 10),
                          fg_color=fg, hover_color=hov,
                          text_color="#fff" if fg == C_ACCENT else C_ACCENT2,
                          corner_radius=8, command=cmd).pack(side="left", padx=(0, 6))
        ctk.CTkButton(arow, text="🗑", height=34, width=40,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=C_DARK, hover_color=C_STOP_HOV,
                      text_color=C_STOP, corner_radius=8,
                      command=self._auto_delete_selected).pack(side="right")

        self._refresh_automations_list()
        return page

    # ── Automations helpers ───────────────────────────────────────────────────
    def _load_automations(self):
        try:
            with open(self._AUTOMATIONS_FILE) as f:
                self._automations = json.load(f)
        except Exception:
            self._automations = []

    def _save_automations(self):
        try:
            with open(self._AUTOMATIONS_FILE, "w") as f:
                json.dump(self._automations, f, indent=2)
        except Exception:
            pass

    def _refresh_automations_list(self):
        if not hasattr(self, "_auto_list_frame"): return
        for w in self._auto_list_frame.winfo_children(): w.destroy()
        if not self._automations:
            ctk.CTkLabel(self._auto_list_frame,
                         text="No scripts yet.\nClick + New to create one.",
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_TEXT_DIM, justify="center"
                         ).pack(pady=30)
            return
        for i, auto in enumerate(self._automations):
            is_sel = (i == self._auto_selected_idx)
            btn = ctk.CTkButton(self._auto_list_frame, text=auto["name"],
                                height=36, font=ctk.CTkFont("Segoe UI", 10),
                                fg_color=C_ACCENT if is_sel else C_CARD,
                                hover_color=C_BTN_HOV, text_color=C_TEXT,
                                anchor="w", corner_radius=8,
                                command=lambda idx=i: self._auto_select(idx))
            btn.pack(fill="x", pady=(2, 0))
            ctk.CTkLabel(self._auto_list_frame,
                         text=auto.get("created", ""),
                         font=ctk.CTkFont("Segoe UI", 8),
                         text_color=C_TEXT_DIM, anchor="w"
                         ).pack(fill="x", padx=4, pady=(0, 4))

    def _auto_select(self, idx):
        self._auto_selected_idx = idx
        auto = self._automations[idx]
        self._auto_name_var.set(auto["name"])
        self._auto_text_box.delete("1.0", "end")
        self._auto_text_box.insert("1.0", auto["text"])
        self._refresh_automations_list()

    def _auto_new(self):
        auto = {"name": "New Script", "text": "", "created": time.strftime("%Y-%m-%d %H:%M")}
        self._automations.append(auto)
        self._save_automations()
        self._auto_select(len(self._automations) - 1)

    def _auto_save_selected(self):
        if self._auto_selected_idx is None: return
        self._automations[self._auto_selected_idx]["name"] = self._auto_name_var.get()
        self._automations[self._auto_selected_idx]["text"] = self._auto_text_box.get("1.0", "end-1c")
        self._save_automations()
        self._refresh_automations_list()
        self._refresh_snippets()
        self._log("AUTOMATION", f"Saved: {self._auto_name_var.get()}")

    def _auto_delete_selected(self):
        if self._auto_selected_idx is None: return
        del self._automations[self._auto_selected_idx]
        self._auto_selected_idx = None
        self._save_automations()
        self._auto_name_var.set("")
        self._auto_text_box.delete("1.0", "end")
        self._refresh_automations_list()
        self._refresh_snippets()

    def _auto_run_selected(self):
        if self._auto_selected_idx is None: return
        text = self._resolve_variables(self._auto_text_box.get("1.0", "end-1c"))
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._show_page("Dashboard")
        self._log("AUTOMATION", f"Running: {self._auto_name_var.get()}")
        self.after(100, self._on_start)

    def _auto_open_in_editor(self):
        if self._auto_selected_idx is None: return
        auto = self._automations[self._auto_selected_idx]
        self._ed_name.delete(0, "end")
        self._ed_name.insert(0, auto["name"])
        self._ed_box.delete("1.0", "end")
        self._ed_box.insert("1.0", auto["text"])
        self._ed_update_stats()
        self._show_page("Editor")

    def _get_automation_names(self):
        return [a["name"] for a in self._automations]

    # ══════════════════════════════════════════════════════════════════════════
    #  TRIGGERS PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_triggers_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self._topbar(page, "Triggers & Rules")

        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: registered triggers
        lc = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        lc.grid_rowconfigure(1, weight=1)
        lc.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(lc, text="REGISTERED HOTKEYS",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        self._trigger_list_frame = ctk.CTkScrollableFrame(lc, fg_color="transparent",
                                                           scrollbar_button_color=C_DARK)
        self._trigger_list_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
        self._trigger_list_frame.grid_columnconfigure(0, weight=1)

        # Right: registration form
        rc = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        rc.grid(row=0, column=1, sticky="nsew")
        rc.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(rc, text="NEW TRIGGER",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID).pack(anchor="w", padx=14, pady=(12, 8))

        for label, attr, placeholder in [
            ("Hotkey",  "_trig_hk_var",     "e.g.  <ctrl>+<shift>+t"),
        ]:
            r = ctk.CTkFrame(rc, fg_color="transparent")
            r.pack(fill="x", padx=10, pady=(0, 6))
            r.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(r, text=label, width=60,
                         font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT
                         ).grid(row=0, column=0, sticky="w")
            setattr(self, attr, ctk.StringVar())
            ctk.CTkEntry(r, textvariable=getattr(self, attr),
                         placeholder_text=placeholder,
                         fg_color=C_BG, border_color=C_BORDER,
                         text_color=C_TEXT, height=30, corner_radius=6
                         ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        sc_r = ctk.CTkFrame(rc, fg_color="transparent")
        sc_r.pack(fill="x", padx=10, pady=(0, 6))
        sc_r.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sc_r, text="Script", width=60,
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT
                     ).grid(row=0, column=0, sticky="w")
        self._trig_script_var = ctk.StringVar()
        self._trig_script_menu = ctk.CTkOptionMenu(
            sc_r, variable=self._trig_script_var,
            values=self._get_automation_names() or ["— save a script first —"],
            fg_color=C_DARK, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOV, font=ctk.CTkFont("Segoe UI", 10))
        self._trig_script_menu.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        at_r = ctk.CTkFrame(rc, fg_color="transparent")
        at_r.pack(fill="x", padx=10, pady=(0, 8))
        at_r.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(at_r, text="Action", width=60,
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT
                     ).grid(row=0, column=0, sticky="w")
        self._trig_action_var = ctk.StringVar(value="Type Script")
        ctk.CTkOptionMenu(at_r, variable=self._trig_action_var,
                          values=["Type Script", "Open Dashboard", "Stop Typing"],
                          fg_color=C_DARK, button_color=C_ACCENT,
                          button_hover_color=C_BTN_HOV, font=ctk.CTkFont("Segoe UI", 10)
                          ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkButton(rc, text="+ Register Trigger", height=38,
                      font=ctk.CTkFont("Segoe UI", 11, "bold"),
                      fg_color=C_ACCENT, hover_color=C_BTN_HOV,
                      text_color="#fff", corner_radius=8,
                      command=self._trigger_register).pack(fill="x", padx=10, pady=8)

        ctk.CTkFrame(rc, fg_color=C_CARD, corner_radius=8,
                      border_width=1, border_color=C_BORDER).pack(fill="x", padx=10)
        ctk.CTkLabel(rc, text=(
            "ℹ  Hotkey format:  <ctrl>+<shift>+t\n"
            "Triggers fire while Typly is running.\n"
            "Use ESC to stop any active typing session."),
            font=ctk.CTkFont("Segoe UI", 9), text_color=C_MID,
            justify="left").pack(padx=20, pady=8, anchor="w")

        self._refresh_trigger_list()
        return page

    # ── Triggers helpers ──────────────────────────────────────────────────────
    def _trigger_register(self):
        hk     = self._trig_hk_var.get().strip()
        script = self._trig_script_var.get()
        action = self._trig_action_var.get()
        if not hk: return

        entry = {"hotkey": hk, "script": script, "action": action, "active": False}
        try:
            from pynput import keyboard as _kb
            def _fire():
                if action == "Stop Typing":
                    self._stop_evt.set()
                elif action == "Open Dashboard":
                    self.after(0, lambda: self._show_page("Dashboard"))
                else:
                    auto = next((a for a in self._automations if a["name"] == script), None)
                    if auto:
                        text = self._resolve_variables(auto["text"])
                        self.after(0, lambda: (
                            self._text.delete("1.0", "end"),
                            self._text.insert("1.0", text),
                            self._on_start()
                        ))
            gh = _kb.GlobalHotKeys({hk: _fire})
            gh.daemon = True
            gh.start()
            entry["_listener"] = gh
            entry["active"]    = True
        except Exception as e:
            entry["error"] = str(e)

        self._registered_triggers.append(entry)
        self._trig_hk_var.set("")
        self._refresh_trigger_list()
        self._log("TRIGGER", f"Registered: {hk} → {action}")

    def _trigger_delete(self, idx):
        t = self._registered_triggers[idx]
        if "_listener" in t:
            try: t["_listener"].stop()
            except: pass
        del self._registered_triggers[idx]
        self._refresh_trigger_list()
        self._log("TRIGGER", f"Removed: {t['hotkey']}")

    def _refresh_trigger_list(self):
        if not hasattr(self, "_trigger_list_frame"): return
        for w in self._trigger_list_frame.winfo_children(): w.destroy()
        if not self._registered_triggers:
            ctk.CTkLabel(self._trigger_list_frame,
                         text="No triggers registered yet.",
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_TEXT_DIM, justify="center"
                         ).pack(pady=30)
            return
        for i, t in enumerate(self._registered_triggers):
            row = ctk.CTkFrame(self._trigger_list_frame, fg_color=C_CARD,
                               corner_radius=8, border_width=1, border_color=C_BORDER)
            row.pack(fill="x", pady=3)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            sc = C_ACCENT_GRN if t.get("active") else C_STOP
            ctk.CTkLabel(top, text="●", font=ctk.CTkFont("Segoe UI", 10),
                         text_color=sc).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(top, text=t["hotkey"],
                         font=ctk.CTkFont("Cascadia Mono", 11, "bold"),
                         text_color=C_TEXT).pack(side="left")
            ctk.CTkButton(top, text="✕", width=24, height=24,
                          font=ctk.CTkFont("Segoe UI", 10),
                          fg_color="transparent", hover_color=C_STOP_HOV,
                          text_color=C_STOP, corner_radius=4,
                          command=lambda idx=i: self._trigger_delete(idx)
                          ).pack(side="right")
            ctk.CTkLabel(row,
                         text=f"{t['action']}  ·  {t.get('script', '')}",
                         font=ctk.CTkFont("Segoe UI", 9), text_color=C_MID
                         ).pack(anchor="w", padx=10, pady=(0, 8))

    # ══════════════════════════════════════════════════════════════════════════
    #  LOGS PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_logs_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self._topbar(page, "Logs & Activity")

        bar = ctk.CTkFrame(page, fg_color=C_PANEL, corner_radius=0, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="FILTER :",
                     font=ctk.CTkFont("Segoe UI", 8, "bold"),
                     text_color=C_MID).pack(side="left", padx=(12, 4))
        self._log_filter_var = ctk.StringVar(value="ALL")
        for flt in ["ALL", "TYPING", "AUTOMATION", "TRIGGER", "EDITOR"]:
            ctk.CTkButton(bar, text=flt, width=84, height=26,
                          font=ctk.CTkFont("Segoe UI", 9),
                          fg_color=C_DARK, hover_color=C_BTN_HOV,
                          text_color=C_ACCENT2, corner_radius=6,
                          command=lambda f=flt: self._log_filter(f)
                          ).pack(side="left", padx=2, pady=8)
        ctk.CTkButton(bar, text="⬇ Export", width=76, height=26,
                      font=ctk.CTkFont("Segoe UI", 9),
                      fg_color=C_DARK, hover_color=C_BTN_HOV,
                      text_color=C_ACCENT2, corner_radius=6,
                      command=self._log_export).pack(side="right", padx=2, pady=8)
        ctk.CTkButton(bar, text="🗑 Clear", width=70, height=26,
                      font=ctk.CTkFont("Segoe UI", 9),
                      fg_color=C_DARK, hover_color=C_STOP_HOV,
                      text_color=C_STOP, corner_radius=6,
                      command=self._log_clear).pack(side="right", padx=(4, 2), pady=8)

        self._log_box = ctk.CTkTextbox(page, font=ctk.CTkFont("Cascadia Mono", 10),
                                        fg_color=C_BG, text_color=C_TEXT,
                                        border_color=C_BORDER, border_width=0,
                                        state="disabled", corner_radius=0)
        self._log_box.pack(fill="both", expand=True)
        self._log_refresh_display()
        return page

    # ── Log helpers ───────────────────────────────────────────────────────────
    def _log(self, event_type, message):
        entry = {"time": time.strftime("%H:%M:%S"), "type": event_type, "msg": message}
        self._log_entries.append(entry)
        if hasattr(self, "_log_box"):
            try:
                if self._log_box.winfo_exists():
                    self._log_append_line(entry)
            except Exception:
                pass

    def _log_append_line(self, entry):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"[{entry['time']}]  {entry['type']:<14}  {entry['msg']}\n")
        self._log_box.configure(state="disabled")
        self._log_box.see("end")

    def _log_refresh_display(self):
        if not hasattr(self, "_log_box"): return
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        flt = self._log_filter_var.get() if hasattr(self, "_log_filter_var") else "ALL"
        for e in self._log_entries:
            if flt == "ALL" or e["type"] == flt:
                self._log_box.insert("end", f"[{e['time']}]  {e['type']:<14}  {e['msg']}\n")
        self._log_box.configure(state="disabled")
        self._log_box.see("end")

    def _log_filter(self, flt):
        self._log_filter_var.set(flt)
        self._log_refresh_display()

    def _log_clear(self):
        self._log_entries.clear()
        if hasattr(self, "_log_box"):
            self._log_box.configure(state="normal")
            self._log_box.delete("1.0", "end")
            self._log_box.configure(state="disabled")

    def _log_export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            title="Export Logs")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            for e in self._log_entries:
                f.write(f"[{e['time']}]  {e['type']:<14}  {e['msg']}\n")
        self._log("SYSTEM", f"Exported to {os.path.basename(path)}")

    # ══════════════════════════════════════════════════════════════════════════
    #  TEMPLATES PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_templates_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self._topbar(page, "Templates & Library")

        body = ctk.CTkScrollableFrame(page, fg_color="transparent",
                                       scrollbar_button_color=C_DARK)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        ctk.CTkLabel(body, text="BUILT-IN TEMPLATES",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID, anchor="w").pack(fill="x", pady=(0, 6))

        _TEMPLATES = [
            ("📧 Professional Email Reply",
             "Thank you for reaching out. I appreciate your message.\n\n"
             "I've reviewed your inquiry and would be happy to assist. "
             "Please allow me to address your points...\n\n"
             "Best regards,\n{name}"),
            ("📝 Meeting Notes Header",
             "MEETING NOTES\nDate: {date}  |  Time: {time}\n"
             "Attendees:\nAgenda:\n\n1. \n2. \n3. \n\n"
             "Action Items:\n—\n\nNext Meeting: "),
            ("💬 Customer Support Reply",
             "Hello,\n\nThank you for getting in touch. We're sorry to hear "
             "about the issue you've experienced.\n\n"
             "We've reviewed your case and here is what we found:\n\n"
             "[Details here]\n\n"
             "Please don't hesitate to reach out if you need further assistance.\n\n"
             "Kind regards,\nSupport Team"),
            ("🐍 Python Function",
             'def function_name(param1, param2):\n'
             '    """\n    Description.\n\n    Args:\n'
             '        param1: Description\n        param2: Description\n\n'
             '    Returns:\n        Description\n    """\n'
             '    result = None\n\n    # Your code here\n\n    return result'),
            ("📋 Bug Report",
             "**Bug Report**\n\n**Summary:** [Brief description]\n\n"
             "**Environment:**\n- OS: \n- Version: \n- Browser/App: \n\n"
             "**Steps to Reproduce:**\n1. \n2. \n3. \n\n"
             "**Expected:** \n\n**Actual:** \n\n**Screenshots:** "),
            ("🤝 LinkedIn Connect",
             "Hi {name},\n\nI came across your profile and was impressed by your work. "
             "I'd love to connect and explore potential collaboration.\n\n"
             "Looking forward to connecting!\n\nBest,\n"),
            ("📊 Status Update",
             "STATUS UPDATE — {date}\n\n"
             "✅ Completed:\n- \n- \n\n"
             "🔄 In Progress:\n- \n- \n\n"
             "🔜 Next Steps:\n- \n- \n\n"
             "⚠ Blockers:\n- None"),
            ("🔑 Password Reset Request",
             "Hello Support Team,\n\nI am writing to request a password reset "
             "for my account registered under this email address.\n\n"
             "Please let me know the steps to regain access.\n\n"
             "Thank you,\n{name}"),
        ]
        for title, text in _TEMPLATES:
            self._template_card(body, title, text)

        ctk.CTkLabel(body, text="MY SNIPPETS",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=C_MID, anchor="w").pack(fill="x", pady=(16, 6))
        self._snippets_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._snippets_frame.pack(fill="x")
        self._refresh_snippets()
        return page

    def _template_card(self, parent, title, text):
        card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10,
                             border_width=1, border_color=C_BORDER)
        card.pack(fill="x", pady=4)
        hrow = ctk.CTkFrame(card, fg_color="transparent")
        hrow.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(hrow, text=title,
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=C_TEXT).pack(side="left")
        ctk.CTkButton(hrow, text="Load →", width=70, height=26,
                      font=ctk.CTkFont("Segoe UI", 9),
                      fg_color=C_ACCENT, hover_color=C_BTN_HOV,
                      text_color="#fff", corner_radius=6,
                      command=lambda t=text: self._template_load(t)
                      ).pack(side="right")
        preview = text[:130].replace("\n", " ") + ("…" if len(text) > 130 else "")
        ctk.CTkLabel(card, text=preview, font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C_MID, anchor="w", wraplength=680
                     ).pack(fill="x", padx=12, pady=(0, 10))

    def _template_load(self, text):
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._show_page("Dashboard")
        self._set_status("✓ TEMPLATE LOADED", C_ACCENT_GRN)
        self._log("TEMPLATE", "Template loaded to Dashboard")
        self.after(2000, lambda: self._set_status("● READY", C_TEXT_DIM))

    def _refresh_snippets(self):
        if not hasattr(self, "_snippets_frame"): return
        for w in self._snippets_frame.winfo_children(): w.destroy()
        if not self._automations:
            ctk.CTkLabel(self._snippets_frame,
                         text="No saved automations yet. "
                              "Save scripts from the Automations page.",
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_TEXT_DIM).pack(pady=10, anchor="w")
            return
        for auto in self._automations:
            self._template_card(self._snippets_frame,
                                f"⚡ {auto['name']}", auto["text"])

    # ══════════════════════════════════════════════════════════════════════════
    #  DEVICES PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_devices_page(self):
        return self._stub_page("Devices & Sessions", [
            "Connected desktops & active sessions",
            "Remote disable / logout",
            "Sync status across devices",
        ])

    # ══════════════════════════════════════════════════════════════════════════
    #  HELP PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_help_page(self):
        return self._stub_page("Help & Support", [
            "Documentation & tutorials",
            "Keyboard shortcut guide",
            "Contact support / live chat",
        ])

    # ══════════════════════════════════════════════════════════════════════════
    #  SETTINGS PAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_settings_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        self._topbar(page, "Settings")

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent",
                                         scrollbar_button_color=C_DARK)
        scroll.pack(fill="both", expand=True)

        # ── Appearance ──
        app_card = self._card(scroll, title="APPEARANCE")
        self._setting_row(app_card, "Theme", widget_type="option",
                          var=self._theme, options=["Dark", "Light", "System"])
        self._setting_row(app_card, "Text area font size", widget_type="slider",
                          var=self._font_size, lo=9, hi=20)

        # ── Behaviour ──
        beh_card = self._card(scroll, title="BEHAVIOUR")
        self._setting_row(beh_card, "Keep window always on top",
                          widget_type="switch", var=self._always_top)
        self._setting_row(beh_card, "Remember last typed text",
                          widget_type="switch", var=self._save_last)

        # ── About ──
        about_card = self._card(scroll, title="ABOUT")
        for label, val in [
            ("App",       "Typly — Human Typing Simulator"),
            ("Version",   "2.0.0 (Rebuilt Edition)"),
            ("Copyright", "© 2025 Typly. All rights reserved."),
            ("Engine",    "pynput + customtkinter"),
        ]:
            row = ctk.CTkFrame(about_card, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(row, text=label, width=100,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_MID, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_TEXT, anchor="w").pack(side="left")

        # Save button
        ctk.CTkButton(scroll, text="Save Settings", height=40,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      fg_color=C_ACCENT, hover_color=C_BTN_HOV,
                      text_color="#fff", corner_radius=10,
                      command=self._apply_and_save_settings
                      ).pack(padx=18, pady=12, fill="x")

        return page

    def _apply_and_save_settings(self):
        self._save_settings()
        self.attributes("-topmost", self._always_top.get())
        # Update textbox font size
        self._text.configure(font=ctk.CTkFont("Cascadia Mono", self._font_size.get()))
        self._set_status("✓ SETTINGS SAVED", C_ACCENT_GRN)
        self.after(2000, lambda: self._set_status("● READY", C_TEXT_DIM))

    # ── UI helpers ────────────────────────────────────────────────────────────
    def _card(self, parent, title="", pad=(18, 6), **kw):
        outer = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=12,
                             border_width=1, border_color=C_BORDER)
        outer.pack(fill="x", padx=pad[0], pady=pad[1])
        if title:
            ctk.CTkLabel(outer, text=title,
                         font=ctk.CTkFont("Segoe UI", 8, "bold"),
                         text_color=C_TEXT_DIM, anchor="w"
                         ).pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkFrame(outer, fg_color=C_BORDER, height=1).pack(fill="x", padx=14)
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)
        return inner

    def _setting_row(self, parent, label, widget_type, var, options=None, lo=0, hi=100):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=label,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=C_TEXT, anchor="w").pack(side="left", fill="x", expand=True)
        if widget_type == "switch":
            ctk.CTkSwitch(row, text="", variable=var, width=48,
                          progress_color=C_ACCENT, button_color=C_ACCENT2
                          ).pack(side="right")
        elif widget_type == "option":
            ctk.CTkOptionMenu(row, values=options, variable=var,
                              fg_color=C_DARK, button_color=C_ACCENT,
                              button_hover_color=C_BTN_HOV, width=110,
                              font=ctk.CTkFont("Segoe UI", 10)
                              ).pack(side="right")
        elif widget_type == "slider":
            lbl = ctk.CTkLabel(row, text=str(var.get()), width=28,
                               font=ctk.CTkFont("Segoe UI", 10, "bold"),
                               text_color=C_ACCENT)
            lbl.pack(side="right")
            sl = ctk.CTkSlider(row, from_=lo, to=hi, variable=var,
                               width=110, progress_color=C_DARK,
                               button_color=C_ACCENT, button_hover_color=C_BTN_HOV)
            sl.pack(side="right", padx=8)
            sl.configure(command=lambda v: lbl.configure(text=str(int(v))))

    def _slider_row(self, parent, label, var, lo, hi, row,
                    unit="", scale=1, fmt=".0f"):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont("Segoe UI", 8, "bold"),
                     text_color=C_TEXT_DIM, anchor="w"
                     ).grid(row=row*2, column=0, sticky="w", pady=(12, 0))
        val_lbl = ctk.CTkLabel(parent, font=ctk.CTkFont("Segoe UI", 11, "bold"),
                               text_color=C_ACCENT, width=52)
        val_lbl.grid(row=row*2, column=2, sticky="e")
        if unit:
            ctk.CTkLabel(parent, text=unit,
                         font=ctk.CTkFont("Segoe UI", 8),
                         text_color=C_MID
                         ).grid(row=row*2, column=3, sticky="w", padx=(2, 0))
        def update(*_):
            val_lbl.configure(text=f"{var.get() * scale:{fmt}}")
        sl = ctk.CTkSlider(parent, from_=lo, to=hi, variable=var,
                           number_of_steps=200, progress_color=C_DARK,
                           button_color=C_ACCENT, button_hover_color=C_BTN_HOV)
        sl.grid(row=row*2+1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        sl.configure(command=lambda v: update())
        parent.columnconfigure(0, weight=1)
        update()
        return val_lbl

    # ── File import ───────────────────────────────────────────────────────────
    def _import_file(self):
        path = filedialog.askopenfilename(
            title="Import file",
            filetypes=[
                ("All supported", "*.txt *.md *.csv *.json *.xml *.html *.py "
                                  "*.docx *.doc *.pdf *.rtf *.log *.ini *.yaml *.yml"),
                ("Text files",    "*.txt *.md *.csv *.log *.ini"),
                ("Word docs",     "*.docx *.doc"),
                ("PDF",           "*.pdf"),
                ("Web/Data",      "*.html *.xml *.json *.yaml *.yml"),
                ("All files",     "*.*"),
            ]
        )
        if not path: return
        content = read_file(path)
        self._text.delete("1.0", "end")
        self._text.insert("1.0", content)
        fname = os.path.basename(path)
        chars = len(content)
        self._file_lbl.configure(
            text=f"📄 {fname}  —  {chars:,} chars loaded",
            text_color=C_ACCENT2)

    # ── Start / stop ──────────────────────────────────────────────────────────
    def _on_start(self):
        text = self._text.get("1.0", "end-1c")
        if not text.strip():
            self._set_status("⚠ NO TEXT", "#ffaa44"); return

        if self._preview.get():
            self._preview_box.pack(fill="x", padx=4, pady=(0, 8))
            self._preview_box.configure(state="normal")
            self._preview_box.delete("1.0", "end")
            est = int(len(text)/5/max(self._wpm.get(), 1))
            self._preview_box.insert("end",
                f"[PREVIEW — {len(text)} chars, ~{est}min at {self._wpm.get()} WPM]\n"
                f"{text[:200]}{'...' if len(text) > 200 else ''}")
            self._preview_box.configure(state="disabled")
            self._set_status("👁 PREVIEW", C_ACCENT2)
            return

        self._stop_evt.clear()
        self._progress.set(0)
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def _run(self, text):
        for i in range(self._countdown.get(), 0, -1):
            if self._stop_evt.is_set(): return self._reset_ui()
            self._set_status(f"⏳  STARTING IN {i}s", "#ffcc55")
            time.sleep(1)
        if self._stop_evt.is_set(): return self._reset_ui()

        self._set_status("⌨  TYPING…", C_ACCENT)
        self._log("TYPING", f"Started — {len(text)} chars @ {self._wpm.get()} WPM")
        zero_err = (self._typo.get() == 0.0)   # Code Mode = zero errors
        human_type(
            text,
            wpm=self._wpm.get(),
            typo_chance=self._typo.get(),
            variance=self._variance.get(),
            burst=self._burst.get(),
            fatigue=self._fatigue.get(),
            stop_evt=self._stop_evt,
            status_cb=lambda p: self.after(0, lambda v=p: self._progress.set(v)),
            zero_errors=zero_err,
        )
        self._session_chars   += len(text)
        self._session_actions += 1
        if not self._stop_evt.is_set():
            self._log("TYPING", "Completed successfully")
        else:
            self._log("TYPING", "Stopped by user")
        self._reset_ui(done=True)

    def _on_stop(self):
        self._stop_evt.set()
        self._reset_ui()

    def _reset_ui(self, done=False):
        self.after(0, lambda: [
            self._start_btn.configure(state="normal"),
            self._stop_btn.configure(state="disabled"),
            self._progress.set(1.0 if done else 0),
            self._set_status("✓ DONE" if done else "● READY",
                             C_ACCENT_GRN if done else C_TEXT_DIM),
        ])

    def _set_status(self, text, color=C_TEXT_DIM):
        self.after(0, lambda: self._status_lbl.configure(text=text, text_color=color))

    # ── Profile apply ─────────────────────────────────────────────────────────
    def _apply_profile(self, name):
        p = PROFILES.get(name)
        if not p: return
        self._wpm.set(p["wpm"])
        self._typo.set(p["typo"])
        self._variance.set(p["variance"])
        self._burst.set(p["burst"])
        self._fatigue.set(p["fatigue"])
        self._active_profile.set(name)
        for lbl, var, scale, fmt in [
            (self._wpm_lbl,  self._wpm,       1,  ".0f"),
            (self._typo_lbl, self._typo,    100,  ".1f"),
            (self._var_lbl,  self._variance,  1,  ".2f"),
        ]:
            lbl.configure(text=f"{var.get() * scale:{fmt}}")
        # Highlight active pill
        for n, btn in self._profile_pill_btns.items():
            if n == name:
                btn.configure(fg_color=C_ACCENT, text_color="#fff")
            else:
                btn.configure(fg_color=C_DARK, text_color=C_ACCENT2)

    def _start_esc_listener(self):
        Listener(on_press=lambda k: self._stop_evt.set() if k == Key.esc else None,
                 daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
#  SPLASH  (video loader edition)
# ══════════════════════════════════════════════════════════════════════════════
class SplashScreen(ctk.CTkToplevel):
    """
    Plays loader.mp4 full-frame as the app splash.
    Falls back to the original static splash if:
      - opencv-python is not installed, OR
      - loader.mp4 is not found next to the executable
    """
    FADE_STEPS  = 30
    # Fallback static splash constants
    QUOTE       = "Type like a human.\nThink like a machine."
    DURATION_MS = 2600

    def __init__(self, on_done):
        super().__init__()
        self._on_done   = on_done
        self._cap       = None
        self._fading    = False
        self._img_ref   = None          # keep PhotoImage alive

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#000000")
        self.resizable(False, False)

        # ── Try video path ────────────────────────────────────────────────────
        video_path = _resource_path("loader.mp4")
        cv2 = self._try_import_cv2()

        if cv2 and os.path.exists(video_path):
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                self._cap  = cap
                self._cv2  = cv2
                fps        = cap.get(cv2.CAP_PROP_FPS) or 30
                self._ms   = max(1, int(1000 / fps))
                W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if W < 1 or H < 1:
                    W, H = 640, 360

                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                self.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

                # Raw tkinter Canvas — fastest for per-frame image swaps
                import tkinter as _tk
                self._canvas = _tk.Canvas(
                    self, width=W, height=H,
                    bg="#000000", highlightthickness=0
                )
                self._canvas.pack(fill="both", expand=True)
                self._canvas_img_id = self._canvas.create_image(0, 0, anchor="nw")
                self.after(50, self._next_frame)
                return      # video branch active — skip fallback

            cap.release()

        # ── Fallback: original static splash ─────────────────────────────────
        self._build_static()

    # ── Video playback ────────────────────────────────────────────────────────
    def _next_frame(self):
        if self._fading:
            return
        ret, frame = self._cap.read()
        if not ret:
            # Video finished → begin fade-out
            self._begin_fade()
            return

        # BGR → RGB → PIL → PhotoImage  (no CTkImage overhead needed here)
        frame_rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        pil_img   = Image.fromarray(frame_rgb)
        tk_img    = ImageTk.PhotoImage(pil_img)
        self._canvas.itemconfig(self._canvas_img_id, image=tk_img)
        self._img_ref = tk_img         # prevent GC
        self.after(self._ms, self._next_frame)

    # ── Shared fade-out ───────────────────────────────────────────────────────
    def _begin_fade(self, step=0):
        if step == 0:
            self._fading = True
            if self._cap:
                self._cap.release()
                self._cap = None
        alpha = 1.0 - step / self.FADE_STEPS
        try:
            self.attributes("-alpha", max(0.0, alpha))
        except Exception:
            pass
        if step < self.FADE_STEPS:
            self.after(16, self._begin_fade, step + 1)
        else:
            self.destroy()
            self._on_done()

    # ── Static fallback ───────────────────────────────────────────────────────
    def _build_static(self):
        W, H = 400, 280
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
        self.configure(fg_color=C_BG)

        outer = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=16,
                              border_width=1, border_color=C_BORDER)
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)

        ctk.CTkFrame(outer, fg_color=C_ACCENT, corner_radius=0, height=3
                     ).pack(fill="x", side="top")

        _icon_path = _resource_path("icon.png")
        if os.path.exists(_icon_path):
            _pil = Image.open(_icon_path).resize((110, 110), Image.LANCZOS)
            self._splash_img = ctk.CTkImage(
                light_image=_pil, dark_image=_pil, size=(110, 110))
            ctk.CTkLabel(outer, image=self._splash_img, text="").pack(pady=(28, 4))
        else:
            ctk.CTkLabel(outer, text="⌨",
                         font=ctk.CTkFont("Segoe UI", 52),
                         text_color=C_ACCENT).pack(pady=(30, 4))

        ctk.CTkLabel(outer, text="Typly",
                     font=ctk.CTkFont("Segoe UI", 28, "bold"),
                     text_color=C_ACCENT2).pack()
        ctk.CTkLabel(outer, text=self.QUOTE,
                     font=ctk.CTkFont("Segoe UI", 12, slant="italic"),
                     text_color=C_MID, justify="center").pack(pady=(4, 16))

        self._prog_var = ctk.DoubleVar(value=0)
        ctk.CTkProgressBar(outer, variable=self._prog_var,
                           progress_color=C_ACCENT,
                           fg_color=C_BORDER, height=3, corner_radius=0
                           ).pack(fill="x", side="bottom")
        ctk.CTkLabel(outer, text="© 2025 Typly",
                     font=ctk.CTkFont("Segoe UI", 8),
                     text_color=C_TEXT_DIM).pack(side="bottom", pady=(0, 4))

        self._animate_bar()
        self.after(self.DURATION_MS, self._begin_fade)

    def _animate_bar(self, step=0, total=60):
        if step <= total:
            self._prog_var.set(step / total)
            self.after(self.DURATION_MS // total, self._animate_bar, step + 1, total)

    # ── Helper ────────────────────────────────────────────────────────────────
    @staticmethod
    def _try_import_cv2():
        try:
            import cv2
            return cv2
        except ImportError:
            return None
if __name__ == "__main__":
    splash_root = ctk.CTk()
    splash_root.withdraw()

    def launch_app():
        splash_root.after(0, _do_launch)

    def _do_launch():
        splash_root.destroy()
        app = App()
        app.mainloop()

    SplashScreen(on_done=launch_app)
    splash_root.mainloop()