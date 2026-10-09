"""
Pannello grafico + cursori di misura.
Asse X in data/ora reale. Grafico aggiornato solo se recording=True.
"""
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QFrame, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
import pyqtgraph as pg
import numpy as np


class PlotPanel(QWidget):
    measure_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.measure_active = False
        self.recording = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Controlli curve
        ctrl = QHBoxLayout()
        self.chk_press = QCheckBox("Mostra Pressione")
        self.chk_press.setChecked(True)
        self.chk_press.stateChanged.connect(self._update_curves_visibility)
        ctrl.addWidget(self.chk_press)

        self.chk_flow = QCheckBox("Mostra Portata")
        self.chk_flow.setChecked(True)
        self.chk_flow.stateChanged.connect(self._update_curves_visibility)
        ctrl.addWidget(self.chk_flow)

        # Auto-scala: QPushButton al posto del ButtonItem pyqtgraph (non stilizzabile)
        self.btn_auto = QPushButton("AutoScale")
        self.btn_auto.setFixedSize(132, 28)
        self.btn_auto.setToolTip("Auto-scala assi (fit dati)")
        self.btn_auto.clicked.connect(self._auto_range)
        ctrl.addWidget(self.btn_auto)

        ctrl.addStretch()

        self.lbl_rec = QLabel("")
        self.lbl_rec.setStyleSheet("color:#f38ba8; font-size:12px; font-weight:bold;")
        ctrl.addWidget(self.lbl_rec)
        layout.addLayout(ctrl)

        # Grafico con asse data/ora
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('#11111b')
        layout.addWidget(self.plot_widget, stretch=1)

        date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot = self.plot_widget.addPlot(axisItems={'bottom': date_axis})
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        # Nasconde il ButtonItem nativo "A" (non risponde a stylesheet Qt)
        try:
            self.plot.hideButtons()
        except Exception:
            pass
        self.plot.setLabel('left', 'Pressione', units='bar', color='#89b4fa')
        self.plot.setLabel('bottom', 'Data / Ora', color='#cdd6f4')
        self.plot.getAxis('left').setPen(pg.mkPen('#89b4fa'))
        self.plot.getAxis('left').setTextPen(pg.mkPen('#89b4fa'))
        self.plot.getAxis('bottom').setPen(pg.mkPen('#cdd6f4'))
        self.plot.getAxis('bottom').setTextPen(pg.mkPen('#cdd6f4'))

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

        # Cursori più sottili e leggibili
        self.cursor1 = pg.InfiniteLine(
            angle=90, movable=True,
            pen=pg.mkPen('#f38ba8', width=1.5, style=Qt.PenStyle.DashLine),
            label='C1',
            labelOpts={
                'position': 0.92, 'color': '#f38ba8',
                'fill': '#1e1e2e', 'movable': False
            }
        )
        self.cursor2 = pg.InfiniteLine(
            angle=90, movable=True,
            pen=pg.mkPen('#a6e3a1', width=1.5, style=Qt.PenStyle.DashLine),
            label='C2',
            labelOpts={
                'position': 0.92, 'color': '#a6e3a1',
                'fill': '#1e1e2e', 'movable': False
            }
        )
        # Regione semi-trasparente tra i cursori
        self.region = pg.LinearRegionItem(
            values=[0, 1],
            brush=pg.mkBrush(137, 180, 250, 30),
            pen=pg.mkPen(None),
            movable=False
        )
        self.region.setVisible(False)
        self.region.setZValue(-10)
        self.plot.addItem(self.region)

        self.cursor1.setVisible(False)
        self.cursor2.setVisible(False)
        self.plot.addItem(self.cursor1)
        self.plot.addItem(self.cursor2)
        self.cursor1.sigPositionChanged.connect(self._on_cursor_moved)
        self.cursor2.sigPositionChanged.connect(self._on_cursor_moved)

        # ---- Pannello misura in basso ----
        self.measure_panel = QFrame()
        self.measure_panel.setObjectName("measurePanel")
        self.measure_panel.setStyleSheet("""
            QFrame#measurePanel {
                background: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 8px;
            }
        """)
        mp = QHBoxLayout(self.measure_panel)
        mp.setContentsMargins(10, 8, 10, 8)
        mp.setSpacing(14)

        self.btn_measure = QPushButton("Cursori")
        self.btn_measure.setCheckable(True)
        self.btn_measure.setFixedWidth(90)
        self.btn_measure.setToolTip("Attiva/disattiva cursori sull'intervallo")
        self.btn_measure.clicked.connect(self._on_btn_measure)
        mp.addWidget(self.btn_measure)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.lbl_delta = QLabel("Cursori OFF")
        self.lbl_delta.setStyleSheet("color:#a6adc8; font-size:11px;")
        self.lbl_range = QLabel("")
        self.lbl_range.setStyleSheet("color:#6c7086; font-size:10px;")
        info_col.addWidget(self.lbl_delta)
        info_col.addWidget(self.lbl_range)
        mp.addLayout(info_col)

        mp.addStretch()

        self.press_box = self._make_stat_box("PRESSIONE", "#89b4fa", "bar")
        mp.addWidget(self.press_box['frame'])

        self.flow_box = self._make_stat_box("PORTATA", "#a6e3a1", "Nl/min")
        mp.addWidget(self.flow_box['frame'])

        layout.addWidget(self.measure_panel)

        self._time = None
        self._press = None
        self._flow = None

    def _make_stat_box(self, title, color, unit):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #11111b;
                border: 1px solid #45475a;
                border-radius: 6px;
            }
        """)
        grid = QGridLayout(frame)
        grid.setContentsMargins(8, 4, 8, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(1)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color:{color}; font-size:10px; font-weight:bold; border:none;"
        )
        grid.addWidget(title_lbl, 0, 0, 1, 2)

        labels = {}
        for i, (name, key) in enumerate(
            [("Max", "max"), ("Min", "min"), ("P-P", "pp"), ("Ave", "ave")], start=1
        ):
            n_lbl = QLabel(f"{name}:")
            n_lbl.setStyleSheet("color:#9399b2; font-size:11px; border:none;")
            v_lbl = QLabel("---")
            v_lbl.setStyleSheet(
                f"color:{color}; font-size:12px; font-weight:bold; border:none;"
            )
            v_lbl.setMinimumWidth(80)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(n_lbl, i, 0)
            grid.addWidget(v_lbl, i, 1)
            labels[key] = v_lbl

        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet("color:#6c7086; font-size:10px; border:none;")
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid.addWidget(unit_lbl, 5, 0, 1, 2)
        return {"frame": frame, "labels": labels}

    # ------------------------------------------------------------------
    def _auto_range(self):
        """
        Auto-scala:
        - cursori ON  → fit Y (e X) solo sull'intervallo C1–C2
        - cursori OFF → fit su tutto il grafico
        """
        if self._time is None or len(self._time) < 2:
            self.plot.enableAutoRange(axis=pg.ViewBox.XYAxes)
            try:
                self.vb_right.enableAutoRange(axis=pg.ViewBox.YAxis)
            except Exception:
                pass
            return

        t = np.array(self._time)
        p = np.array(self._press)
        f = np.array(self._flow)

        if self.measure_active:
            c1 = self.cursor1.value()
            c2 = self.cursor2.value()
            t_lo, t_hi = min(c1, c2), max(c1, c2)
            mask = (t >= t_lo) & (t <= t_hi)
            if not np.any(mask):
                return
            t_sel, p_sel, f_sel = t[mask], p[mask], f[mask]
            f_valid = f_sel[f_sel >= 0]
            if len(f_valid) == 0:
                f_valid = f_sel

            # Asse X: intervallo cursori (con piccolo margine)
            margin = max((t_hi - t_lo) * 0.02, 0.5)
            self.plot.setXRange(t_lo - margin, t_hi + margin, padding=0)

            # Pressione (asse sinistro)
            p_min, p_max = float(np.min(p_sel)), float(np.max(p_sel))
            p_pad = max((p_max - p_min) * 0.08, 0.01)
            self.plot.setYRange(p_min - p_pad, p_max + p_pad, padding=0)

            # Portata (asse destro)
            f_min, f_max = float(np.min(f_valid)), float(np.max(f_valid))
            f_pad = max((f_max - f_min) * 0.08, 0.5)
            self.vb_right.setYRange(f_min - f_pad, f_max + f_pad, padding=0)
        else:
            # Tutto il grafico
            self.plot.enableAutoRange(axis=pg.ViewBox.XYAxes)
            try:
                self.vb_right.enableAutoRange(axis=pg.ViewBox.YAxis)
            except Exception:
                pass

    def set_data_refs(self, time_data, press_data, flow_data):
        self._time = time_data
        self._press = press_data
        self._flow = flow_data

    def set_recording(self, active: bool):
        self.recording = active
        if active:
            self.lbl_rec.setText("● REGISTRAZIONE")
            self.lbl_rec.setStyleSheet(
                "color:#f38ba8; font-size:12px; font-weight:bold;"
            )
        else:
            if self._time and len(self._time) > 0:
                self.lbl_rec.setText("■ FERMO – dati in memoria")
                self.lbl_rec.setStyleSheet(
                    "color:#f9e2af; font-size:12px; font-weight:bold;"
                )
            else:
                self.lbl_rec.setText("")

    def clear_plot(self):
        self.curve_p.setData([], [])
        self.curve_f.setData([], [])
        if self.measure_active:
            self.toggle_measure(False)
            self.btn_measure.setChecked(False)

    def _update_views(self):
        self.vb_right.setGeometry(self.plot.vb.sceneBoundingRect())
        self.vb_right.linkedViewChanged(self.plot.vb, self.vb_right.XAxis)

    def _update_curves_visibility(self):
        self.curve_p.setVisible(self.chk_press.isChecked())
        self.curve_f.setVisible(self.chk_flow.isChecked())

    def update_curves(self):
        """Aggiorna solo se stiamo registrando (o ci sono dati da mostrare dopo stop/load)."""
        if self._time is None or len(self._time) < 2:
            return
        # Durante recording aggiorna sempre; a fermo i dati restano (già disegnati)
        if not self.recording and not getattr(self, '_force_redraw', False):
            # aggiorna solo le stats cursori se attivi
            if self.measure_active:
                self._update_measure()
            return
        t = np.array(self._time)
        self.curve_p.setData(t, np.array(self._press))
        self.curve_f.setData(t, np.array(self._flow))
        if self.measure_active:
            self._update_measure()

    def force_redraw(self):
        """Ridisegna i dati presenti (dopo load CSV o stop)."""
        if self._time is None or len(self._time) < 1:
            self.clear_plot()
            return
        t = np.array(self._time)
        self.curve_p.setData(t, np.array(self._press))
        self.curve_f.setData(t, np.array(self._flow))
        if self.measure_active:
            self._update_measure()

    def set_curves_data(self, times, presses, flows):
        self.curve_p.setData(times, presses)
        self.curve_f.setData(times, flows)

    def get_cursor_range(self):
        """Restituisce (t_lo, t_hi) unix se cursori attivi, altrimenti None."""
        if not self.measure_active:
            return None
        c1 = self.cursor1.value()
        c2 = self.cursor2.value()
        return min(c1, c2), max(c1, c2)

    def _on_btn_measure(self):
        active = self.btn_measure.isChecked()
        self.toggle_measure(active)
        self.measure_toggled.emit(active)

    def toggle_measure(self, active: bool):
        self.measure_active = active
        self.btn_measure.setChecked(active)
        self.cursor1.setVisible(active)
        self.cursor2.setVisible(active)
        self.region.setVisible(active)
        if active and self._time is not None and len(self._time) >= 2:
            t = np.array(self._time)
            mid = (t[0] + t[-1]) / 2
            span = max((t[-1] - t[0]) * 0.15, 1.0)
            self.cursor1.setValue(mid - span)
            self.cursor2.setValue(mid + span)
            self._sync_region()
            self._update_measure()
        else:
            self.lbl_delta.setText("Cursori OFF")
            self.lbl_range.setText("")
            self._clear_stats(self.press_box)
            self._clear_stats(self.flow_box)

    def _sync_region(self):
        c1 = self.cursor1.value()
        c2 = self.cursor2.value()
        self.region.setRegion((min(c1, c2), max(c1, c2)))

    def _clear_stats(self, box):
        for lbl in box["labels"].values():
            lbl.setText("---")

    def _on_cursor_moved(self):
        if self.measure_active:
            self._sync_region()
            self._update_measure()

    def _fill_stats(self, box, data, fmt):
        mn = float(np.min(data))
        mx = float(np.max(data))
        ave = float(np.mean(data))
        pp = mx - mn
        box["labels"]["max"].setText(fmt.format(mx))
        box["labels"]["min"].setText(fmt.format(mn))
        box["labels"]["pp"].setText(fmt.format(pp))
        box["labels"]["ave"].setText(fmt.format(ave))

    @staticmethod
    def _fmt_ts(ts):
        try:
            return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            return str(ts)

    def _update_measure(self):
        if self._time is None or len(self._time) < 2:
            return
        t = np.array(self._time)
        p = np.array(self._press)
        f = np.array(self._flow)

        c1 = self.cursor1.value()
        c2 = self.cursor2.value()
        t_lo, t_hi = min(c1, c2), max(c1, c2)

        mask = (t >= t_lo) & (t <= t_hi)
        if not np.any(mask):
            self.lbl_delta.setText(f"Δt={abs(c2 - c1):.1f}s — nessun campione")
            self.lbl_range.setText("")
            self._clear_stats(self.press_box)
            self._clear_stats(self.flow_box)
            return

        p_sel = p[mask]
        f_sel = f[mask]
        f_valid = f_sel[f_sel >= 0]
        if len(f_valid) == 0:
            f_valid = f_sel

        n = int(np.sum(mask))
        self.lbl_delta.setText(f"Δt={abs(c2 - c1):.1f}s  ({n} campioni)")
        self.lbl_range.setText(
            f"{self._fmt_ts(t_lo)}  →  {self._fmt_ts(t_hi)}"
        )
        self._fill_stats(self.press_box, p_sel, "{:.3f}")
        self._fill_stats(self.flow_box, f_valid, "{:.2f}")
