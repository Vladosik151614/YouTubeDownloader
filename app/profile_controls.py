"""Small reusable controls for the main download profile row."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


def switch_card(label_text: str, switch, tooltip: str = "") -> QFrame:
    card = QFrame()
    card.setObjectName("smart_card")
    layout = QHBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(8)
    if tooltip:
        switch.setToolTip(tooltip)
    label = QLabel(label_text)
    if tooltip:
        label.setToolTip(tooltip)
    layout.addWidget(switch)
    layout.addWidget(label)
    return card
