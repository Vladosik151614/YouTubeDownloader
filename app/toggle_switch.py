"""
toggle_switch.py — Капсульный ползунок (Toggle Switch) в стиле Modern UI
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._thumb_position = 1.0 if checked else 0.0
        self.setFixedSize(50, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    @Property(float)
    def thumb_position(self):
        return self._thumb_position

    @thumb_position.setter
    def thumb_position(self, pos: float):
        self._thumb_position = pos
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._animate_to(1.0 if checked else 0.0)
            self.toggled.emit(self._checked)

    def _animate_to(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._thumb_position)
        self._anim.setEndValue(target)
        self._anim.start()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw track capsule
        bg_color = QColor("#e94560") if self._checked else QColor("#334155")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_color))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 13, 13)

        # Draw sliding thumb circle
        thumb_radius = 9
        margin = 4
        x_min = margin + thumb_radius
        x_max = self.width() - margin - thumb_radius
        current_x = x_min + self._thumb_position * (x_max - x_min)

        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QRectF(current_x - thumb_radius, self.height()/2 - thumb_radius, thumb_radius * 2, thumb_radius * 2))
