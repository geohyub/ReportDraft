"""Reusable summary card used by the desktop shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "-", detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricCardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricCardValue")
        self.detail_label = QLabel(detail)
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("metricCardDetail")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)
        layout.addStretch(1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_detail(self, detail: str) -> None:
        self.detail_label.setText(detail)

