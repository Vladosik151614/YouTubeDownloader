"""
sidebar_button.py - fixed-size painted icons for the left navigation.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton


class SidebarNavButton(QPushButton):
    def __init__(self, icon_name: str, label: str, parent=None):
        super().__init__(label, parent)
        self.icon_name = icon_name
        self.setObjectName("nav_btn")
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#ffffff" if self.property("active") == "true" else "#a8adb7")
        pen = QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(color)
        box = QRectF(13, (self.height() - 16) / 2, 16, 16)
        cx, cy = box.center().x(), box.center().y()

        if self.icon_name == "download":
            painter.drawLine(QPointF(cx, box.top() + 2), QPointF(cx, box.bottom() - 5))
            path = QPainterPath()
            path.moveTo(cx - 4, cy + 2)
            path.lineTo(cx, cy + 6)
            path.lineTo(cx + 4, cy + 2)
            painter.drawPath(path)
            painter.drawLine(QPointF(cx - 6, box.bottom() - 2), QPointF(cx + 6, box.bottom() - 2))
        elif self.icon_name == "settings":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
            for dx, dy in ((0, -8), (0, 8), (-8, 0), (8, 0), (-6, -6), (6, 6), (-6, 6), (6, -6)):
                painter.drawLine(QPointF(cx + dx * 0.7, cy + dy * 0.7), QPointF(cx + dx, cy + dy))
        elif self.icon_name == "history":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(box.adjusted(2, 2, -2, -2))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - 5))
            painter.drawLine(QPointF(cx, cy), QPointF(cx + 4, cy + 2))
        elif self.icon_name == "accounts":
            painter.drawEllipse(QRectF(cx - 4, cy - 6, 8, 8))
            painter.drawArc(QRectF(cx - 7, cy - 1, 14, 12), 20 * 16, 140 * 16)
        elif self.icon_name == "fixes":
            path = QPainterPath()
            path.moveTo(cx, box.top() + 1)
            path.lineTo(box.right() - 1, cy)
            path.lineTo(cx, box.bottom() - 1)
            path.lineTo(box.left() + 1, cy)
            path.closeSubpath()
            painter.drawPath(path)
        elif self.icon_name == "github":
            painter.drawLine(QPointF(cx, box.bottom() - 2), QPointF(cx, box.top() + 5))
            path = QPainterPath()
            path.moveTo(cx - 4, box.top() + 8)
            path.lineTo(cx, box.top() + 4)
            path.lineTo(cx + 4, box.top() + 8)
            painter.drawPath(path)
            painter.drawLine(QPointF(cx - 6, box.bottom() - 2), QPointF(cx + 6, box.bottom() - 2))
