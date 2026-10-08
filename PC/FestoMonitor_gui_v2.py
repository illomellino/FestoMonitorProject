#!/usr/bin/env python3
"""
Air Consumption Meter - ESP32 GUI
Versione completa:
- Grafico unico doppio asse Y
- Cursori di misura
- Tab valori grezzi
- Report PDF
- Selezione unità: l/min | Nl/min DIN1343 | Nl/min ISO | SCFM ANSI
- Temperatura configurabile da GUI
- FIX: ricarica tabella/buffer al load CSV
- FIX: report PDF con tutte le unità di portata
- FIX: cambio unità ricalcola totalizzatore sullo storico (non azzera)
"""

import sys
import csv
import time
import threading
from datetime import datetime
from collections import deque

import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFileDialog,
    QMessageBox, QStatusBar, QFrame, QCheckBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QObject
import pyqtgraph as pg
import numpy as np

# ReportLab (opzionale)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ----------------------------------------------------------------------
# Costanti di riferimento per la normalizzazione
# ----------------------------------------------------------------------
REF_CONDITIONS = {
    "l/min (grezzi)": None,
    "Nl/min – DIN 1343": {
        "Pn": 1.01325,      # bar
        "Tn": 273.15,       # K (0°C)
        "unit": "Nl/min",
        "name": "DIN 1343"
    },
    "Nl/min – ISO 6358/8778": {
        "Pn": 1.0,          # bar
        "Tn": 293.15,       # K (20°C)
        "unit": "Nl/min",
        "name": "ISO 6358/8778"
    },
    "SCFM – ANSI": {
        "Pn": 1.01325,      # bar
        "Tn": 288.706,      # K (15.56°C)
        "unit": "SCFM",
        "name": "ANSI"
    },
}

# Fattore di conversione Nl/min → SCFM
NL_TO_SCFM = 0.0353146667


