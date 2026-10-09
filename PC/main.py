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
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return QIcon(path)
    return QIcon()


def close_native_splash():
    """Chiude lo splash screen nativo di PyInstaller non appena l'app è pronta."""
    try:
        import pyi_splash
        if pyi_splash.is_alive():
            pyi_splash.close()
    except ImportError:
        pass  # In ambiente di sviluppo (es. VSCode) pyi_splash non esiste e viene ignorato


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 1. Caricamento icone
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    # 2. Inizializzazione della finestra principale
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)

    # 3. Mostra la finestra principale
    window.show()

    # 4. Chiude lo splash screen nativo nell'esatto momento in cui la finestra appare
    close_native_splash()

    sys.exit(app.exec())