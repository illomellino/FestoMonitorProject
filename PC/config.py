# ----------------------------------------------------------------------
# Stile dark theme
# ----------------------------------------------------------------------
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #11111b;
    color: #cdd6f4;
    font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 10px;
    font-weight: bold;
    color: #cdd6f4;
    background-color: #11111b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #89b4fa;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton:checked {
    background-color: #45475a;
    border-color: #89b4fa;
}
QPushButton:disabled {
    background-color: #1e1e2e;
    color: #6c7086;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
}
QStatusBar {
    background-color: #11111b;
    color: #a6adc8;
    border-top: 1px solid #313244;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background: #11111b;
    border-radius: 8px;
}
QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #313244;
    color: #89b4fa;
    font-weight: bold;
    border-bottom: 2px solid #89b4fa;
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
