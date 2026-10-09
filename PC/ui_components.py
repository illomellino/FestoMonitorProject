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
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox
)
from PyQt6.QtCore import QTimer, Qt
import pyqtgraph as pg
import numpy as np

from config import DARK_STYLE
from ReadSerial import SerialWorker
from export_pdf import generate_pdf_report


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Consumption Meter – Festo Monitor Professional")
        self.resize(1450, 920)

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
            QComboBox, QSpinBox {
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
        self.flow_data = deque(maxlen=self.buffer_size)   # già Nl/min DIN 1343 dallo strumento
        self.vp_data = deque(maxlen=self.buffer_size)
        self.vf_data = deque(maxlen=self.buffer_size)

        self.logging = False
        self.csv_file = None
        self.csv_writer = None
        self.start_time = None
        self.total_volume = 0.0          # Nl
        self.last_sample_time = None
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
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Barra connessione / sessione ---
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
        self.btn_pdf.clicked.connect(
            lambda: generate_pdf_report(self, self.press_data, self.time_data, self.flow_data)
        )
        conn_layout.addWidget(self.btn_pdf)

        conn_layout.addStretch()
        layout.addWidget(conn_box)

        # --- Card valori in tempo reale ---
        values_layout = QHBoxLayout()
        values_layout.setSpacing(12)

        def create_card(title, default_val, unit_val, val_color="#a6e3a1"):
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                stop:0 #1e1e2e, stop:1 #181825);
                    border: 1px solid #45475a;
                    border-top: 2px solid #585b70;
                    border-radius: 10px;
                    padding: 12px;
                }
            """)
            l = QVBoxLayout(frame)
            l.setContentsMargins(8, 8, 8, 8)

            title_lbl = QLabel(title, alignment=Qt.AlignmentFlag.AlignCenter)
            title_lbl.setStyleSheet(
                "color: #bac2de; font-size: 11px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            l.addWidget(title_lbl)

            val_lbl = QLabel(default_val)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet(
                f"font-size: 28px; font-weight: bold; color: {val_color}; "
                "background: transparent; border: none;"
            )
            l.addWidget(val_lbl)

            u_lbl = QLabel(unit_val, alignment=Qt.AlignmentFlag.AlignCenter)
            u_lbl.setStyleSheet(
                "color: #9399b2; font-size: 12px; background: transparent; border: none;"
            )
            l.addWidget(u_lbl)
            return frame, val_lbl, u_lbl

        self.p_card, self.lbl_press, _ = create_card("PRESSIONE", "---", "bar", "#89b4fa")
        self.f_card, self.lbl_flow, _ = create_card("PORTATA", "---", "Nl/min", "#a6e3a1")
        self.t_card, self.lbl_total, _ = create_card("CONSUMO TOTALE", "0.0", "Nl", "#f9e2af")
        self.c_card, self.lbl_curr, _ = create_card("TENSIONI ADS1115", "--- / --- V", "Canali P / F", "#fab387")

        values_layout.addWidget(self.p_card)
        values_layout.addWidget(self.f_card)
        values_layout.addWidget(self.t_card)
        values_layout.addWidget(self.c_card)
        layout.addLayout(values_layout)

        # --- Tabs ---
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        # Tab grafico
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
        self.measure_panel.setStyleSheet(
            "background:#1e1e2e; border: 1px solid #45475a; border-radius:8px; padding:8px;"
        )
        self.measure_panel.setVisible(False)
        mp = QHBoxLayout(self.measure_panel)
        self.lbl_measure = QLabel("Cursori disattivati")
        mp.addWidget(self.lbl_measure)
        graph_layout.addWidget(self.measure_panel)

        self.tabs.addTab(graph_tab, "Grafico in Tempo Reale")

        # Tab tabella
        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Tempo (s)", "Pressione (bar)", "Portata (Nl/min)",
            "V_p (V)", "V_f (V)", "Totale (Nl)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        raw_layout.addWidget(self.table)
        self.tabs.addTab(raw_tab, "Tabella Valori")

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto – Seleziona la porta seriale per iniziare")

    # ------------------------------------------------------------------
    # Grafici
    # ------------------------------------------------------------------
    def _setup_plots(self):
        self.plot = self.plot_widget.addPlot()
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel('left', 'Pressione', units='bar', color='#89b4fa')
        self.plot.setLabel('bottom', 'Tempo', units='s', color='#cdd6f4')
        self.plot.getAxis('left').setPen(pg.mkPen('#89b4fa'))
        self.plot.getAxis('left').setTextPen(pg.mkPen('#89b4fa'))

        self.plot.showAxis('right')
        self.plot.setLabel('right', 'Portata', units='Nl/min', color='#a6e3a1')
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

        self.cursor1 = pg.InfiniteLine(
            angle=90, movable=True,
            pen=pg.mkPen('#f38ba8', width=2, style=Qt.PenStyle.DashLine)
        )
        self.cursor2 = pg.InfiniteLine(
            angle=90, movable=True,
            pen=pg.mkPen('#fab387', width=2, style=Qt.PenStyle.DashLine)
        )
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
        self.vp_data = deque(self.vp_data, maxlen=self.buffer_size)
        self.vf_data = deque(self.vf_data, maxlen=self.buffer_size)
        self.status.showMessage(f"Buffer aggiornato a {minutes} min", 3000)

    # ------------------------------------------------------------------
    # Connessione seriale
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Dati in arrivo (già Nl/min DIN 1343)
    # ------------------------------------------------------------------
    def on_data(self, t, pressure, flow, v_p, v_f):
        """flow è già in Nl/min DIN 1343 dallo strumento."""
        now = time.time() - self.start_time if self.start_time else t

        if self.last_sample_time is not None and flow >= 0:
            dt_min = (now - self.last_sample_time) / 60.0
            self.total_volume += flow * dt_min
        self.last_sample_time = now

        self.time_data.append(now)
        self.press_data.append(pressure)
        self.flow_data.append(flow)
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
        vals = [
            f"{now:.2f}",
            f"{pressure:.4f}",
            f"{flow:.2f}",
            f"{v_p:.3f}",
            f"{v_f:.3f}",
            f"{self.total_volume:.2f}",
        ]
        for col, v in enumerate(vals):
            self.table.setItem(row, col, QTableWidgetItem(v))
        self.table.scrollToBottom()

        if self.logging and self.csv_writer:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.csv_writer.writerow([
                ts,
                f"{pressure:.4f}",
                f"{flow:.3f}",
                f"{v_p:.3f}",
                f"{v_f:.3f}",
                f"{self.total_volume:.3f}",
            ])

    def update_plots(self):
        if len(self.time_data) > 1:
            t = np.array(self.time_data)
            self.curve_p.setData(t, np.array(self.press_data))
            self.curve_f.setData(t, np.array(self.flow_data))
            if self.measure_active:
                self._update_measure_labels()

    # ------------------------------------------------------------------
    # Cursori di misura
    # ------------------------------------------------------------------
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
        text = (
            f"<b>C1</b>: {t[idx1]:.2f}s (P={p[idx1]:.3f} bar, F={f[idx1]:.2f} Nl/min) | "
            f"<b>C2</b>: {t[idx2]:.2f}s (P={p[idx2]:.3f} bar, F={f[idx2]:.2f} Nl/min) | "
            f"<b>Δt</b>={abs(t[idx2] - t[idx1]):.2f}s  "
            f"<b>ΔP</b>={p[idx2] - p[idx1]:+.3f} bar"
        )
        self.lbl_measure.setText(text)

    # ------------------------------------------------------------------
    # Log CSV
    # ------------------------------------------------------------------
    def toggle_logging(self):
        if not self.logging:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva log",
                f"air_log_{datetime.now():%Y%m%d_%H%M%S}.csv",
                "CSV (*.csv)"
            )
            if path:
                self.csv_file = open(path, 'w', newline='', encoding='utf-8')
                self.csv_writer = csv.writer(self.csv_file)
                self.csv_writer.writerow([
                    "timestamp", "pressure_bar", "flow_Nl_min",
                    "V_pressure", "V_flow", "total_Nl"
                ])
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

    # ------------------------------------------------------------------
    # Carica CSV storico
    # ------------------------------------------------------------------
    def load_history(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carica CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            times, presses, flows, vps, vfs = [], [], [], [], []
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    times.append(i * 0.1)
                    presses.append(float(row.get('pressure_bar', 0) or 0))
                    # compatibilità con vecchi CSV (flow_raw / flow_converted / flow_Nl_min)
                    flow_val = float(
                        row.get('flow_Nl_min')
                        or row.get('flow_raw')
                        or row.get('flow_converted')
                        or 0
                    )
                    flows.append(flow_val)
                    vps.append(float(row.get('V_pressure', 0) or row.get('V_p', 0) or 0))
                    vfs.append(float(row.get('V_flow', 0) or row.get('V_f', 0) or 0))

            n = len(times)
            if n == 0:
                QMessageBox.warning(self, "CSV vuoto", "Nessuna riga dati trovata.")
                return

            self.time_data = deque(times, maxlen=self.buffer_size)
            self.press_data = deque(presses, maxlen=self.buffer_size)
            self.flow_data = deque(flows, maxlen=self.buffer_size)
            self.vp_data = deque(vps, maxlen=self.buffer_size)
            self.vf_data = deque(vfs, maxlen=self.buffer_size)

            # ricalcola totale volume
            self.total_volume = 0.0
            for i in range(1, n):
                if flows[i] >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if dt_min > 0:
                        self.total_volume += flows[i] * dt_min
            self.lbl_total.setText(f"{self.total_volume:.1f}")

            self.table.setRowCount(0)
            start = max(0, n - 500)
            running = 0.0
            for i in range(start):
                if i > 0 and flows[i] >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if dt_min > 0:
                        running += flows[i] * dt_min

            for i in range(start, n):
                flow = flows[i]
                if i > 0 and flow >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if dt_min > 0:
                        running += flow * dt_min
                row = self.table.rowCount()
                self.table.insertRow(row)
                vals = [
                    f"{times[i]:.2f}",
                    f"{presses[i]:.4f}",
                    f"{flow:.2f}",
                    f"{vps[i]:.3f}",
                    f"{vfs[i]:.3f}",
                    f"{running:.2f}",
                ]
                for col, v in enumerate(vals):
                    self.table.setItem(row, col, QTableWidgetItem(v))
            self.table.scrollToBottom()

            self.curve_p.setData(times, presses)
            self.curve_f.setData(times, flows)

            if presses:
                self.lbl_press.setText(f"{presses[-1]:.3f}")
                self.lbl_flow.setText(f"{flows[-1]:.2f}")
                self.lbl_curr.setText(f"{vps[-1]:.2f} / {vfs[-1]:.2f} V")

            self.last_sample_time = times[-1] if times else None
            self.status.showMessage(f"Caricato {path} ({n} punti)", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

    def closeEvent(self, event):
        self.worker.disconnect()
        if self.csv_file:
            self.csv_file.close()
        event.accept()
