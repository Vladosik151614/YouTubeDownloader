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
    padding: 10px 12px;
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
    "graphite_red": {
        "bg": "#191919",
        "panel": "#242424",
        "panel_alt": "#2d2d2d",
        "control": "#333333",
        "control_hover": "#3f3f3f",
        "control_pressed": "#202020",
        "border": "#3a3a3a",
        "accent": "#e5485f",
        "accent_alt": "#b82d47",
        "accent_hover": "#ff5c72",
        "info": "#d7d7d7",
        "text": "#eeeeee",
        "muted": "#a7a7a7",
    },
    "graphite_purple": {
        "bg": "#18171c",
        "panel": "#24222b",
        "panel_alt": "#302d3a",
        "control": "#35323f",
        "control_hover": "#443f52",
        "control_pressed": "#24212c",
        "border": "#474150",
        "accent": "#8f5cff",
        "accent_alt": "#6f3fd3",
        "accent_hover": "#a77cff",
        "info": "#d6d0e5",
        "text": "#f0edf7",
        "muted": "#aaa3b8",
    },
    "light_gray": {
        "bg": "#eeeeee",
        "panel": "#f8f8f8",
        "panel_alt": "#e6e6e6",
        "control": "#dedede",
        "control_hover": "#d2d2d2",
        "control_pressed": "#c4c4c4",
        "border": "#c7c7c7",
        "accent": "#c83d55",
        "accent_alt": "#a52e43",
        "accent_hover": "#dd5268",
        "info": "#2d2d2d",
        "text": "#1f1f1f",
        "muted": "#666666",
    },
}


def app_qss(theme_name: str) -> str:
    p = THEMES.get(theme_name, THEMES["graphite_red"])
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
"""
    return qss

