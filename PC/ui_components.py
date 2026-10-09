import csv
import time
import threading
from datetime import datetime
from collections import deque

import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFileDialog,
    QMessageBox, QStatusBar, QFrame, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import QTimer, Qt

from config import DARK_STYLE
from ReadSerial import SerialWorker
from export_pdf import generate_pdf_report
from plot_panel import PlotPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AirFlowTrace | Pneumatic Data Logger")
        self.resize(1450, 920)
        self.setStyleSheet(DARK_STYLE)

        self.worker = SerialWorker()
        self.worker.data_received.connect(self.on_data)
        self.worker.error.connect(self.on_error)
        self.worker.status_msg.connect(self._on_status_msg)

        self.sample_rate_hz = 10
        self.buffer_minutes = 60
        self.buffer_size = self.buffer_minutes * 60 * self.sample_rate_hz

        self.time_data = deque(maxlen=self.buffer_size)   # unix timestamps
        self.press_data = deque(maxlen=self.buffer_size)
        self.flow_data = deque(maxlen=self.buffer_size)
        self.vp_data = deque(maxlen=self.buffer_size)
        self.vf_data = deque(maxlen=self.buffer_size)

        self.logging = False
        self.csv_file = None
        self.csv_writer = None
        self.total_volume = 0.0
        self.last_sample_time = None
        self.debug_volt = False
        self.session_start = None   # datetime inizio log

        self._build_ui()

        self.plot_panel.set_data_refs(self.time_data, self.press_data, self.flow_data)

        self.timer = QTimer()
        self.timer.timeout.connect(self.plot_panel.update_curves)
        self.timer.start(100)

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # ===== RIGA 1: Connessione seriale =====
        ser_box = QGroupBox("Connessione seriale")
        ser_layout = QHBoxLayout(ser_box)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(280)
        self.refresh_ports()
        ser_layout.addWidget(QLabel("Porta:"))
        ser_layout.addWidget(self.port_combo)

        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self.refresh_ports)
        ser_layout.addWidget(btn_refresh)

        self.btn_connect = QPushButton("Connetti")
        self.btn_connect.clicked.connect(self.toggle_connection)
        ser_layout.addWidget(self.btn_connect)

        ser_layout.addStretch()

        self.btn_debug = QPushButton("⚙ Diagnostica")
        self.btn_debug.setCheckable(True)
        self.btn_debug.setToolTip("Mostra tensioni ADS1115 nelle card")
        self.btn_debug.clicked.connect(self._toggle_debug)
        ser_layout.addWidget(self.btn_debug)

        layout.addWidget(ser_box)

        # ===== RIGA 2: Comandi registrazione / plot =====
        cmd_box = QGroupBox("Registrazione e analisi")
        cmd_layout = QHBoxLayout(cmd_box)

        self.btn_log = QPushButton("▶ Avvia Log")
        self.btn_log.setEnabled(False)
        self.btn_log.clicked.connect(self.toggle_logging)
        cmd_layout.addWidget(self.btn_log)

        btn_load = QPushButton("📂 Carica storico")
        btn_load.clicked.connect(self.load_history)
        cmd_layout.addWidget(btn_load)

        btn_reset = QPushButton("↺ Reset totale")
        btn_reset.clicked.connect(self.reset_total)
        cmd_layout.addWidget(btn_reset)

        self.btn_pdf = QPushButton("📄 Report PDF")
        self.btn_pdf.clicked.connect(self._make_pdf)
        cmd_layout.addWidget(self.btn_pdf)

        cmd_layout.addStretch()
        layout.addWidget(cmd_box)

        # ===== Card valori =====
        values_layout = QHBoxLayout()
        values_layout.setSpacing(12)

        self.p_card, self.lbl_press, self.lbl_vp = self._create_card(
            "PRESSIONE", "--- bar", "#89b4fa"
        )
        self.f_card, self.lbl_flow, self.lbl_vf = self._create_card(
            "PORTATA", "--- Nl/min", "#a6e3a1"
        )
        self.t_card, self.lbl_total, _ = self._create_card(
            "CONSUMO TOTALE", "0.0 Nl", "#f9e2af", with_volt=False
        )

        for c in (self.p_card, self.f_card, self.t_card):
            values_layout.addWidget(c)
        layout.addLayout(values_layout)

        # ===== Tabs =====
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self.plot_panel = PlotPanel()
        self.tabs.addTab(self.plot_panel, "Grafico")

        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Data/Ora", "Pressione (bar)", "Portata (Nl/min)",
            "V_p (V)", "V_f (V)", "Totale (Nl)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setColumnHidden(3, True)
        self.table.setColumnHidden(4, True)
        raw_layout.addWidget(self.table)
        self.tabs.addTab(raw_tab, "Tabella")

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto – connetti la porta seriale")

    @staticmethod
    def _create_card(title, default_val, val_color, with_volt=True):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 #1e1e2e, stop:1 #181825);
                border: 1px solid #45475a;
                border-top: 2px solid #585b70;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        l = QVBoxLayout(frame)
        l.setContentsMargins(8, 6, 8, 6)
        l.setSpacing(2)

        title_lbl = QLabel(title, alignment=Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(
            "color:#bac2de; font-size:11px; font-weight:bold; "
            "background:transparent; border:none;"
        )
        l.addWidget(title_lbl)

        val_lbl = QLabel(default_val)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet(
            f"font-size:26px; font-weight:bold; color:{val_color}; "
            "background:transparent; border:none;"
        )
        l.addWidget(val_lbl)

        volt_lbl = None
        if with_volt:
            volt_lbl = QLabel("")
            volt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            volt_lbl.setStyleSheet(
                "color:#6c7086; font-size:11px; background:transparent; border:none;"
            )
            volt_lbl.setVisible(False)
            l.addWidget(volt_lbl)

        return frame, val_lbl, volt_lbl

    def _toggle_debug(self):
        self.debug_volt = self.btn_debug.isChecked()
        if self.lbl_vp:
            self.lbl_vp.setVisible(self.debug_volt)
        if self.lbl_vf:
            self.lbl_vf.setVisible(self.debug_volt)
        self.table.setColumnHidden(3, not self.debug_volt)
        self.table.setColumnHidden(4, not self.debug_volt)

    # ------------------------------------------------------------------
    def refresh_ports(self):
        self.port_combo.clear()
        for p in serial.tools.list_ports.comports():
            self.port_combo.addItem(f"{p.device} – {p.description}", p.device)

    def toggle_connection(self):
        if self.worker.running:
            if self.logging:
                self._stop_logging()
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
                self.status.showMessage(f"Connesso a {port}")
                threading.Thread(target=self.worker.read_loop, daemon=True).start()
            else:
                QMessageBox.critical(self, "Errore", "Impossibile aprire la porta seriale.")

    def _on_status_msg(self, msg):
        self.status.showMessage(msg, 4000)

    def on_error(self, msg):
        self.status.showMessage(f"⚠ {msg}", 8000)

    # ------------------------------------------------------------------
    # Dati: monitor sempre, grafico solo se logging
    # ------------------------------------------------------------------
    def on_data(self, t, pressure, flow, v_p, v_f):
        # Tensioni diagnostiche sempre aggiornate
        if self.lbl_vp:
            self.lbl_vp.setText(f"{v_p:.3f} V")
        if self.lbl_vf:
            self.lbl_vf.setText(f"{v_f:.3f} V")

        # Fault numerici dal firmware ESP32:
        #   -999 = cavo scollegato / segnale < 0.50 V
        #   -998 = overrange / segnale > 3.40 V
        fault_p = pressure < -900
        fault_f = flow < -900
        if fault_p or fault_f:
            if (pressure <= -999) or (flow <= -999):
                msg = "⚠ FAULT SENSORE: cavo scollegato o segnale < 0.50 V"
            else:
                msg = "⚠ OVERRANGE: segnale > 3.40 V"
            self.status.showMessage(msg, 5000)
            self.lbl_press.setText("FAULT" if fault_p else f"{pressure:.3f} bar")
            self.lbl_flow.setText("FAULT" if fault_f else f"{flow:.2f} Nl/min")
            # Non registrare / non aggiornare grafico con valori di fault
            return

        # Valori live sempre (anche senza log)
        self.lbl_press.setText(f"{pressure:.3f} bar")
        self.lbl_flow.setText(f"{flow:.2f} Nl/min")
        if not self.logging:
            return

        now_ts = time.time()

        if self.last_sample_time is not None and flow >= 0:
            dt_min = (now_ts - self.last_sample_time) / 60.0
            self.total_volume += flow * dt_min
        self.last_sample_time = now_ts

        self.time_data.append(now_ts)
        self.press_data.append(pressure)
        self.flow_data.append(flow)
        self.vp_data.append(v_p)
        self.vf_data.append(v_f)

        self.lbl_total.setText(f"{self.total_volume:.1f} Nl")

        if self.table.rowCount() > 500:
            self.table.removeRow(0)
        row = self.table.rowCount()
        self.table.insertRow(row)
        ts_str = datetime.fromtimestamp(now_ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        for col, v in enumerate([
            ts_str, f"{pressure:.4f}", f"{flow:.2f}",
            f"{v_p:.3f}", f"{v_f:.3f}", f"{self.total_volume:.2f}",
        ]):
            self.table.setItem(row, col, QTableWidgetItem(v))
        self.table.scrollToBottom()

        if self.csv_writer:
            self.csv_writer.writerow([
                ts_str, f"{pressure:.4f}", f"{flow:.3f}",
                f"{v_p:.3f}", f"{v_f:.3f}", f"{self.total_volume:.3f}",
            ])

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------
    def toggle_logging(self):
        if not self.logging:
            self._start_logging()
        else:
            self._stop_logging()

    def _start_logging(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva log",
            f"air_log_{datetime.now():%Y%m%d_%H%M%S}.csv",
            "CSV (*.csv)"
        )
        if not path:
            return

        # Chiude eventuale file precedente e azzera tutto
        if self.csv_file:
            try:
                self.csv_file.close()
            except Exception:
                pass
            self.csv_file = None
            self.csv_writer = None

        self._clear_session()

        self.csv_file = open(path, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            "timestamp", "pressure_bar", "flow_Nl_min",
            "V_pressure", "V_flow", "total_Nl"
        ])

        self.logging = True
        self.session_start = datetime.now()
        self.last_sample_time = None
        self.btn_log.setText("⏹ Ferma Log")
        self.plot_panel.set_recording(True)
        self.status.showMessage(f"Registrazione avviata → {path}")

    def _stop_logging(self):
        self.logging = False
        if self.csv_file:
            try:
                self.csv_file.close()
            except Exception:
                pass
            self.csv_file = None
            self.csv_writer = None
        self.btn_log.setText("▶ Avvia Log")
        self.plot_panel.set_recording(False)
        self.plot_panel.force_redraw()
        self.status.showMessage("Registrazione fermata – dati in memoria")

    def _clear_session(self):
        self.time_data.clear()
        self.press_data.clear()
        self.flow_data.clear()
        self.vp_data.clear()
        self.vf_data.clear()
        self.total_volume = 0.0
        self.last_sample_time = None
        self.session_start = None
        self.lbl_total.setText("0.0 Nl")
        self.table.setRowCount(0)
        self.plot_panel.clear_plot()

    def reset_total(self):
        self.total_volume = 0.0
        self.lbl_total.setText("0.0 Nl")

    # ------------------------------------------------------------------
    def _make_pdf(self):
        if len(self.time_data) < 5:
            QMessageBox.warning(self, "Dati insufficienti", "Servono più campioni.")
            return
        cursor_range = self.plot_panel.get_cursor_range()
        generate_pdf_report(
            self,
            self.press_data,
            self.time_data,
            self.flow_data,
            cursor_range=cursor_range,
        )

    # ------------------------------------------------------------------
    def load_history(self):
        if self.logging:
            QMessageBox.warning(
                self, "Registrazione attiva",
                "Ferma il log prima di caricare uno storico."
            )
            return
        path, _ = QFileDialog.getOpenFileName(self, "Carica CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            times, presses, flows, vps, vfs = [], [], [], [], []
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    ts_raw = row.get('timestamp', '')
                    try:
                        # prova parsing data/ora
                        for fmt in (
                            "%Y-%m-%d %H:%M:%S.%f",
                            "%Y-%m-%d %H:%M:%S",
                            "%d/%m/%Y %H:%M:%S",
                        ):
                            try:
                                ts = datetime.strptime(ts_raw.strip(), fmt).timestamp()
                                break
                            except ValueError:
                                ts = None
                        if ts is None:
                            ts = i * 0.1 + time.time() - 1000  # fallback
                    except Exception:
                        ts = i * 0.1 + time.time() - 1000

                    times.append(ts)
                    presses.append(float(row.get('pressure_bar', 0) or 0))
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

            self._clear_session()
            self.time_data = deque(times, maxlen=self.buffer_size)
            self.press_data = deque(presses, maxlen=self.buffer_size)
            self.flow_data = deque(flows, maxlen=self.buffer_size)
            self.vp_data = deque(vps, maxlen=self.buffer_size)
            self.vf_data = deque(vfs, maxlen=self.buffer_size)
            self.plot_panel.set_data_refs(
                self.time_data, self.press_data, self.flow_data
            )

            self.total_volume = 0.0
            for i in range(1, n):
                if flows[i] >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if 0 < dt_min < 10:
                        self.total_volume += flows[i] * dt_min
            self.lbl_total.setText(f"{self.total_volume:.1f} Nl")

            self.table.setRowCount(0)
            start = max(0, n - 500)
            running = 0.0
            for i in range(start):
                if i > 0 and flows[i] >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if 0 < dt_min < 10:
                        running += flows[i] * dt_min

            for i in range(start, n):
                flow = flows[i]
                if i > 0 and flow >= 0:
                    dt_min = (times[i] - times[i - 1]) / 60.0
                    if 0 < dt_min < 10:
                        running += flow * dt_min
                row = self.table.rowCount()
                self.table.insertRow(row)
                try:
                    ts_str = datetime.fromtimestamp(times[i]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except Exception:
                    ts_str = f"{times[i]:.1f}"
                for col, v in enumerate([
                    ts_str, f"{presses[i]:.4f}", f"{flow:.2f}",
                    f"{vps[i]:.3f}", f"{vfs[i]:.3f}", f"{running:.2f}",
                ]):
                    self.table.setItem(row, col, QTableWidgetItem(v))
            self.table.scrollToBottom()

            self.plot_panel.set_recording(False)
            self.plot_panel.force_redraw()

            if presses:
                self.lbl_press.setText(f"{presses[-1]:.3f} bar")
                self.lbl_flow.setText(f"{flows[-1]:.2f} Nl/min")
                if self.lbl_vp:
                    self.lbl_vp.setText(f"{vps[-1]:.3f} V")
                if self.lbl_vf:
                    self.lbl_vf.setText(f"{vfs[-1]:.3f} V")

            self.status.showMessage(f"Caricato {path} ({n} punti)", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

    def closeEvent(self, event):
        if self.logging:
            self._stop_logging()
        self.worker.disconnect()
        event.accept()
