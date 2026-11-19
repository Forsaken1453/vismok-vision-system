"""Tema visual Leviathan v2 — deep-sea futuristic dengan font bawaan.

Family font diambil dari app.ui.fonts.FAMILY setelah load_fonts().
"""
from app.ui.fonts import FAMILY

BODY = FAMILY["body"]
DISPLAY = FAMILY["display"]

# nama lama (sekian dipakai di pages) biar aman:
DISPLAY_FONT = DISPLAY

# Palette
BG        = "#060A13"
BG_PANEL  = "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0B1424, stop:1 #070D19)"
PANEL     = "#0B1424"
PANEL_2   = "#0F1D33"
LINE      = "#173252"
LINE_SOFT = "rgba(34,211,238,0.16)"
ACCENT    = "#22D3EE"
ACCENT_2  = "#38BDF8"
VIOLET    = "#8B5CF6"
TEXT      = "#E6F0FA"
TEXT_DIM  = "#9DB2C7"
MUTED     = "#5E7590"
GOOD      = "#34D399"
WARN      = "#FBBF24"
BAD       = "#F87171"

QSS = f"""
* {{
    font-family: "{BODY}";
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #041019;
}}
QMainWindow, QWidget {{ background-color: {BG}; }}

/* ---------- teks ---------- */
#Title     {{ font-family:"{DISPLAY}"; font-size:26px; font-weight:800;
             letter-spacing:4px; color:{ACCENT}; }}
#SubTitle  {{ font-size:14px; color:{TEXT_DIM}; letter-spacing:1px; }}
#BigLabel  {{ font-size:24px; font-weight:600; }}
#SpeciesName {{ font-family:"{DISPLAY}"; font-size:36px; font-weight:800;
                color:{ACCENT}; letter-spacing:1px; }}
#Hint      {{ font-size:17px; color:{TEXT}; letter-spacing:2px; }}
#Small     {{ font-size:12px; color:{MUTED}; }}
#SectionH  {{ font-family:"{DISPLAY}"; font-size:14px; color:{ACCENT_2};
              letter-spacing:2px; font-weight:700; }}
#Clock     {{ font-family:"{DISPLAY}"; font-size:15px; color:{TEXT_DIM};
              letter-spacing:1px; }}

/* ---------- sidebar ---------- */
#Sidebar {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0A1220, stop:1 #090F1C);
    border-right: 1px solid {LINE};
}}
#NavTitle {{
    font-family:"{DISPLAY}"; font-size:13px; color:{MUTED};
    letter-spacing:3px; font-weight:700;
}}
QPushButton#Nav {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    padding: 13px 14px;
    text-align: left;
    font-family: "{DISPLAY}";
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    color: {TEXT_DIM};
}}
QPushButton#Nav:hover {{ background: rgba(34,211,238,0.06); color: {TEXT}; }}
QPushButton#Nav:checked {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 rgba(34,211,238,0.16), stop:1 rgba(34,211,238,0.02));
    border-left: 3px solid {ACCENT};
    color: {ACCENT};
    font-weight: 700;
}}

/* ---------- panel/kartu ---------- */
QFrame#Card {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(17,32,55,0.92), stop:1 rgba(10,19,36,0.94));
    border: 1px solid {LINE};
    border-radius: 14px;
}}
QFrame#CardEmph {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(12,42,66,0.92), stop:1 rgba(9,25,42,0.95));
    border: 1px solid {ACCENT};
    border-radius: 14px;
}}
QFrame#Glass {{
    background: rgba(7,13,25,0.72);
    border: 1px solid {LINE_SOFT};
    border-radius: 14px;
}}
QFrame#GlassSurf {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(34,211,238,0.10), stop:1 rgba(7,13,25,0.78));
    border: 1px solid {LINE_SOFT};
    border-radius: 14px;
}}

/* ---------- tombol ---------- */
QPushButton {{
    background: {PANEL_2};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 10px 18px;
    font-family: "{DISPLAY}";
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:pressed {{ background: #12283F; }}

QPushButton#Primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0E7490, stop:1 #0F5E75);
    border: 1px solid {ACCENT};
    color: #FFFFFF;
    font-family: "{DISPLAY}";
    letter-spacing: 1px;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0891B2, stop:1 #0E7490);
}}
QPushButton#Danger {{ border-color: {BAD}; color: {BAD}; }}
QPushButton#Danger:hover {{ background: rgba(248,113,113,0.12); }}
QPushButton#Big {{
    font-size: 13px; padding: 11px 18px; border-radius: 10px;
}}
QPushButton:disabled {{ color: {MUTED}; border-color: {LINE}; }}

/* ---------- input ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {PANEL_2};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {PANEL_2};
    border: 1px solid {LINE};
    selection-background-color: {ACCENT};
    selection-color: #041019;
}}

/* ---------- tabel ---------- */
QTableWidget {{
    background: {PANEL};
    alternate-background-color: #0C1830;
    gridline-color: {LINE};
    border: 1px solid {LINE};
    border-radius: 10px;
    font-size: 13px;
}}
QTableWidget::item {{ padding: 6px; }}
QHeaderView::section {{
    background: {PANEL_2};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 2px solid {ACCENT};
    padding: 8px;
    font-weight: 700;
    font-family: "{DISPLAY}";
    font-size: 11px;
    letter-spacing: 1px;
}}

/* ---------- tab admin ---------- */
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 10px; top:-1px; }}
QTabBar::tab {{
    background: {PANEL};
    padding: 9px 18px;
    margin-right: 4px;
    border: 1px solid {LINE};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: {TEXT_DIM};
    font-family: "{DISPLAY}";
    font-size: 11px;
    letter-spacing: 1px;
}}
QTabBar::tab:selected {{ color: {ACCENT}; border-color: {ACCENT}; font-weight: 700; }}

QProgressBar#ConfBar {{
    background: {PANEL_2};
    border: 1px solid {LINE};
    border-radius: 8px;
    text-align: center;
    color: {TEXT};
    font-weight: 700;
    font-family: "{DISPLAY}";
    height: 20px;
}}
QProgressBar#ConfBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #155E75, stop:1 {ACCENT});
    border-radius: 7px;
}}
QProgressBar#MiniBar {{
    background: rgba(7,13,25,0.9);
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar#MiniBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {LINE}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_2}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{
    background: {PANEL_2}; color: {TEXT}; border: 1px solid {ACCENT};
}}
"""


def glow(widget, color=ACCENT, blur=30, parent=None):
    """QGraphicsDropShadowEffect glow untuk elemen penting.

    CATATAN: JANGAN setParent effect ke widget yg sama — Qt sudah
    mengambil ownership via setGraphicsEffect() (double-ownership
    = double delete = heap corruption).
    """
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(blur)
    eff.setColor(QColor(color))
    if parent is not None and parent is not widget:
        eff.setParent(parent)
    else:
        eff.setParent(None)
    widget.setGraphicsEffect(eff)
    return eff


def chip_text(text, color=MUTED):
    return f"[ {text} ]"
