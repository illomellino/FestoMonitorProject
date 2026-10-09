import csv
import time
import threading
from datetime import datetime
from collections import deque

import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFileDialog,
    QMessageBox, QStatusBar, QFrame, QCheckBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import QTimer, Qt
import pyqtgraph as pg
import numpy as np

from config import REF_CONDITIONS, DARK_STYLE
from converters import convert_flow
from ReadSerial import SerialWorker
from export_pdf import generate_pdf_report

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Consumption Meter – Festo Monitor Professional")
        self.resize(1450, 920)
        
        # --- MIGLIORAMENTO GRAFICO GLOBALE ---
        # Stile CSS rifinito per massimizzare il contrasto, la leggibilità e i bordi
        enhanced_dark_style = DARK_STYLE + """
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
            /* Stile specifico e ad alto contrasto per il tasto ? */
            QPushButton#btnHelp {
                background-color: #89b4fa;
                color: #11111b;
                border: 1px solid #b4befe;
                font-size: 14px;
                font-weight: 900;
            }
            QPushButton#btnHelp:hover {
                background-color: #b4befe;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 4px;
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
        """
        self.setStyleSheet(enhanced_dark_style)

        self.worker = SerialWorker()
        self.worker.data_received.connect(self.on_data)
        self.worker.error.connect(self.on_error)
        self.worker.status_msg.connect(self._on_status_msg)

        self.sample_rate_hz = 10
        self.buffer_minutes = 10
        self.buffer_size = self.buffer_minutes * 60 * self.sample_rate_hz

        self.time_data = deque(maxlen=self.buffer_size)
        self.press_data = deque(maxlen=self.buffer_size)
        self.flow_data = deque(maxlen=self.buffer_size)
        self.flow_raw_data = deque(maxlen=self.buffer_size)
        self.vp_data = deque(maxlen=self.buffer_size)
        self.vf_data = deque(maxlen=self.buffer_size)

        self.logging = False
        self.csv_file = None
        self.csv_writer = None
        self.start_time = None
        self.total_volume = 0.0
        self.last_sample_time = None

        self.flow_unit = "l/min (grezzi)"
        self.temperature_c = 20.0
        self.atm_pressure = 1.01325
        self.measure_active = False

        self._build_ui()
        self._setup_plots()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(100)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Controlli Superiori
        conn_box = QGroupBox("Gestione Connessione e Sessione")
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

        btn_load = QPushButton("📂 Carica CSV")
        btn_load.clicked.connect(self.load_history)
        conn_layout.addWidget(btn_load)

        btn_reset = QPushButton("↺ Reset Totale")
        btn_reset.clicked.connect(self.reset_total)
        conn_layout.addWidget(btn_reset)

        self.btn_measure = QPushButton("📏 Cursori")
        self.btn_measure.setObjectName("measureBtn")
        self.btn_measure.setCheckable(True)
        self.btn_measure.clicked.connect(self.toggle_measure)
        conn_layout.addWidget(self.btn_measure)

        self.btn_pdf = QPushButton("📄 Report PDF")
        self.btn_pdf.clicked.connect(lambda: generate_pdf_report(
            self, self.press_data, self.time_data, self.flow_raw_data, self.flow_unit, self.temperature_c))
        conn_layout.addWidget(self.btn_pdf)

        conn_layout.addSpacing(10)
        conn_layout.addWidget(QLabel("Unità:"))
        self.combo_unit = QComboBox()
        self.combo_unit.addItems(list(REF_CONDITIONS.keys()))
        self.combo_unit.setMinimumWidth(180)
        self.combo_unit.currentTextChanged.connect(self._on_unit_changed)
        conn_layout.addWidget(self.combo_unit)

        # --- FIX CONTRASTO TASTO ? ---
        btn_help = QPushButton("?")
        btn_help.setObjectName("btnHelp") # Collega allo stile CSS definito sopra
        btn_help.setFixedWidth(36)
        btn_help.setFixedHeight(30)
        btn_help.clicked.connect(self._show_unit_help)
        conn_layout.addWidget(btn_help)

        self.lbl_temp = QLabel("Temp °C:")
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(-20.0, 80.0)
        self.spin_temp.setValue(20.0)
        self.spin_temp.valueChanged.connect(self._on_temp_changed)
        self.lbl_temp.setVisible(False)
        self.spin_temp.setVisible(False)
        conn_layout.addWidget(self.lbl_temp)
        conn_layout.addWidget(self.spin_temp)

        conn_layout.addStretch()
        layout.addWidget(conn_box)

        # Indicatori numerici in tempo reale (Card principali)
        values_layout = QHBoxLayout()
        values_layout.setSpacing(12)

        def create_card(title, default_val, unit_val, val_color="#a6e3a1"):
            frame = QFrame()
            # --- FIX CONTRASTO E RIQUADRI PRINCIPALI ---
            # Sfondo netto, bordo ben definito con effetto rilievo e ombreggiatura visiva
            frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e1e2e, stop:1 #181825);
                    border: 1px solid #45475a;
                    border-top: 2px solid #585b70;
                    border-radius: 10px;
                    padding: 12px;
                }
            """)
            l = QVBoxLayout(frame)
            l.setContentsMargins(8, 8, 8, 8)
            
            title_lbl = QLabel(title, alignment=Qt.AlignmentFlag.AlignCenter)
            title_lbl.setStyleSheet("color: #bac2de; font-size: 11px; font-weight: bold; background: transparent; border: none;")
            l.addWidget(title_lbl)
            
            val_lbl = QLabel(default_val)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {val_color}; background: transparent; border: none;")
            l.addWidget(val_lbl)
            
            u_lbl = QLabel(unit_val, alignment=Qt.AlignmentFlag.AlignCenter)
            u_lbl.setStyleSheet("color: #9399b2; font-size: 12px; background: transparent; border: none;")
            l.addWidget(u_lbl)
            return frame, val_lbl, u_lbl

        self.p_card, self.lbl_press, _ = create_card("PRESSIONE", "---", "bar", "#89b4fa")
        self.f_card, self.lbl_flow, self.lbl_flow_unit = create_card("PORTATA", "---", "l/min", "#a6e3a1")
        self.t_card, self.lbl_total, self.lbl_total_unit = create_card("CONSUMO TOTALE", "0.0", "l", "#f9e2af")
        self.c_card, self.lbl_curr, _ = create_card("TENSIONI ADS1115", "--- / --- V", "Canali P / F", "#fab387")

        values_layout.addWidget(self.p_card)
        values_layout.addWidget(self.f_card)
        values_layout.addWidget(self.t_card)
        values_layout.addWidget(self.c_card)
        layout.addLayout(values_layout)

        # Tabs centrali (Grafici & Tabelle)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        graph_tab = QWidget()
        graph_layout = QVBoxLayout(graph_tab)
        
        ctrl = QHBoxLayout()
        self.chk_press = QCheckBox("Mostra Pressione")
        self.chk_press.setChecked(True)
        self.chk_press.stateChanged.connect(self._update_curves_visibility)
        ctrl.addWidget(self.chk_press)

        self.chk_flow = QCheckBox("Mostra Portata")
        self.chk_flow.setChecked(True)
        self.chk_flow.stateChanged.connect(self._update_curves_visibility)
        ctrl.addWidget(self.chk_flow)

        ctrl.addSpacing(20)
        ctrl.addWidget(QLabel("Finestra Storico (minuti):"))
        self.spin_buffer = QSpinBox()
        self.spin_buffer.setRange(1, 60)
        self.spin_buffer.setValue(10)
        self.spin_buffer.valueChanged.connect(self._change_buffer_size)
        ctrl.addWidget(self.spin_buffer)
        ctrl.addStretch()
        graph_layout.addLayout(ctrl)

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('#11111b')
        graph_layout.addWidget(self.plot_widget)

        self.measure_panel = QFrame()
        self.measure_panel.setStyleSheet("background:#1e1e2e; border: 1px solid #45475a; border-radius:8px; padding:8px;")
        self.measure_panel.setVisible(False)
        mp = QHBoxLayout(self.measure_panel)
        self.lbl_measure = QLabel("Cursori disattivati")
        mp.addWidget(self.lbl_measure)
        graph_layout.addWidget(self.measure_panel)

        self.tabs.addTab(graph_tab, "Grafico in Tempo Reale")

        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Tempo (s)", "Pressione (bar)", "Portata Grezza",
            "Portata Convertita", "V_p (Volt)", "V_f (Volt)", "Totale (l)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        raw_layout.addWidget(self.table)
        self.tabs.addTab(raw_tab, "Tabella Valori Grezzi")

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto – Seleziona la porta seriale per iniziare")

    def _setup_plots(self):
        self.plot = self.plot_widget.addPlot()
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel('left', 'Pressione', units='bar', color='#89b4fa')
        self.plot.setLabel('bottom', 'Tempo', units='s', color='#cdd6f4')
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

        self.cursor1 = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen('#f38ba8', width=2, style=Qt.PenStyle.DashLine))
        self.cursor2 = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen('#fab387', width=2, style=Qt.PenStyle.DashLine))
        self.cursor1.setVisible(False)
        self.cursor2.setVisible(False)
        self.plot.addItem(self.cursor1)
        self.plot.addItem(self.cursor2)
        self.cursor1.sigPositionChanged.connect(self._update_measure_labels)
        self.cursor2.sigPositionChanged.connect(self._update_measure_labels)

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
        self.status.showMessage(f"Buffer aggiornato a {minutes} min", 3000)

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
                QMessageBox.warning(self, "Attenzione", "Selezionare una porta COM valida.")
                return
            if self.worker.connect(port):
                self.btn_connect.setText("Disconnetti")
                self.btn_log.setEnabled(True)
                self.start_time = time.time()
                self.last_sample_time = None
                self.status.showMessage(f"Connesso a {port} – In attesa dati ESP32...")
                threading.Thread(target=self.worker.read_loop, daemon=True).start()
            else:
                QMessageBox.critical(self, "Errore", "Impossibile aprire la porta seriale.")

    def _on_status_msg(self, msg):
        self.status.showMessage(msg, 4000)

    def on_error(self, msg):
        self.status.showMessage(f"⚠ {msg}", 8000)

    def on_data(self, t, pressure, flow_raw, v_p, v_f):
        now = time.time() - self.start_time if self.start_time else t
        flow = convert_flow(flow_raw, pressure, self.flow_unit, self.temperature_c, self.atm_pressure)

        if self.last_sample_time is not None and flow >= 0:
            dt_min = (now - self.last_sample_time) / 60.0
            self.total_volume += flow * dt_min
        self.last_sample_time = now

        self.time_data.append(now)
        self.press_data.append(pressure)
        self.flow_data.append(flow)
        self.flow_raw_data.append(flow_raw)
        self.vp_data.append(v_p)
        self.vf_data.append(v_f)

        self.lbl_press.setText(f"{pressure:.3f}")
        self.lbl_flow.setText(f"{flow:.2f}")
        self.lbl_total.setText(f"{self.total_volume:.1f}")
        self.lbl_curr.setText(f"{v_p:.2f} / {v_f:.2f} V")

        if self.table.rowCount() > 500:
            self.table.removeRow(0)
        row = self.table.rowCount()
        self.table.insertRow(row)
        vals = [f"{now:.2f}", f"{pressure:.4f}", f"{flow_raw:.2f}", f"{flow:.2f}", f"{v_p:.3f}", f"{v_f:.3f}", f"{self.total_volume:.2f}"]
        for col, v in enumerate(vals):
            self.table.setItem(row, col, QTableWidgetItem(v))
        self.table.scrollToBottom()

        if self.logging and self.csv_writer:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.csv_writer.writerow([ts, f"{pressure:.4f}", f"{flow_raw:.3f}", f"{flow:.3f}", f"{v_p:.3f}", f"{v_f:.3f}", f"{self.total_volume:.3f}", self.flow_unit, f"{self.temperature_c:.1f}"])

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

    def _update_measure_labels(self):
        if not self.measure_active or len(self.time_data) < 2:
            return
        t = np.array(self.time_data)
        p = np.array(self.press_data)
        f = np.array(self.flow_data)
        idx1 = np.argmin(np.abs(t - self.cursor1.value()))
        idx2 = np.argmin(np.abs(t - self.cursor2.value()))
        text = (f"<b>C1</b>: {t[idx1]:.2f}s (P={p[idx1]:.3f}, F={f[idx1]:.2f}) | "
                f"<b>C2</b>: {t[idx2]:.2f}s (P={p[idx2]:.3f}, F={f[idx2]:.2f}) | "
                f"<b>Δt</b>={abs(t[idx2]-t[idx1]):.2f}s  <b>ΔP</b>={p[idx2]-p[idx1]:+.3f}")
        self.lbl_measure.setText(text)

    def _on_unit_changed(self, text: str):
        self.flow_unit = text
        needs_temp = REF_CONDITIONS[text] is not None
        self.lbl_temp.setVisible(needs_temp)
        self.spin_temp.setVisible(needs_temp)
        unit = REF_CONDITIONS[text]["unit"] if needs_temp else "l/min"
        self.lbl_flow_unit.setText(unit)
        self.lbl_total_unit.setText(unit.replace("/min", ""))
        self._recalculate_from_history()

    def _on_temp_changed(self, value: float):
        self.temperature_c = value
        if REF_CONDITIONS[self.flow_unit] is not None:
            self._recalculate_from_history()

    def _recalculate_from_history(self):
        if not self.flow_raw_data:
            return
        new_flows, total = [], 0.0
        times = list(self.time_data)
        presses = list(self.press_data)
        raws = list(self.flow_raw_data)
        for i in range(len(raws)):
            flow = convert_flow(raws[i], presses[i], self.flow_unit, self.temperature_c, self.atm_pressure)
            new_flows.append(flow)
            if i > 0 and flow >= 0:
                dt_min = (times[i] - times[i - 1]) / 60.0
                if dt_min > 0:
                    total += flow * dt_min
        self.flow_data = deque(new_flows, maxlen=self.buffer_size)
        self.total_volume = total
        self.lbl_total.setText(f"{self.total_volume:.1f}")

    def toggle_logging(self):
        if not self.logging:
            path, _ = QFileDialog.getSaveFileName(self, "Salva log", f"air_log_{datetime.now():%Y%m%d_%H%M%S}.csv", "CSV (*.csv)")
            if path:
                self.csv_file = open(path, 'w', newline='', encoding='utf-8')
                self.csv_writer = csv.writer(self.csv_file)
                self.csv_writer.writerow(["timestamp", "pressure_bar", "flow_raw", "flow_converted", "V_pressure", "V_flow", "total", "unit", "temperature_C"])
                self.logging = True
                self.btn_log.setText("⏹ Ferma Log")
        else:
            self.logging = False
            if self.csv_file:
                self.csv_file.close()
            self.btn_log.setText("▶ Avvia Log")

    def reset_total(self):
        self.total_volume = 0.0
        self.lbl_total.setText("0.0")

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
                    conv = row.get('flow_converted')
                    if conv is not None and conv != '':
                        flows_conv.append(float(conv))
                    else:
                        flows_conv.append(None)
                    vps.append(float(row.get('V_pressure', 0) or row.get('V_p', 0) or 0))
                    vfs.append(float(row.get('V_flow', 0) or row.get('V_f', 0) or 0))
                    totals.append(float(row.get('total', 0) or 0))

            n = len(times)
            if n == 0:
                QMessageBox.warning(self, "CSV vuoto", "Nessuna riga dati trovata.")
                return

            for i in range(n):
                if flows_conv[i] is None:
                    flows_conv[i] = convert_flow(flows_raw[i], presses[i], self.flow_unit, self.temperature_c, self.atm_pressure)

            self.time_data = deque(times, maxlen=self.buffer_size)
            self.press_data = deque(presses, maxlen=self.buffer_size)
            self.flow_raw_data = deque(flows_raw, maxlen=self.buffer_size)
            self.flow_data = deque(flows_conv, maxlen=self.buffer_size)
            self.vp_data = deque(vps, maxlen=self.buffer_size)
            self.vf_data = deque(vfs, maxlen=self.buffer_size)

            self._recalculate_from_history()

            self.table.setRowCount(0)
            start = max(0, n - 500)
            running = 0.0
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

            self.curve_p.setData(times, presses)
            self.curve_f.setData(times, list(self.flow_data))

            if presses:
                self.lbl_press.setText(f"{presses[-1]:.3f}")
                self.lbl_flow.setText(f"{list(self.flow_data)[-1]:.2f}")
                self.lbl_curr.setText(f"{vps[-1]:.2f} / {vfs[-1]:.2f} V")

            self.last_sample_time = times[-1] if times else None
            self.status.showMessage(f"Caricato {path} ({n} punti)", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

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

    def closeEvent(self, event):
        self.worker.disconnect()
        if self.csv_file:
            self.csv_file.close()
        event.accept()