# ----------------------------------------------------------------------
# Stile Grafico Moderno (Dark Theme ingegneristico)
# ----------------------------------------------------------------------
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #11111b;
    color: #cdd6f4;
    font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 10px;
    margin-top: 14px;
    font-weight: bold;
    font-size: 13px;
    background-color: #181825;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #89b4fa;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover { background-color: #b4befe; }
QPushButton:pressed { background-color: #74c7ec; }
QPushButton:disabled { background-color: #313244; color: #6c7086; }
QPushButton#measureBtn {
    background-color: #f9e2af;
    color: #1e1e2e;
}
QPushButton#measureBtn:checked {
    background-color: #fab387;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
    min-width: 110px;
    color: #cdd6f4;
}
QStatusBar {
    background-color: #11111b;
    color: #a6adc8;
    border-top: 1px solid #313244;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background: #181825;
    border-radius: 8px;
}
QTabBar::tab {
    background: #11111b;
    color: #a6adc8;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #313244;
    color: #89b4fa;
    font-weight: bold;
}
QTableWidget {
    background-color: #181825;
    gridline-color: #313244;
    color: #cdd6f4;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    padding: 6px;
    border: none;
    font-weight: bold;
}
QCheckBox { spacing: 8px; color: #cdd6f4; }
"""