"""
Small painted action buttons that avoid missing emoji glyphs on Windows.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton


class ActionIconButton(QPushButton):
    COLORS = {
        "pause": "#f3c643",
        "resume": "#54c76d",
        "cancel": "#ff5a66",
        "retry": "#67b7ff",
        "folder": "#f0b84a",
        "details": "#c78cff",
        "expand": "#d7d7d7",
        "collapse": "#d7d7d7",
    }

    def __init__(self, action: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.setText("")
        self.setToolTip(tooltip)
        self.setFixedSize(32, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("action_icon_btn")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.COLORS.get(self.action, "#eeeeee"))
        pen = QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(color)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        if self.action == "pause":
            painter.drawRoundedRect(QRectF(cx - 6, cy - 7, 3.5, 14), 1.2, 1.2)
            painter.drawRoundedRect(QRectF(cx + 2.5, cy - 7, 3.5, 14), 1.2, 1.2)
        elif self.action == "resume":
            path = QPainterPath()
            path.moveTo(cx - 5, cy - 8)
            path.lineTo(cx - 5, cy + 8)
            path.lineTo(cx + 8, cy)
            path.closeSubpath()
            painter.drawPath(path)
        elif self.action == "cancel":
            painter.drawLine(int(cx - 6), int(cy - 6), int(cx + 6), int(cy + 6))
            painter.drawLine(int(cx + 6), int(cy - 6), int(cx - 6), int(cy + 6))
        elif self.action == "retry":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(cx - 8, cy - 8, 16, 16), 35 * 16, 285 * 16)
            path = QPainterPath()
            path.moveTo(cx + 8, cy - 7)
            path.lineTo(cx + 8, cy - 1)
            path.lineTo(cx + 2, cy - 4)
            path.closeSubpath()
            painter.setBrush(color)
            painter.drawPath(path)
        elif self.action == "folder":
            painter.drawRoundedRect(QRectF(cx - 10, cy - 3, 20, 11), 2, 2)
            painter.drawRoundedRect(QRectF(cx - 10, cy - 7, 9, 5), 1.5, 1.5)
        elif self.action == "details":
            painter.drawEllipse(QRectF(cx - 8, cy - 8, 16, 16))
            painter.setPen(QPen(QColor("#202020"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(cx), int(cy - 4), int(cx), int(cy + 2))
            painter.drawPoint(int(cx), int(cy + 6))
        elif self.action == "expand":
            path = QPainterPath()
            path.moveTo(cx - 3, cy - 7)
            path.lineTo(cx + 5, cy)
            path.lineTo(cx - 3, cy + 7)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        elif self.action == "collapse":
            path = QPainterPath()
            path.moveTo(cx - 7, cy - 3)
            path.lineTo(cx, cy + 5)
            path.lineTo(cx + 7, cy - 3)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
