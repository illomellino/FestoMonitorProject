import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ui_components import MainWindow


def resource_path(relative: str) -> str:
    """Path risorsa: funziona sia da sorgente sia da exe one-file PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


def load_app_icon() -> QIcon:
    candidates = [
        resource_path("icon.ico"),
        resource_path("app.ico"),
        resource_path("FestoMonitor.ico"),
        # sviluppo: icona nella cartella PC
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return QIcon(path)
    return QIcon()  # vuota se assente


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())