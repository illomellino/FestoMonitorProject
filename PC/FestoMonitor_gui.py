#!/usr/bin/env python3
"""
Air Consumption Meter - ESP32 GUI
Interfaccia moderna per visualizzazione e storicizzazione
"""

import sys
import csv
import time
from datetime import datetime
from collections import deque
from pathlib import Path

import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFileDialog,
    QMessageBox, QStatusBar, QFrame
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg
import numpy as np

# ---------- Stile ----------
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
}
QPushButton:hover { background-color: #b4befe; }
QPushButton:pressed { background-color: #74c7ec; }
QPushButton:disabled { background-color: #45475a; color: #6c7086; }
QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
    min-width: 120px;
}
QLabel#valueLabel {
    font-size: 28px;
    font-weight: bold;
    color: #a6e3a1;
}
QLabel#unitLabel {
    font-size: 14px;
    color: #bac2de;
}
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
}
"""

class SerialWorker(QObject):
    data_received = pyqtSignal(float, float, float, float, float)  # t, P, F, mA_p, mA_f
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.running = False

    def connect(self, port, baud=115200):
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.running = True
            return True
        except Exception as e:
            self.error.emit(str(e))
            return False

    def disconnect(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

    def read_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if not line or line.startswith("ESP32"):
                    continue
                parts = line.split(',')
                if len(parts) >= 5:
                    t = float(parts[0]) / 1000.0
                    p = float(parts[1])
                    f = float(parts[2])
                    ma_p = float(parts[3])
                    ma_f = float(parts[4])
                    self.data_received.emit(t, p, f, ma_p, ma_f)
            except Exception as e:
                self.error.emit(str(e))
                time.sleep(0.05)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Consumption Meter – ESP32")
        self.resize(1200, 750)
        self.setStyleSheet(DARK_STYLE)

        self.worker = SerialWorker()
        self.worker.data_received.connect(self.on_data)
        self.worker.error.connect(self.on_error)

        self.buffer_size = 300          # ~60 s a 5 Hz
        self.time_data = deque(maxlen=self.buffer_size)
        self.press_data = deque(maxlen=self.buffer_size)
        self.flow_data = deque(maxlen=self.buffer_size)

        self.logging = False
        self.csv_file = None
        self.csv_writer = None
        self.start_time = None

        self._build_ui()
        self._setup_plots()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(100)  # 10 fps

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Barra connessione ---
        conn_box = QGroupBox("Connessione")
        conn_layout = QHBoxLayout(conn_box)

        self.port_combo = QComboBox()
        self.refresh_ports()
        conn_layout.addWidget(QLabel("Porta:"))
        conn_layout.addWidget(self.port_combo)

        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedWidth(40)
        btn_refresh.clicked.connect(self.refresh_ports)
        conn_layout.addWidget(btn_refresh)

        self.btn_connect = QPushButton("Connetti")
        self.btn_connect.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.btn_connect)

        self.btn_log = QPushButton("▶ Avvia Log")
        self.btn_log.setEnabled(False)
        self.btn_log.clicked.connect(self.toggle_logging)
        conn_layout.addWidget(self.btn_log)

        btn_load = QPushButton("📂 Carica storico")
        btn_load.clicked.connect(self.load_history)
        conn_layout.addWidget(btn_load)

        conn_layout.addStretch()
        layout.addWidget(conn_box)

        # --- Valori digitali ---
        values_layout = QHBoxLayout()

        # Pressione
        p_frame = QFrame()
        p_frame.setStyleSheet("background:#313244; border-radius:10px; padding:12px;")
        p_l = QVBoxLayout(p_frame)
        p_l.addWidget(QLabel("PRESSIONE", alignment=Qt.AlignmentFlag.AlignCenter))
        self.lbl_press = QLabel("---")
        self.lbl_press.setObjectName("valueLabel")
        self.lbl_press.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_l.addWidget(self.lbl_press)
        unit_p = QLabel("bar")
        unit_p.setObjectName("unitLabel")
        unit_p.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_l.addWidget(unit_p)
        values_layout.addWidget(p_frame)

        # Portata
        f_frame = QFrame()
        f_frame.setStyleSheet("background:#313244; border-radius:10px; padding:12px;")
        f_l = QVBoxLayout(f_frame)
        f_l.addWidget(QLabel("PORTATA", alignment=Qt.AlignmentFlag.AlignCenter))
        self.lbl_flow = QLabel("---")
        self.lbl_flow.setObjectName("valueLabel")
        self.lbl_flow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f_l.addWidget(self.lbl_flow)
        unit_f = QLabel("litri")
        unit_f.setObjectName("unitLabel")
        unit_f.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f_l.addWidget(unit_f)
        values_layout.addWidget(f_frame)

        # Correnti (diagnostica)
        c_frame = QFrame()
        c_frame.setStyleSheet("background:#313244; border-radius:10px; padding:12px;")
        c_l = QVBoxLayout(c_frame)
        c_l.addWidget(QLabel("CORRENTI (diagnostica)", alignment=Qt.AlignmentFlag.AlignCenter))
        self.lbl_curr = QLabel("--- / --- mA")
        self.lbl_curr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_curr.setStyleSheet("font-size:16px; color:#f9e2af;")
        c_l.addWidget(self.lbl_curr)
        values_layout.addWidget(c_frame)

        layout.addLayout(values_layout)

        # --- Grafici ---
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('#1e1e2e')
        layout.addWidget(self.plot_widget, stretch=1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto – seleziona porta e connetti")

    def _setup_plots(self):
        # Pressione
        self.plot_p = self.plot_widget.addPlot(row=0, col=0, title="Pressione [bar]")
        self.plot_p.showGrid(x=True, y=True, alpha=0.3)
        self.plot_p.setLabel('left', 'bar')
        self.curve_p = self.plot_p.plot(pen=pg.mkPen('#89b4fa', width=2))

        # Portata
        self.plot_f = self.plot_widget.addPlot(row=1, col=0, title="Portata [litri]")
        self.plot_f.showGrid(x=True, y=True, alpha=0.3)
        self.plot_f.setLabel('left', 'litri')
        self.plot_f.setLabel('bottom', 'Tempo [s]')
        self.curve_f = self.plot_f.plot(pen=pg.mkPen('#a6e3a1', width=2))

        self.plot_f.setXLink(self.plot_p)

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(f"{p.device} – {p.description}", p.device)

    def toggle_connection(self):
        if self.worker.running:
            self.worker.disconnect()
            self.btn_connect.setText("Connetti")
            self.btn_log.setEnabled(False)
            self.status.showMessage("Disconnesso")
        else:
            port = self.port_combo.currentData()
            if not port:
                QMessageBox.warning(self, "Errore", "Nessuna porta selezionata")
                return
            if self.worker.connect(port):
                self.btn_connect.setText("Disconnetti")
                self.btn_log.setEnabled(True)
                self.start_time = time.time()
                self.status.showMessage(f"Connesso a {port}")
                # Avvia lettura in thread
                import threading
                t = threading.Thread(target=self.worker.read_loop, daemon=True)
                t.start()
            else:
                QMessageBox.critical(self, "Errore", "Impossibile aprire la porta")

    def on_data(self, t, pressure, flow, ma_p, ma_f):
        if pressure < -900 or flow < -900:
            self.status.showMessage("⚠ Fault sensore rilevato!", 3000)
            return

        now = time.time() - self.start_time if self.start_time else t
        self.time_data.append(now)
        self.press_data.append(pressure)
        self.flow_data.append(flow)

        self.lbl_press.setText(f"{pressure:.3f}")
        self.lbl_flow.setText(f"{flow:.1f}")
        self.lbl_curr.setText(f"{ma_p:.2f} / {ma_f:.2f} mA")

        if self.logging and self.csv_writer:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.csv_writer.writerow([ts, f"{pressure:.4f}", f"{flow:.2f}", f"{ma_p:.3f}", f"{ma_f:.3f}"])

    def update_plots(self):
        if len(self.time_data) > 1:
            t = np.array(self.time_data)
            self.curve_p.setData(t, np.array(self.press_data))
            self.curve_f.setData(t, np.array(self.flow_data))

    def toggle_logging(self):
        if not self.logging:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva log", f"air_log_{datetime.now():%Y%m%d_%H%M%S}.csv",
                "CSV (*.csv)")
            if path:
                self.csv_file = open(path, 'w', newline='', encoding='utf-8')
                self.csv_writer = csv.writer(self.csv_file)
                self.csv_writer.writerow(["timestamp", "pressure_bar", "flow_liters", "mA_pressure", "mA_flow"])
                self.logging = True
                self.btn_log.setText("⏹ Ferma Log")
                self.status.showMessage(f"Logging attivo → {path}")
        else:
            self.logging = False
            if self.csv_file:
                self.csv_file.close()
            self.btn_log.setText("▶ Avvia Log")
            self.status.showMessage("Logging fermato")

    def load_history(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carica CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            times, presses, flows = [], [], []
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    times.append(i * 0.2)  # approx
                    presses.append(float(row.get('pressure_bar', 0)))
                    flows.append(float(row.get('flow_liters', 0)))
            self.curve_p.setData(times, presses)
            self.curve_f.setData(times, flows)
            self.status.showMessage(f"Caricato {path} ({len(times)} punti)")
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

    def on_error(self, msg):
        self.status.showMessage(f"Errore: {msg}")

    def closeEvent(self, event):
        self.worker.disconnect()
        if self.csv_file:
            self.csv_file.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())