"""Animated status overlay for Dictate."""

from __future__ import annotations

import math

from PySide6 import QtCore, QtGui, QtWidgets


class StatusSignals(QtCore.QObject):
    """Thread-safe bridge from the dictation worker to the overlay."""

    changed = QtCore.Signal(str)
    level = QtCore.Signal(float)
    failed = QtCore.Signal(str)


class StatusOverlay(QtWidgets.QWidget):
    """Small, animated, focusless Material-style status pill."""

    _WINDOW_SIZE = QtCore.QSize(96, 48)
    _BOTTOM_MARGIN = 24
    _WAVEFORM_BARS = 17
    _SURFACE = QtGui.QColor("#2B2930")
    _OUTLINE = QtGui.QColor("#49454F")
    _PRIMARY = QtGui.QColor("#A8C7FA")

    def __init__(self) -> None:
        super().__init__()
        flags = (
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.ToolTip
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
            | QtCore.Qt.WindowType.WindowTransparentForInput
        )
        # X11 window managers may activate ordinary top-level windows despite
        # the no-focus hints. An override-redirect window is never managed and
        # therefore cannot take focus from the dictation target.
        if QtGui.QGuiApplication.platformName() == "xcb":
            flags |= QtCore.Qt.WindowType.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        if hasattr(QtCore.Qt.WidgetAttribute, "WA_X11DoNotAcceptFocus"):
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_X11DoNotAcceptFocus)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._status = "idle"
        self._phase = 0.0
        self._level_history = [0.0] * self._WAVEFORM_BARS
        self._animation = QtCore.QTimer(self)
        self._animation.setInterval(33)
        self._animation.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._phase += 0.2
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QtCore.Qt.GlobalColor.transparent)
        painter.setCompositionMode(
            QtGui.QPainter.CompositionMode.CompositionMode_SourceOver
        )
        unit = self.height() / 48
        pill = QtCore.QRectF(self.rect()).adjusted(
            4 * unit, 4 * unit, -4 * unit, -4 * unit
        )
        radius = pill.height() / 2

        painter.setBrush(self._SURFACE)
        painter.setPen(QtGui.QPen(self._OUTLINE, unit))
        painter.drawRoundedRect(pill, radius, radius)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

        if self._status == "listening":
            painter.setBrush(self._PRIMARY)
            center = pill.center().y()
            for index, level in enumerate(self._level_history):
                height = (2 + level * 19) * unit
                offset = index - (self._WAVEFORM_BARS - 1) / 2
                x = pill.center().x() + offset * 4 * unit - unit
                painter.drawRoundedRect(
                    QtCore.QRectF(x, center - height / 2, 2 * unit, height),
                    unit,
                    unit,
                )
        elif self._status == "transcribing":
            for index in range(3):
                pulse = (math.sin(self._phase + index * 1.4) + 1) / 2
                color = QtGui.QColor(self._PRIMARY)
                color.setAlphaF(0.38 + pulse * 0.62)
                painter.setBrush(color)
                dot_radius = (3 + pulse) * unit
                painter.drawEllipse(
                    QtCore.QPointF(
                        pill.center().x() + (index - 1) * 9 * unit,
                        pill.center().y(),
                    ),
                    dot_radius,
                    dot_radius,
                )
        elif self._status == "error":
            painter.setPen(
                QtGui.QPen(
                    self._PRIMARY,
                    3 * unit,
                    QtCore.Qt.PenStyle.SolidLine,
                    QtCore.Qt.PenCapStyle.RoundCap,
                )
            )
            center_x = pill.center().x()
            painter.drawLine(
                QtCore.QPointF(center_x, pill.center().y() - 8 * unit),
                QtCore.QPointF(center_x, pill.center().y() + 3 * unit),
            )
            painter.drawPoint(
                QtCore.QPointF(center_x, pill.center().y() + 9 * unit)
            )

    @QtCore.Slot(str)
    def set_status(self, status: str) -> None:
        self._status = status
        if status == "listening":
            self._level_history = [0.0] * self._WAVEFORM_BARS
        if status == "idle":
            self._animation.stop()
            self.hide()
            return
        if status == "transcribing":
            self._animation.start()
        else:
            self._animation.stop()
        screen = QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.setFixedSize(self._WINDOW_SIZE)
            self.move(
                area.center().x() - self.width() // 2,
                area.y() + area.height() - self.height() - self._BOTTOM_MARGIN,
            )
        self.update()
        self.show()

    @QtCore.Slot(float)
    def set_audio_level(self, level: float) -> None:
        """Update the listening waveform from a normalized microphone level."""
        if self._status != "listening":
            return
        level = max(0.0, min(1.0, level))
        self._level_history = self._level_history[1:] + [level]
        self.update()