# ----------------------------------------------------------------------
# Stile
# ----------------------------------------------------------------------
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
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover { background-color: #b4befe; }
QPushButton:pressed { background-color: #74c7ec; }
QPushButton:disabled { background-color: #45475a; color: #6c7086; }
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
    padding: 5px;
    min-width: 110px;
}
QLabel#valueLabel {
    font-size: 28px;
    font-weight: bold;
    color: #a6e3a1;
}
QLabel#unitLabel {
    font-size: 13px;
    color: #bac2de;
}
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
}
QTabWidget::pane {
    border: 1px solid #45475a;
    background: #1e1e2e;
}
QTabBar::tab {
    background: #313244;
    color: #cdd6f4;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #89b4fa;
    color: #1e1e2e;
}
QTableWidget {
    background-color: #1e1e2e;
    gridline-color: #45475a;
    color: #cdd6f4;
}
QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    padding: 6px;
    border: none;
}
QCheckBox { spacing: 8px; }
"""


class SerialWorker(QObject):
    data_received = pyqtSignal(float, float, float, float, float)  # t, P, F, Vp, Vf
    error = pyqtSignal(str)
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.running = False

    def connect(self, port, baud=115200):
        try:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = baud
            self.ser.timeout = 0.1
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.open()
            self.running = True

            # Sequenza reset ESP32
            try:
                self.ser.setDTR(False)
                self.ser.setRTS(True)
                time.sleep(0.1)
                self.ser.setDTR(True)
                self.ser.setRTS(False)
                time.sleep(0.1)
                self.ser.setRTS(True)
                self.ser.setDTR(True)
                time.sleep(0.05)
                self.ser.setDTR(False)
                time.sleep(0.05)
                self.ser.setRTS(False)
                time.sleep(0.7)
                self.ser.reset_input_buffer()
            except Exception:
                pass
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
                if not line:
                    continue
                if line.startswith("ESP32"):
                    self.status_msg.emit(line)
                    continue
                lower = line.lower()
                if any(k in lower for k in ("errore", "error", "fault", "non trovata", "failed")):
                    self.error.emit(line)
                    continue
                parts = line.split(',')
                if len(parts) >= 5:
                    try:
                        t = float(parts[0]) / 1000.0
                        p = float(parts[1])
                        f = float(parts[2])
                        vp = float(parts[3])
                        vf = float(parts[4])
                        self.data_received.emit(t, p, f, vp, vf)
                    except ValueError:
                        self.error.emit(f"Riga non valida: {line}")
            except Exception as e:
                self.error.emit(str(e))
                time.sleep(0.05)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Consumption Meter – ESP32 + ADS1115")
        self.resize(1450, 920)
        self.setStyleSheet(DARK_STYLE)

        self.worker = SerialWorker()
        self.worker.data_received.connect(self.on_data)
        self.worker.error.connect(self.on_error)
        self.worker.status_msg.connect(self._on_status_msg)

        # Buffer (default 10 minuti @ 10 Hz)
        self.sample_rate_hz = 10
        self.buffer_minutes = 10
        self.buffer_size = self.buffer_minutes * 60 * self.sample_rate_hz

        self.time_data = deque(maxlen=self.buffer_size)
        self.press_data = deque(maxlen=self.buffer_size)
        self.flow_data = deque(maxlen=self.buffer_size)      # valore convertito
        self.flow_raw_data = deque(maxlen=self.buffer_size)  # valore grezzo
        self.vp_data = deque(maxlen=self.buffer_size)
        self.vf_data = deque(maxlen=self.buffer_size)

        # Logging / totalizzatore
        self.logging = False
        self.csv_file = None
        self.csv_writer = None
        self.start_time = None
        self.total_volume = 0.0          # nell'unità selezionata
        self.last_sample_time = None

        # Unità e temperatura
        self.flow_unit = "l/min (grezzi)"
        self.temperature_c = 20.0
        self.atm_pressure = 1.01325     # bar

        # Cursori
        self.measure_active = False

        self._build_ui()
        self._setup_plots()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(100)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # === Barra superiore ===
        conn_box = QGroupBox("Connessione / Controlli")
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

        btn_load = QPushButton("📂 Carica")
        btn_load.clicked.connect(self.load_history)
        conn_layout.addWidget(btn_load)

        btn_reset = QPushButton("↺ Reset Totale")
        btn_reset.clicked.connect(self.reset_total)
        conn_layout.addWidget(btn_reset)

        self.btn_measure = QPushButton("📏 Misura")
        self.btn_measure.setObjectName("measureBtn")
        self.btn_measure.setCheckable(True)
        self.btn_measure.clicked.connect(self.toggle_measure)
        conn_layout.addWidget(self.btn_measure)

        self.btn_pdf = QPushButton("📄 Report PDF")
        self.btn_pdf.clicked.connect(self.generate_pdf_report)
        conn_layout.addWidget(self.btn_pdf)

        # --- Selezione unità ---
        conn_layout.addSpacing(12)
        conn_layout.addWidget(QLabel("Unità:"))
        self.combo_unit = QComboBox()
        self.combo_unit.addItems(list(REF_CONDITIONS.keys()))
        self.combo_unit.setMinimumWidth(180)
        self.combo_unit.currentTextChanged.connect(self._on_unit_changed)
        conn_layout.addWidget(self.combo_unit)

        btn_help = QPushButton("?")
        btn_help.setFixedWidth(32)
        btn_help.clicked.connect(self._show_unit_help)
        conn_layout.addWidget(btn_help)

        self.lbl_temp = QLabel("Temp °C:")
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(-20.0, 80.0)
        self.spin_temp.setDecimals(1)
        self.spin_temp.setSingleStep(0.5)
        self.spin_temp.setValue(20.0)
        self.spin_temp.valueChanged.connect(self._on_temp_changed)
        self.lbl_temp.setVisible(False)
        self.spin_temp.setVisible(False)
        conn_layout.addWidget(self.lbl_temp)
        conn_layout.addWidget(self.spin_temp)

        conn_layout.addStretch()
        layout.addWidget(conn_box)

        # === Valori digitali ===
        values_layout = QHBoxLayout()

        # Pressione
        p_frame = QFrame()
        p_frame.setStyleSheet("background:#313244; border-radius:10px; padding:10px;")
        pl = QVBoxLayout(p_frame)
        pl.addWidget(QLabel("PRESSIONE", alignment=Qt.AlignmentFlag.AlignCenter))
        self.lbl_press = QLabel("---")
        self.lbl_press.setObjectName("valueLabel")
        self.lbl_press.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(self.lbl_press)
        unit_p = QLabel("bar")
        unit_p.setObjectName("unitLabel")
        unit_p.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(unit_p)
        values_layout.addWidget(p_frame)

        # Portata
        f_frame = QFrame()
        f_frame.setStyleSheet("background:#313244; border-radius:10px; padding:10px;")
        fl = QVBoxLayout(f_frame)
        fl.addWidget(QLabel("PORTATA", alignment=Qt.AlignmentFlag.AlignCenter))
        self.lbl_flow = QLabel("---")
        self.lbl_flow.setObjectName("valueLabel")
        self.lbl_flow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fl.addWidget(self.lbl_flow)
        self.lbl_flow_unit = QLabel("l/min")
        self.lbl_flow_unit.setObjectName("unitLabel")
        self.lbl_flow_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fl.addWidget(self.lbl_flow_unit)
        values_layout.addWidget(f_frame)

        # Totalizzatore
        t_frame = QFrame()
        t_frame.setStyleSheet("background:#313244; border-radius:10px; padding:10px;")
        tl = QVBoxLayout(t_frame)
        tl.addWidget(QLabel("CONSUMO TOTALE", alignment=Qt.AlignmentFlag.AlignCenter))
        self.lbl_total = QLabel("0.0")
        self.lbl_total.setObjectName("valueLabel")
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_total.setStyleSheet("font-size:26px; font-weight:bold; color:#f9e2af;")
        tl.addWidget(self.lbl_total)
        self.lbl_total_unit = QLabel("l")
        self.lbl_total_unit.setObjectName("unitLabel")
        self.lbl_total_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.addWidget(self.lbl_total_unit)
        values_layout.addWidget(t_frame)

        # Tensioni
        c_frame = QFrame()
        c_frame.setStyleSheet("background:#313244; border-radius:10px; padding:10px;")
        cl = QVBoxLayout(c_frame)
        cl.addWidget(QLabel("TENSIONI", alignment=Qt.AlignmentFlag.AlignCenter))
        self.lbl_curr = QLabel("--- / --- V")
        self.lbl_curr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_curr.setStyleSheet("font-size:16px; color:#f9e2af;")
        cl.addWidget(self.lbl_curr)
        values_layout.addWidget(c_frame)

        layout.addLayout(values_layout)

        # === Tabs ===
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        # Tab Grafico
        graph_tab = QWidget()
        graph_layout = QVBoxLayout(graph_tab)
        graph_layout.setContentsMargins(0, 6, 0, 0)

        ctrl = QHBoxLayout()
        self.chk_press = QCheckBox("Pressione")
        self.chk_press.setChecked(True)
        self.chk_press.stateChanged.connect(self._update_curves_visibility)
        ctrl.addWidget(self.chk_press)

        self.chk_flow = QCheckBox("Portata")
        self.chk_flow.setChecked(True)
        self.chk_flow.stateChanged.connect(self._update_curves_visibility)
        ctrl.addWidget(self.chk_flow)

        ctrl.addSpacing(20)
        ctrl.addWidget(QLabel("Storia (minuti):"))
        self.spin_buffer = QSpinBox()
        self.spin_buffer.setRange(1, 60)
        self.spin_buffer.setValue(10)
        self.spin_buffer.valueChanged.connect(self._change_buffer_size)
        ctrl.addWidget(self.spin_buffer)
        ctrl.addStretch()
        graph_layout.addLayout(ctrl)

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('#1e1e2e')
        graph_layout.addWidget(self.plot_widget)

        # Pannello misure
        self.measure_panel = QFrame()
        self.measure_panel.setStyleSheet("background:#313244; border-radius:8px; padding:8px;")
        self.measure_panel.setVisible(False)
        mp = QHBoxLayout(self.measure_panel)
        self.lbl_measure = QLabel("Cursori disattivati")
        self.lbl_measure.setStyleSheet("font-size:13px;")
        mp.addWidget(self.lbl_measure)
        graph_layout.addWidget(self.measure_panel)

        self.tabs.addTab(graph_tab, "Grafico")

        # Tab grezzi
        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Tempo (s)", "Pressione (bar)", "Portata grezza",
            "Portata convertita", "V_p", "V_f", "Totale"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        raw_layout.addWidget(self.table)
        self.tabs.addTab(raw_tab, "Valori grezzi")

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto – seleziona porta e connetti")

    def _setup_plots(self):
        self.plot = self.plot_widget.addPlot(title="Air Flow Analyser")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel('left', 'Pressione', units='bar', color='#89b4fa')
        self.plot.setLabel('bottom', 'Tempo', units='s')
        self.plot.getAxis('left').setPen(pg.mkPen('#89b4fa'))
        self.plot.getAxis('left').setTextPen(pg.mkPen('#89b4fa'))

        self.plot.showAxis('right')
        self.plot.setLabel('right', 'Portata', color='#a6e3a1')
        self.plot.getAxis('right').setPen(pg.mkPen('#a6e3a1'))
        self.plot.getAxis('right').setTextPen(pg.mkPen('#a6e3a1'))

        self.vb_right = pg.ViewBox()
        self.plot.scene().addItem(self.vb_right)
        self.plot.getAxis('right').linkToView(self.vb_right)
        self.vb_right.setXLink(self.plot)
        self.plot.vb.sigResized.connect(self._update_views)

        self.curve_p = self.plot.plot(pen=pg.mkPen('#89b4fa', width=2))
        self.curve_f = pg.PlotDataItem(pen=pg.mkPen('#a6e3a1', width=2))
        self.vb_right.addItem(self.curve_f)

        self.cursor1 = pg.InfiniteLine(angle=90, movable=True,
                                       pen=pg.mkPen('#f38ba8', width=2, style=Qt.PenStyle.DashLine))
        self.cursor2 = pg.InfiniteLine(angle=90, movable=True,
                                       pen=pg.mkPen('#fab387', width=2, style=Qt.PenStyle.DashLine))
        self.cursor1.setVisible(False)
        self.cursor2.setVisible(False)
        self.plot.addItem(self.cursor1)
        self.plot.addItem(self.cursor2)
        self.cursor1.sigPositionChanged.connect(self._update_measure_labels)
        self.cursor2.sigPositionChanged.connect(self._update_measure_labels)

    # ------------------------------------------------------------------
    # Conversione portata
    # ------------------------------------------------------------------
    def convert_flow(self, flow_raw: float, pressure_gauge: float) -> float:
        """Converte portata grezza nell'unità selezionata (self.flow_unit)."""
        ref = REF_CONDITIONS[self.flow_unit]
        if ref is None:
            return flow_raw

        P_abs = pressure_gauge + self.atm_pressure
        T_k = self.temperature_c + 273.15

        if P_abs < 0.2 or T_k < 200:
            return flow_raw

        q = flow_raw * (P_abs / ref["Pn"]) * (ref["Tn"] / T_k)

        if ref["unit"] == "SCFM":
            q *= NL_TO_SCFM
        return q

    def convert_flow_for_unit(self, flow_raw: float, pressure_gauge: float, unit_key: str) -> float:
        """Converte portata grezza per una specifica unità (usato nel report PDF)."""
        ref = REF_CONDITIONS[unit_key]
        if ref is None:
            return flow_raw

        P_abs = pressure_gauge + self.atm_pressure
        T_k = self.temperature_c + 273.15

        if P_abs < 0.2 or T_k < 200:
            return flow_raw

        q = flow_raw * (P_abs / ref["Pn"]) * (ref["Tn"] / T_k)

        if ref["unit"] == "SCFM":
            q *= NL_TO_SCFM
        return q

    def _recalculate_from_history(self):
        """
        Ricalcola flow_data convertito e totalizzatore a partire dallo storico
        (flow_raw_data + press_data + time_data) usando l'unità e temperatura correnti.
        Non azzera: ricostruisce il totale integrando i campioni esistenti.
        """
        n = len(self.flow_raw_data)
        if n == 0:
            self.total_volume = 0.0
            self.lbl_total.setText("0.0")
            return

        times = list(self.time_data)
        presses = list(self.press_data)
        raws = list(self.flow_raw_data)

        new_flows = []
        total = 0.0
        for i in range(n):
            flow = self.convert_flow(raws[i], presses[i])
            new_flows.append(flow)
            if i > 0 and flow >= 0:
                dt_min = (times[i] - times[i - 1]) / 60.0
                if dt_min > 0:
                    total += flow * dt_min

        self.flow_data = deque(new_flows, maxlen=self.buffer_size)
        self.total_volume = total
        self.lbl_total.setText(f"{self.total_volume:.1f}")

        # Aggiorna colonna "Portata convertita" e "Totale" nella tabella
        # (allineata agli ultimi punti del buffer se la tabella è più corta)
        self._refresh_table_converted_column()

        # Aggiorna etichetta portata corrente se ci sono dati
        if new_flows:
            self.lbl_flow.setText(f"{new_flows[-1]:.2f}")

    def _refresh_table_converted_column(self):
        """Aggiorna le colonne Portata convertita e Totale nella tabella grezzi."""
        n_table = self.table.rowCount()
        n_buf = len(self.flow_data)
        if n_table == 0 or n_buf == 0:
            return

        # La tabella tiene al massimo 500 righe (le più recenti).
        # Il buffer può essere più lungo; allineiamo le ultime n_table righe.
        offset = max(0, n_buf - n_table)
        times = list(self.time_data)
        presses = list(self.press_data)
        raws = list(self.flow_raw_data)
        flows = list(self.flow_data)

        # Ricalcola totale progressivo solo per le righe visibili (approssimato
        # dal totale globale se non vogliamo ricalcolare tutto; qui ricalcoliamo
        # cumulativo dagli indici del buffer)
        running = 0.0
        for i in range(offset):
            if i > 0 and flows[i] >= 0:
                dt_min = (times[i] - times[i - 1]) / 60.0
                if dt_min > 0:
                    running += flows[i] * dt_min

        for row in range(n_table):
            idx = offset + row
            if idx >= n_buf:
                break
            flow = flows[idx]
            if idx > 0 and flow >= 0:
                dt_min = (times[idx] - times[idx - 1]) / 60.0
                if dt_min > 0:
                    running += flow * dt_min
            self.table.setItem(row, 3, QTableWidgetItem(f"{flow:.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{running:.2f}"))

    def _on_unit_changed(self, text: str):
        self.flow_unit = text
        needs_temp = REF_CONDITIONS[text] is not None
        self.lbl_temp.setVisible(needs_temp)
        self.spin_temp.setVisible(needs_temp)

        unit = REF_CONDITIONS[text]["unit"] if needs_temp else "l/min"
        self.lbl_flow_unit.setText(unit)
        self.lbl_total_unit.setText(unit.replace("/min", ""))  # Nl oppure SCF oppure l

        # Ricalcola sullo storico invece di azzerare
        self._recalculate_from_history()
        self.status.showMessage(
            f"Unità impostata: {text} – totalizzatore ricalcolato sullo storico", 4000
        )

    def _on_temp_changed(self, value: float):
        self.temperature_c = value
        # Ricalcola anche al cambio temperatura (influenza le normalizzazioni)
        if REF_CONDITIONS[self.flow_unit] is not None:
            self._recalculate_from_history()
            self.status.showMessage(
                f"Temperatura: {value:.1f} °C – valori ricalcolati", 3000
            )

    def _show_unit_help(self):
        msg = (
            "<h3>Condizioni di normalizzazione</h3>"
            "<b>l/min (grezzi)</b><br>"
            "Valore volumetrico diretto dal trasduttore. Nessuna correzione.<br><br>"
            "<b>Nl/min – DIN 1343</b><br>"
            "Pn = 1,01325 bar &nbsp;&nbsp; Tn = 0 °C (273,15 K)<br>"
            "Standard classico europeo.<br><br>"
            "<b>Nl/min – ISO 6358 / ISO 8778</b><br>"
            "Pn = 1,0 bar &nbsp;&nbsp; Tn = 20 °C (293,15 K)<br>"
            "Standard più usato in pneumatica.<br><br>"
            "<b>SCFM – ANSI</b><br>"
            "Pn = 1,01325 bar &nbsp;&nbsp; Tn = 15,56 °C (288,7 K)<br>"
            "Standard Cubic Feet per Minute.<br><br>"
            "<b>Formula:</b><br>"
            "Q<sub>norm</sub> = Q<sub>misurata</sub> × (P<sub>ass</sub> / Pn) × (Tn / T)<br>"
            "P<sub>ass</sub> = pressione manometrica + 1,01325 bar"
        )
        QMessageBox.information(self, "Legenda unità di portata", msg)

    # ------------------------------------------------------------------
    # Resto dei metodi
    # ------------------------------------------------------------------
    def _update_views(self):
        self.vb_right.setGeometry(self.plot.vb.sceneBoundingRect())
        self.vb_right.linkedViewChanged(self.plot.vb, self.vb_right.XAxis)

    def _update_curves_visibility(self):
        self.curve_p.setVisible(self.chk_press.isChecked())
        self.curve_f.setVisible(self.chk_flow.isChecked())

    def _change_buffer_size(self, minutes: int):
        self.buffer_minutes = minutes
        self.buffer_size = minutes * 60 * self.sample_rate_hz
        self.time_data = deque(self.time_data, maxlen=self.buffer_size)
        self.press_data = deque(self.press_data, maxlen=self.buffer_size)
        self.flow_data = deque(self.flow_data, maxlen=self.buffer_size)
        self.flow_raw_data = deque(self.flow_raw_data, maxlen=self.buffer_size)
        self.vp_data = deque(self.vp_data, maxlen=self.buffer_size)
        self.vf_data = deque(self.vf_data, maxlen=self.buffer_size)
        self.status.showMessage(f"Buffer: {minutes} min ({self.buffer_size} campioni)", 3000)

    def refresh_ports(self):
        self.port_combo.clear()
        for p in serial.tools.list_ports.comports():
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
                self.last_sample_time = None
                self._got_data_or_error = False
                self.status.showMessage(f"Connesso a {port} – attendo ESP32…")
                threading.Thread(target=self.worker.read_loop, daemon=True).start()
                QTimer.singleShot(4000, self._check_esp_alive)
            else:
                QMessageBox.critical(self, "Errore", "Impossibile aprire la porta")

    def _on_status_msg(self, msg):
        self._got_data_or_error = True
        self.status.showMessage(msg, 4000)

    def _check_esp_alive(self):
        if not self.worker.running or getattr(self, "_got_data_or_error", False):
            return
        self.status.showMessage("⚠ Nessun dato dall'ESP32", 10000)
        QMessageBox.warning(self, "Nessuna risposta",
                            "Controlla firmware, cablaggio ADS1115 o premi RESET.")

    def on_data(self, t, pressure, flow_raw, v_p, v_f):
        self._got_data_or_error = True

        if pressure < -900 or flow_raw < -900:
            msg = "⚠ FAULT SENSORE" if pressure <= -999 else "⚠ OVERRANGE"
            self.status.showMessage(msg, 5000)
            self.lbl_press.setText("FAULT" if pressure < -900 else f"{pressure:.3f}")
            self.lbl_flow.setText("FAULT" if flow_raw < -900 else f"{flow_raw:.1f}")
            self.lbl_curr.setText(f"{v_p:.2f} / {v_f:.2f} V")
            return

        now = time.time() - self.start_time if self.start_time else t

        # Conversione
        flow = self.convert_flow(flow_raw, pressure)

        # Totalizzatore
        if self.last_sample_time is not None and flow >= 0:
            dt_min = (now - self.last_sample_time) / 60.0
            self.total_volume += flow * dt_min
        self.last_sample_time = now

        # Buffer
        self.time_data.append(now)
        self.press_data.append(pressure)
        self.flow_data.append(flow)
        self.flow_raw_data.append(flow_raw)
        self.vp_data.append(v_p)
        self.vf_data.append(v_f)

        # Display
        self.lbl_press.setText(f"{pressure:.3f}")
        self.lbl_flow.setText(f"{flow:.2f}")
        self.lbl_total.setText(f"{self.total_volume:.1f}")
        self.lbl_curr.setText(f"{v_p:.2f} / {v_f:.2f} V")

        # Tabella (max 500 righe)
        if self.table.rowCount() > 500:
            self.table.removeRow(0)
        row = self.table.rowCount()
        self.table.insertRow(row)
        vals = [f"{now:.2f}", f"{pressure:.4f}", f"{flow_raw:.2f}",
                f"{flow:.2f}", f"{v_p:.3f}", f"{v_f:.3f}", f"{self.total_volume:.2f}"]
        for col, v in enumerate(vals):
            self.table.setItem(row, col, QTableWidgetItem(v))
        self.table.scrollToBottom()

        # Logging
        if self.logging and self.csv_writer:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.csv_writer.writerow([
                ts, f"{pressure:.4f}", f"{flow_raw:.3f}", f"{flow:.3f}",
                f"{v_p:.3f}", f"{v_f:.3f}", f"{self.total_volume:.3f}",
                self.flow_unit, f"{self.temperature_c:.1f}"
            ])
            if int(now * 5) % 10 == 0:
                self.csv_file.flush()

    def update_plots(self):
        if len(self.time_data) > 1:
            t = np.array(self.time_data)
            self.curve_p.setData(t, np.array(self.press_data))
            self.curve_f.setData(t, np.array(self.flow_data))
            if self.measure_active:
                self._update_measure_labels()

    def toggle_measure(self):
        self.measure_active = self.btn_measure.isChecked()
        self.cursor1.setVisible(self.measure_active)
        self.cursor2.setVisible(self.measure_active)
        self.measure_panel.setVisible(self.measure_active)

        if self.measure_active and len(self.time_data) > 10:
            t = np.array(self.time_data)
            mid = (t[0] + t[-1]) / 2
            span = (t[-1] - t[0]) * 0.15
            self.cursor1.setValue(mid - span)
            self.cursor2.setValue(mid + span)
            self._update_measure_labels()
        else:
            self.lbl_measure.setText("Cursori disattivati")

    def _update_measure_labels(self):
        if not self.measure_active or len(self.time_data) < 2:
            return
        t = np.array(self.time_data)
        p = np.array(self.press_data)
        f = np.array(self.flow_data)
        idx1 = np.argmin(np.abs(t - self.cursor1.value()))
        idx2 = np.argmin(np.abs(t - self.cursor2.value()))
        t1, t2 = t[idx1], t[idx2]
        p1, p2 = p[idx1], p[idx2]
        f1, f2 = f[idx1], f[idx2]
        text = (f"<b>C1</b>: {t1:.2f}s  P={p1:.3f}  F={f1:.2f} &nbsp;|&nbsp; "
                f"<b>C2</b>: {t2:.2f}s  P={p2:.3f}  F={f2:.2f} &nbsp;|&nbsp; "
                f"<b>Δt</b>={abs(t2-t1):.2f}s  <b>ΔP</b>={p2-p1:+.3f}  <b>ΔF</b>={f2-f1:+.2f}")
        self.lbl_measure.setText(text)

    def toggle_logging(self):
        if not self.logging:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva log",
                f"air_log_{datetime.now():%Y%m%d_%H%M%S}.csv", "CSV (*.csv)")
            if path:
                self.csv_file = open(path, 'w', newline='', encoding='utf-8')
                self.csv_writer = csv.writer(self.csv_file)
                self.csv_writer.writerow([
                    "timestamp", "pressure_bar", "flow_raw", "flow_converted",
                    "V_pressure", "V_flow", "total", "unit", "temperature_C"
                ])
                self.logging = True
                self.btn_log.setText("⏹ Ferma Log")
                self.status.showMessage(f"Logging → {path}")
        else:
            self.logging = False
            if self.csv_file:
                self.csv_file.close()
                self.csv_file = None
                self.csv_writer = None
            self.btn_log.setText("▶ Avvia Log")
            self.status.showMessage("Logging fermato")

    def reset_total(self):
        self.total_volume = 0.0
        self.lbl_total.setText("0.0")
        self.status.showMessage("Totalizzatore azzerato", 2000)

    def load_history(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carica CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            times, presses, flows_raw, flows_conv, vps, vfs, totals = (
                [], [], [], [], [], [], []
            )
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    times.append(i * 0.1)
                    presses.append(float(row.get('pressure_bar', 0) or 0))
                    raw_val = float(
                        row.get('flow_raw') or row.get('flow_Nl_min') or 0
                    )
                    flows_raw.append(raw_val)
                    # Preferisce il convertito se presente, altrimenti userà convert_flow dopo
                    conv = row.get('flow_converted')
                    if conv is not None and conv != '':
                        flows_conv.append(float(conv))
                    else:
                        flows_conv.append(None)  # placeholder, ricalcoleremo
                    vps.append(float(row.get('V_pressure', 0) or row.get('V_p', 0) or 0))
                    vfs.append(float(row.get('V_flow', 0) or row.get('V_f', 0) or 0))
                    totals.append(float(row.get('total', 0) or 0))

            n = len(times)
            if n == 0:
                QMessageBox.warning(self, "CSV vuoto", "Nessuna riga dati trovata.")
                return

            # Se manca flow_converted, calcola con l'unità corrente
            for i in range(n):
                if flows_conv[i] is None:
                    flows_conv[i] = self.convert_flow(flows_raw[i], presses[i])

            # --- FIX 1: svuota buffer e tabella, poi ricarica solo i nuovi dati ---
            self.time_data = deque(times, maxlen=self.buffer_size)
            self.press_data = deque(presses, maxlen=self.buffer_size)
            self.flow_raw_data = deque(flows_raw, maxlen=self.buffer_size)
            self.flow_data = deque(flows_conv, maxlen=self.buffer_size)
            self.vp_data = deque(vps, maxlen=self.buffer_size)
            self.vf_data = deque(vfs, maxlen=self.buffer_size)

            # Ricalcola totalizzatore sullo storico con unità corrente
            self._recalculate_from_history()

            # Svuota e ripopola la tabella (max 500 ultime righe)
            self.table.setRowCount(0)
            start = max(0, n - 500)
            running = 0.0
            # Pre-calcola running fino a start
            for i in range(start):
                if i > 0 and flows_conv[i] >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if dt_min > 0:
                        running += flows_conv[i] * dt_min

            for i in range(start, n):
                flow = flows_conv[i]
                if i > 0 and flow >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if dt_min > 0:
                        running += flow * dt_min
                row = self.table.rowCount()
                self.table.insertRow(row)
                vals = [
                    f"{times[i]:.2f}",
                    f"{presses[i]:.4f}",
                    f"{flows_raw[i]:.2f}",
                    f"{flow:.2f}",
                    f"{vps[i]:.3f}",
                    f"{vfs[i]:.3f}",
                    f"{running:.2f}",
                ]
                for col, v in enumerate(vals):
                    self.table.setItem(row, col, QTableWidgetItem(v))
            self.table.scrollToBottom()

            # Grafico
            self.curve_p.setData(times, presses)
            self.curve_f.setData(times, list(self.flow_data))

            # Display ultimi valori
            if presses:
                self.lbl_press.setText(f"{presses[-1]:.3f}")
                self.lbl_flow.setText(f"{list(self.flow_data)[-1]:.2f}")
                self.lbl_curr.setText(f"{vps[-1]:.2f} / {vfs[-1]:.2f} V")

            self.last_sample_time = times[-1] if times else None
            self.status.showMessage(f"Caricato {path} ({n} punti)", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

    def generate_pdf_report(self):
        if not REPORTLAB_AVAILABLE:
            QMessageBox.warning(self, "Manca reportlab", "Installa con:\npip install reportlab")
            return
        if len(self.press_data) < 5:
            QMessageBox.warning(self, "Dati insufficienti", "Servono più campioni.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Report PDF",
            f"report_air_{datetime.now():%Y%m%d_%H%M%S}.pdf", "PDF (*.pdf)")
        if not path:
            return

        try:
            p = np.array(self.press_data)
            t = np.array(self.time_data)
            raw = np.array(self.flow_raw_data)
            duration = t[-1] - t[0] if len(t) > 1 else 0

            # Calcola portate in tutte le unità
            unit_keys = list(REF_CONDITIONS.keys())
            flows_by_unit = {}
            totals_by_unit = {}
            for uk in unit_keys:
                fl = np.array([
                    self.convert_flow_for_unit(raw[i], p[i], uk)
                    for i in range(len(raw))
                ])
                flows_by_unit[uk] = fl
                # Integrale volume
                total_u = 0.0
                for i in range(1, len(t)):
                    if fl[i] >= 0:
                        dt_min = (t[i] - t[i - 1]) / 60.0
                        if dt_min > 0:
                            total_u += fl[i] * dt_min
                totals_by_unit[uk] = total_u

            doc = SimpleDocTemplate(path, pagesize=A4,
                                    rightMargin=18*mm, leftMargin=18*mm,
                                    topMargin=15*mm, bottomMargin=15*mm)
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, spaceAfter=10)
            h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, spaceBefore=8, spaceAfter=4)

            elements = []
            elements.append(Paragraph("Air Consumption Meter – Report", title_style))

            elements.append(Paragraph("<b>Header</b>", h2))
            header = [
                ["Logger:", "AirFlow (ESP32 + ADS1115)"],
                ["Unità portata (corrente):", self.flow_unit],
                ["Temperatura usata:", f"{self.temperature_c:.1f} °C"],
                ["Durata selezionata:", f"{duration:.1f} s"],
                ["Campioni:", str(len(p))],
            ]
            ht = Table(header, colWidths=[50*mm, 105*mm])
            ht.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
            ]))
            elements.append(ht)
            elements.append(Spacer(1, 10))

            # --- Statistiche pressione ---
            elements.append(Paragraph("<b>Statistics – Pressione</b>", h2))
            stats_p = [
                ["Grandezza", "Minimo", "Massimo", "Media", "Dev.Std"],
                ["Pressione (bar)", f"{np.min(p):.4f}", f"{np.max(p):.4f}",
                 f"{np.mean(p):.4f}", f"{np.std(p):.4e}"],
            ]
            st_p = Table(stats_p, colWidths=[45*mm, 32*mm, 32*mm, 32*mm, 32*mm])
            st_p.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#313244')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#888888')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(st_p)
            elements.append(Spacer(1, 8))

            # --- Statistiche portata in tutte le unità ---
            elements.append(Paragraph("<b>Statistics – Portata (tutte le unità)</b>", h2))
            stats_f = [
                ["Unità", "Minimo", "Massimo", "Media", "Dev.Std", "Consumo tot."],
            ]
            for uk in unit_keys:
                fl = flows_by_unit[uk]
                ref = REF_CONDITIONS[uk]
                short = ref["unit"] if ref else "l/min"
                vol_unit = short.replace("/min", "")
                stats_f.append([
                    uk,
                    f"{np.min(fl):.3f}",
                    f"{np.max(fl):.3f}",
                    f"{np.mean(fl):.3f}",
                    f"{np.std(fl):.3e}",
                    f"{totals_by_unit[uk]:.2f} {vol_unit}",
                ])

            st_f = Table(stats_f, colWidths=[48*mm, 24*mm, 24*mm, 24*mm, 28*mm, 32*mm])
            st_f.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#313244')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#888888')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(st_f)

            elements.append(Spacer(1, 16))
            elements.append(Paragraph(
                f"Generato il {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles['Normal']))
            elements.append(Paragraph(
                "Note: le portate normalizzate usano P_ass = P_gauge + 1,01325 bar "
                f"e T = {self.temperature_c:.1f} °C.",
                styles['Normal']))

            doc.build(elements)
            self.status.showMessage(f"Report salvato: {path}", 5000)
            QMessageBox.information(self, "PDF", f"Report creato:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Errore PDF", str(e))

    def on_error(self, msg):
        self._got_data_or_error = True
        self.status.showMessage(f"⚠ {msg}", 8000)
        if any(k in msg.lower() for k in ("ads1115", "non trovata", "failed")):
            if not getattr(self, "_critical_shown", False):
                self._critical_shown = True
                QMessageBox.critical(self, "Errore hardware", msg)

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