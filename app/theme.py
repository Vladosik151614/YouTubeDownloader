"""
theme.py - application QSS themes.
"""

DARK_QSS = """
QMainWindow, QWidget#central {
    background: #1a1a2e;
    color: #e0e0e0;
}
QWidget {
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
/* Sidebar */
QWidget#sidebar {
    background: #16213e;
    border-right: 1px solid #0f3460;
}
QPushButton#nav_btn {
    background: transparent;
    color: #8892b0;
    border: none;
    border-radius: 6px;
    padding: 8px 12px 8px 38px;
    text-align: left;
    font-size: 13px;
}
QPushButton#nav_btn:hover {
    background: #0f3460;
    color: #e0e0e0;
}
QPushButton#nav_btn[active="true"] {
    background: #e94560;
    color: #fff;
    font-weight: bold;
}
/* Content */
QWidget#content_area {
    background: #1a1a2e;
}
/* URL field */
QLineEdit {
    background: #16213e;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 14px;
    selection-background-color: #e94560;
}
QLineEdit:focus {
    border: 1px solid #e94560;
}
/* Buttons */
QPushButton {
    background: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 13px;
}
QPushButton:hover {
    background: #16457a;
}
QPushButton:pressed {
    background: #0a2540;
}
QPushButton#primary_btn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #e94560, stop:1 #c62a47);
    color: #fff;
    font-weight: bold;
    font-size: 13px;
    padding: 9px 18px;
}
QPushButton#primary_btn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #ff5577, stop:1 #e94560);
}
/* Table */
QTableWidget {
    background: #16213e;
    alternate-background-color: #1a2850;
    gridline-color: transparent;
    border: none;
    border-radius: 6px;
}
QHeaderView::section {
    background: #0f3460;
    color: #8892b0;
    font-size: 12px;
    font-weight: bold;
    padding: 7px;
    border: none;
}
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #0f3460;
    height: 14px;
    text-align: center;
    color: #fff;
    font-size: 10px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #e94560, stop:1 #4fc3f7);
    border-radius: 4px;
}
/* GroupBox */
QGroupBox {
    border: 1px solid #0f3460;
    border-radius: 7px;
    margin-top: 10px;
    padding: 12px;
    font-size: 14px;
    font-weight: bold;
    color: #8892b0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    top: -2px;
    color: #8892b0;
}
/* ComboBox */
QComboBox {
    background: #16213e;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e0e0;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #16213e;
    border: 1px solid #0f3460;
    selection-background-color: #e94560;
}
/* CheckBox */
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 4px;
    border: 1px solid #0f3460;
    background: #16213e;
}
QCheckBox::indicator:checked {
    background: #e94560;
    image: none;
}
/* ScrollArea */
QScrollArea { border: none; }
QScrollBar:vertical {
    background: #16213e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #0f3460;
    border-radius: 4px;
    min-height: 20px;
}
/* StatusBar */
QStatusBar {
    background: #16213e;
    color: #8892b0;
    border-top: 1px solid #0f3460;
}
"""


THEMES = {
    "lux_graphite": {
        "bg": "#111214",
        "panel": "#1b1d21",
        "panel_alt": "#24272d",
        "control": "#2d3138",
        "control_hover": "#383d46",
        "control_pressed": "#181a1f",
        "border": "#3e434d",
        "accent": "#ef476f",
        "accent_alt": "#b82f51",
        "accent_hover": "#ff6b8c",
        "info": "#52d6c9",
        "text": "#f4f4f5",
        "muted": "#a8adb7",
    },
    "lux_midnight": {
        "bg": "#101116",
        "panel": "#191b23",
        "panel_alt": "#242735",
        "control": "#2b3040",
        "control_hover": "#394056",
        "control_pressed": "#171a24",
        "border": "#42495c",
        "accent": "#b88cff",
        "accent_alt": "#8057d8",
        "accent_hover": "#d0adff",
        "info": "#f5c45e",
        "text": "#f1f2f6",
        "muted": "#a9afc0",
    },
    "lux_silver": {
        "bg": "#f1f2f4",
        "panel": "#ffffff",
        "panel_alt": "#e7e9ed",
        "control": "#d9dde4",
        "control_hover": "#cbd1dc",
        "control_pressed": "#bcc3cf",
        "border": "#bfc5d0",
        "accent": "#b92f5a",
        "accent_alt": "#8f2447",
        "accent_hover": "#d84a72",
        "info": "#2364aa",
        "text": "#1d222a",
        "muted": "#667080",
    },
}

_QSS_CACHE: dict[str, str] = {}


def app_qss(theme_name: str) -> str:
    if theme_name not in {"lux_graphite", "lux_midnight", "lux_silver"}:
        theme_name = "lux_graphite"
    if theme_name in _QSS_CACHE:
        return _QSS_CACHE[theme_name]
    p = THEMES.get(theme_name, THEMES["lux_graphite"])
    qss = DARK_QSS
    replacements = {
        "#1a1a2e": p["bg"],
        "#16213e": p["panel"],
        "#1a2850": p["panel_alt"],
        "#0f3460": p["control"],
        "#16457a": p["control_hover"],
        "#0a2540": p["control_pressed"],
        "#e94560": p["accent"],
        "#c62a47": p["accent_alt"],
        "#ff5577": p["accent_hover"],
        "#4fc3f7": p["info"],
        "#8892b0": p["muted"],
        "#e0e0e0": p["text"],
    }
    for old, new in replacements.items():
        qss = qss.replace(old, new)
    qss += f"""
QFrame#tool_band {{
    background: {p["panel"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
}}
QTabWidget::pane {{
    background: {p["panel"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    top: -1px;
}}
QTabBar::tab {{
    background: {p["control_pressed"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-bottom: none;
    padding: 7px 13px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}}
QTabBar::tab:selected {{
    background: {p["panel"]};
    color: {p["text"]};
    font-weight: 700;
}}
QTabBar::tab:hover {{
    background: {p["control_hover"]};
}}
QGroupBox {{
    background: {p["panel_alt"]};
    border: 1px solid {p["border"]};
    color: {p["text"]};
}}
QGroupBox::title {{
    background: {p["panel_alt"]};
    color: {p["muted"]};
    padding: 0px 5px;
}}
QLabel {{
    color: {p["text"]};
}}
QLineEdit, QComboBox {{
    background: {p["panel"]};
    border: 1px solid {p["border"]};
    color: {p["text"]};
}}
QComboBox QAbstractItemView {{
    background: {p["panel"]};
    color: {p["text"]};
    selection-background-color: {p["accent"]};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 0px;
}}
QFrame#smart_card {{
    background: {p["panel_alt"]};
    border: 1px solid {p["border"]};
    border-radius: 7px;
}}
QLabel#mini_label {{
    color: {p["muted"]};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#section_title {{
    color: {p["text"]};
    font-size: 18px;
    font-weight: 700;
}}
QLabel#subtle {{
    color: {p["muted"]};
    font-size: 12px;
}}
QPushButton#action_icon_btn {{
    background: {p["control"]};
    border: 1px solid {p["border"]};
    border-radius: 7px;
    padding: 0px;
}}
QPushButton#action_icon_btn:hover {{
    background: {p["control_hover"]};
    border-color: {p["accent"]};
}}
QPushButton#action_icon_btn:pressed {{
    background: {p["control_pressed"]};
}}
"""
    _QSS_CACHE[theme_name] = qss
    return qss

