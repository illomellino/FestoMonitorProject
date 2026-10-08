# AIR CONSUMPTION METER — UI/PDF RESTYLE PATCH
# Incolla questi blocchi nel tuo script esistente.
# Non cambia protocollo seriale, acquisizione, conversioni o CSV.

# ============================================================
# 1) IMPORT AGGIUNTIVI
# ============================================================
# Aggiungi:
import os
import tempfile
import pyqtgraph.exporters
from reportlab.platypus import Image, KeepTogether


# ============================================================
# 2) SOSTITUISCI DARK_STYLE CON QUESTO
# ============================================================
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #0f172a;
    color: #e5e7eb;
    font-family: 'Segoe UI', Arial;
    font-size: 12px;
}
QGroupBox {
    background-color: #111c2f;
    border: 1px solid #293548;
    border-radius: 10px;
    margin-top: 13px;
    padding-top: 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 7px;
    color: #cbd5e1;
}
QPushButton {
    background-color: #2563eb;
    color: white;
    border: 1px solid #3b82f6;
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #3b82f6;
}
QPushButton:pressed {
    background-color: #1d4ed8;
}
QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}
QPushButton#measureBtn {
    background-color: #172554;
    color: #93c5fd;
    border: 1px solid #2563eb;
}
QPushButton#measureBtn:hover {
    background-color: #1e3a8a;
}
QPushButton#measureBtn:checked {
    background-color: #f59e0b;
    color: #111827;
    border-color: #fbbf24;
}
QPushButton#helpBtn {
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
    border-radius: 14px;
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #64748b;
    font-size: 15px;
    font-weight: 800;
}
QPushButton#helpBtn:hover {
    background-color: #475569;
    border-color: #94a3b8;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #162033;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 5px 8px;
    min-height: 24px;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #64748b;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #38bdf8;
}
QLabel#valueLabel {
    font-size: 29px;
    font-weight: 700;
    color: #f8fafc;
}
QLabel#unitLabel {
    font-size: 12px;
    color: #94a3b8;
}
QStatusBar {
    background-color: #0b1220;
    color: #94a3b8;
    border-top: 1px solid #1e293b;
}
QTabWidget::pane {
    border: 1px solid #293548;
    border-radius: 8px;
    background: #111827;
    top: -1px;
}
QTabBar::tab {
    background: #162033;
    color: #94a3b8;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}
QTabBar::tab:hover {
    color: #e2e8f0;
    background: #1e293b;
}
QTabBar::tab:selected {
    background: #1d4ed8;
    color: white;
}
QTableWidget {
    background-color: #0f172a;
    alternate-background-color: #111c2f;
    gridline-color: #263449;
    color: #e5e7eb;
    border: none;
    selection-background-color: #1d4ed8;
}
QHeaderView::section {
    background-color: #162033;
    color: #cbd5e1;
    padding: 7px;
    border: none;
    border-right: 1px solid #293548;
    font-weight: 600;
}
QCheckBox {
    spacing: 7px;
    color: #cbd5e1;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
}
"""


# ============================================================
# 3) PICCOLE MODIFICHE IN _build_ui()
# ============================================================
# Subito dopo:
#     btn_help = QPushButton("?")
# aggiungi:
#
#     btn_help.setObjectName("helpBtn")
#
# Sostituisci gli stylesheet dei quattro riquadri valori con:
#
# p_frame.setStyleSheet("background:#111c2f; border:1px solid #293548; border-radius:10px; padding:10px;")
# f_frame.setStyleSheet("background:#111c2f; border:1px solid #293548; border-radius:10px; padding:10px;")
# t_frame.setStyleSheet("background:#111c2f; border:1px solid #293548; border-radius:10px; padding:10px;")
# c_frame.setStyleSheet("background:#111c2f; border:1px solid #293548; border-radius:10px; padding:10px;")
#
# E cambia il colore del totalizzatore:
#
# self.lbl_total.setStyleSheet("font-size:26px; font-weight:700; color:#fbbf24;")
#
# E le tensioni:
#
# self.lbl_curr.setStyleSheet("font-size:16px; color:#cbd5e1;")
#
# Pannello misure:
#
# self.measure_panel.setStyleSheet(
#     "background:#111c2f; border:1px solid #293548; border-radius:8px; padding:8px;"
# )


# ============================================================
# 4) SOSTITUISCI COMPLETAMENTE _setup_plots()
# ============================================================
def _setup_plots(self):
    self.plot = self.plot_widget.addPlot(title="Air Flow Analyser")
    self.plot_widget.setBackground('#0b1220')

    self.plot.showGrid(x=True, y=True, alpha=0.14)
    self.plot.setLabel('left', 'Pressione', units='bar', color='#60a5fa')
    self.plot.setLabel('bottom', 'Tempo', units='s', color='#94a3b8')
    self.plot.showAxis('right')
    self.plot.setLabel('right', 'Portata', color='#34d399')

    for axis_name in ('left', 'bottom'):
        ax = self.plot.getAxis(axis_name)
        ax.setPen(pg.mkPen('#475569'))
        ax.setTextPen(pg.mkPen('#94a3b8'))

    self.plot.getAxis('right').setPen(pg.mkPen('#475569'))
    self.plot.getAxis('right').setTextPen(pg.mkPen('#94a3b8'))

    self.plot.setMouseEnabled(x=True, y=True)
    self.plot.vb.setBackgroundColor('#0b1220')

    self.vb_right = pg.ViewBox()
    self.plot.scene().addItem(self.vb_right)
    self.plot.getAxis('right').linkToView(self.vb_right)
    self.vb_right.setXLink(self.plot)
    self.plot.vb.sigResized.connect(self._update_views)

    self.curve_p = self.plot.plot(
        pen=pg.mkPen('#60a5fa', width=2.2),
        name='Pressione'
    )
    self.curve_f = pg.PlotDataItem(
        pen=pg.mkPen('#34d399', width=2.2),
        name='Portata'
    )
    self.vb_right.addItem(self.curve_f)

    # Cursori
    self.cursor1 = pg.InfiniteLine(
        angle=90,
        movable=True,
        pen=pg.mkPen('#f472b6', width=1.8, style=Qt.PenStyle.DashLine),
        hoverPen=pg.mkPen('#f9a8d4', width=2.5)
    )
    self.cursor2 = pg.InfiniteLine(
        angle=90,
        movable=True,
        pen=pg.mkPen('#f59e0b', width=1.8, style=Qt.PenStyle.DashLine),
        hoverPen=pg.mkPen('#fbbf24', width=2.5)
    )

    self.plot.addItem(self.cursor1, ignoreBounds=True)
    self.plot.addItem(self.cursor2, ignoreBounds=True)

    # Etichette "floating" dei cursori.
    # Vengono posizionate in alto nel grafico e mostrano t / P / F.
    self.cursor1_tag = pg.TextItem(
        html="",
        anchor=(0, 1),
        fill=pg.mkBrush('#1f2937'),
        border=pg.mkPen('#f472b6', width=1)
    )
    self.cursor2_tag = pg.TextItem(
        html="",
        anchor=(1, 1),
        fill=pg.mkBrush('#1f2937'),
        border=pg.mkPen('#f59e0b', width=1)
    )
    self.plot.addItem(self.cursor1_tag, ignoreBounds=True)
    self.plot.addItem(self.cursor2_tag, ignoreBounds=True)

    self.cursor1.setVisible(False)
    self.cursor2.setVisible(False)
    self.cursor1_tag.setVisible(False)
    self.cursor2_tag.setVisible(False)

    self.cursor1.sigPositionChanged.connect(self._update_measure_labels)
    self.cursor2.sigPositionChanged.connect(self._update_measure_labels)
    self.plot.vb.sigRangeChanged.connect(lambda *args: self._update_cursor_tag_positions())


# ============================================================
# 5) AGGIUNGI QUESTO NUOVO METODO
# ============================================================
def _update_cursor_tag_positions(self):
    if not self.measure_active:
        return
    if len(self.time_data) < 2:
        return

    y_range = self.plot.vb.viewRange()[1]
    y_top = y_range[1]
    y_span = max(y_range[1] - y_range[0], 1e-6)
    y = y_top - y_span * 0.025

    self.cursor1_tag.setPos(self.cursor1.value(), y)
    self.cursor2_tag.setPos(self.cursor2.value(), y)


# ============================================================
# 6) SOSTITUISCI toggle_measure()
# ============================================================
def toggle_measure(self):
    self.measure_active = self.btn_measure.isChecked()

    for item in (
        self.cursor1, self.cursor2,
        self.cursor1_tag, self.cursor2_tag
    ):
        item.setVisible(self.measure_active)

    self.measure_panel.setVisible(self.measure_active)

    if self.measure_active and len(self.time_data) > 10:
        t = np.array(self.time_data)
        mid = (t[0] + t[-1]) / 2
        span = max((t[-1] - t[0]) * 0.15, 0.1)

        self.cursor1.setValue(mid - span)
        self.cursor2.setValue(mid + span)
        self._update_measure_labels()
    else:
        self.lbl_measure.setText("Cursori disattivati")


# ============================================================
# 7) SOSTITUISCI _update_measure_labels()
# ============================================================
def _update_measure_labels(self):
    if not self.measure_active or len(self.time_data) < 2:
        return

    t = np.asarray(self.time_data)
    p = np.asarray(self.press_data)
    f = np.asarray(self.flow_data)

    idx1 = int(np.argmin(np.abs(t - self.cursor1.value())))
    idx2 = int(np.argmin(np.abs(t - self.cursor2.value())))

    t1, t2 = t[idx1], t[idx2]
    p1, p2 = p[idx1], p[idx2]
    f1, f2 = f[idx1], f[idx2]

    unit = self.lbl_flow_unit.text()

    self.cursor1_tag.setHtml(
        "<div style='padding:5px 7px; color:#f8fafc;'>"
        "<span style='color:#f472b6; font-weight:700;'>C1</span>"
        f"&nbsp;&nbsp;{t1:.2f} s<br>"
        f"<span style='color:#93c5fd;'>P {p1:.3f} bar</span><br>"
        f"<span style='color:#6ee7b7;'>F {f1:.2f} {unit}</span>"
        "</div>"
    )

    self.cursor2_tag.setHtml(
        "<div style='padding:5px 7px; color:#f8fafc;'>"
        "<span style='color:#fbbf24; font-weight:700;'>C2</span>"
        f"&nbsp;&nbsp;{t2:.2f} s<br>"
        f"<span style='color:#93c5fd;'>P {p2:.3f} bar</span><br>"
        f"<span style='color:#6ee7b7;'>F {f2:.2f} {unit}</span>"
        "</div>"
    )

    self._update_cursor_tag_positions()

    self.lbl_measure.setText(
        "<span style='color:#94a3b8;'>Differenze:</span>"
        f"&nbsp;&nbsp;<b>Δt</b> {abs(t2-t1):.2f} s"
        f"&nbsp;&nbsp;&nbsp;<b>ΔP</b> {p2-p1:+.3f} bar"
        f"&nbsp;&nbsp;&nbsp;<b>ΔF</b> {f2-f1:+.2f} {unit}"
    )


# ============================================================
# 8) AGGIUNGI QUESTO METODO PER HEADER/FOOTER PDF
# ============================================================
def _draw_pdf_page(self, canvas, doc):
    canvas.saveState()

    width, height = A4

    # Header
    canvas.setFillColor(colors.HexColor('#0f172a'))
    canvas.rect(0, height - 22*mm, width, 22*mm, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(18*mm, height - 14*mm, "AIR CONSUMPTION METER")

    canvas.setFillColor(colors.HexColor('#94a3b8'))
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(
        width - 18*mm,
        height - 14*mm,
        datetime.now().strftime("%d/%m/%Y  %H:%M")
    )

    # Footer
    canvas.setStrokeColor(colors.HexColor('#cbd5e1'))
    canvas.line(18*mm, 13*mm, width - 18*mm, 13*mm)

    canvas.setFillColor(colors.HexColor('#64748b'))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18*mm, 8*mm, "ESP32 + ADS1115 Air Flow Analyser")
    canvas.drawRightString(
        width - 18*mm,
        8*mm,
        f"Pagina {doc.page}"
    )

    canvas.restoreState()


# ============================================================
# 9) SOSTITUISCI COMPLETAMENTE generate_pdf_report()
# ============================================================
def generate_pdf_report(self):
    if not REPORTLAB_AVAILABLE:
        QMessageBox.warning(
            self, "Manca reportlab",
            "Installa con:\npip install reportlab"
        )
        return

    if len(self.press_data) < 5:
        QMessageBox.warning(
            self, "Dati insufficienti",
            "Servono più campioni."
        )
        return

    path, _ = QFileDialog.getSaveFileName(
        self,
        "Salva Report PDF",
        f"report_air_{datetime.now():%Y%m%d_%H%M%S}.pdf",
        "PDF (*.pdf)"
    )
    if not path:
        return

    temp_graph = None

    try:
        p = np.asarray(self.press_data, dtype=float)
        t = np.asarray(self.time_data, dtype=float)
        raw = np.asarray(self.flow_raw_data, dtype=float)

        duration = float(t[-1] - t[0]) if len(t) > 1 else 0.0

        unit_keys = list(REF_CONDITIONS.keys())
        flows_by_unit = {}
        totals_by_unit = {}

        for uk in unit_keys:
            fl = np.asarray([
                self.convert_flow_for_unit(raw[i], p[i], uk)
                for i in range(len(raw))
            ], dtype=float)

            flows_by_unit[uk] = fl

            total_u = 0.0
            for i in range(1, len(t)):
                if fl[i] >= 0:
                    dt_min = (t[i] - t[i - 1]) / 60.0
                    if dt_min > 0:
                        total_u += fl[i] * dt_min

            totals_by_unit[uk] = total_u

        current_flow = flows_by_unit[self.flow_unit]
        current_ref = REF_CONDITIONS[self.flow_unit]
        current_unit = current_ref["unit"] if current_ref else "l/min"
        volume_unit = current_unit.replace("/min", "")

        # Snapshot del grafico GUI
        try:
            fd, temp_graph = tempfile.mkstemp(suffix=".png")
            os.close(fd)

            exporter = pyqtgraph.exporters.ImageExporter(self.plot)
            exporter.parameters()['width'] = 1500
            exporter.export(temp_graph)
        except Exception:
            temp_graph = None

        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            rightMargin=18*mm,
            leftMargin=18*mm,
            topMargin=30*mm,
            bottomMargin=20*mm
        )

        styles = getSampleStyleSheet()

        section = ParagraphStyle(
            'Section',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=colors.HexColor('#0f172a'),
            spaceBefore=10,
            spaceAfter=6
        )

        small = ParagraphStyle(
            'Small',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#475569')
        )

        elements = []

        # Titolo report
        elements.append(Paragraph(
            "<b>Report di misura del consumo aria</b>",
            ParagraphStyle(
                'ReportTitle',
                parent=styles['Title'],
                fontName='Helvetica-Bold',
                fontSize=18,
                textColor=colors.HexColor('#0f172a'),
                leading=21,
                spaceAfter=4
            )
        ))
        elements.append(Paragraph(
            "Analisi pressione, portata e volume totalizzato",
            ParagraphStyle(
                'SubTitle',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#64748b'),
                spaceAfter=12
            )
        ))

        # KPI
        def kpi(title, value, subtitle):
            return Table(
                [[
                    Paragraph(
                        f"<font color='#64748b' size='8'>{title}</font><br/>"
                        f"<font color='#0f172a' size='16'><b>{value}</b></font><br/>"
                        f"<font color='#94a3b8' size='7'>{subtitle}</font>",
                        styles['Normal']
                    )
                ]],
                colWidths=[51*mm],
                rowHeights=[24*mm],
                style=TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
                    ('BOX', (0,0), (-1,-1), 0.7, colors.HexColor('#cbd5e1')),
                    ('LEFTPADDING', (0,0), (-1,-1), 7),
                    ('RIGHTPADDING', (0,0), (-1,-1), 7),
                    ('TOPPADDING', (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ])
            )

        kpi_row = Table(
            [[
                kpi("DURATA", f"{duration:.1f} s", f"{len(t)} campioni"),
                kpi("PRESSIONE MEDIA", f"{np.mean(p):.3f} bar",
                    f"min {np.min(p):.3f} · max {np.max(p):.3f}"),
                kpi("PORTATA MEDIA", f"{np.mean(current_flow):.2f}",
                    current_unit),
            ]],
            colWidths=[55*mm, 55*mm, 55*mm]
        )
        kpi_row.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(kpi_row)
        elements.append(Spacer(1, 5))

        total_card = Table(
            [[
                Paragraph(
                    "<font color='#92400e' size='9'>CONSUMO TOTALE</font><br/>"
                    f"<font color='#78350f' size='19'><b>"
                    f"{totals_by_unit[self.flow_unit]:.2f} {volume_unit}"
                    "</b></font>",
                    styles['Normal']
                ),
                Paragraph(
                    "<font color='#64748b' size='8'>Condizioni correnti</font><br/>"
                    f"<font color='#0f172a' size='10'><b>{self.flow_unit}</b></font><br/>"
                    f"<font color='#475569' size='8'>T = {self.temperature_c:.1f} °C</font>",
                    styles['Normal']
                )
            ]],
            colWidths=[85*mm, 80*mm],
            style=TableStyle([
                ('BACKGROUND', (0,0), (0,0), colors.HexColor('#fef3c7')),
                ('BACKGROUND', (1,0), (1,0), colors.HexColor('#f8fafc')),
                ('BOX', (0,0), (-1,-1), 0.7, colors.HexColor('#cbd5e1')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('LEFTPADDING', (0,0), (-1,-1), 9),
                ('RIGHTPADDING', (0,0), (-1,-1), 9),
                ('TOPPADDING', (0,0), (-1,-1), 7),
                ('BOTTOMPADDING', (0,0), (-1,-1), 7),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ])
        )
        elements.append(total_card)
        elements.append(Spacer(1, 12))

        # Grafico
        if temp_graph and os.path.exists(temp_graph):
            elements.append(Paragraph("Andamento temporale", section))
            img = Image(temp_graph, width=174*mm, height=86*mm)
            elements.append(img)
            elements.append(Spacer(1, 8))

        # Statistiche pressione
        elements.append(Paragraph("Statistiche pressione", section))

        stats_p = [
            ["Grandezza", "Min", "Max", "Media", "Dev. std"],
            [
                "Pressione [bar]",
                f"{np.min(p):.4f}",
                f"{np.max(p):.4f}",
                f"{np.mean(p):.4f}",
                f"{np.std(p):.4f}"
            ],
        ]

        st_p = Table(
            stats_p,
            colWidths=[45*mm, 30*mm, 30*mm, 30*mm, 30*mm]
        )
        st_p.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#1e293b')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8.5),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(st_p)
        elements.append(Spacer(1, 8))

        # Tutte le unità
        elements.append(Paragraph("Confronto unità di portata", section))

        stats_f = [
            ["Riferimento", "Min", "Max", "Media", "Dev. std", "Totale"]
        ]

        for uk in unit_keys:
            fl = flows_by_unit[uk]
            ref = REF_CONDITIONS[uk]
            short = ref["unit"] if ref else "l/min"
            vol = short.replace("/min", "")

            stats_f.append([
                uk,
                f"{np.min(fl):.2f}",
                f"{np.max(fl):.2f}",
                f"{np.mean(fl):.2f}",
                f"{np.std(fl):.2f}",
                f"{totals_by_unit[uk]:.2f} {vol}",
            ])

        st_f = Table(
            stats_f,
            colWidths=[51*mm, 21*mm, 21*mm, 21*mm, 23*mm, 30*mm],
            repeatRows=1
        )
        st_f.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),

            ('BACKGROUND', (0,1), (-1,-1), colors.white),
            ('ROWBACKGROUNDS', (0,1), (-1,-1),
             [colors.white, colors.HexColor('#f8fafc')]),

            ('GRID', (0,0), (-1,-1), 0.45, colors.HexColor('#cbd5e1')),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTSIZE', (0,0), (-1,-1), 7.8),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(st_f)

        elements.append(Spacer(1, 12))

        # Note tecniche
        note_data = [[Paragraph(
            "<b>Condizioni di normalizzazione</b><br/>"
            "La conversione utilizza "
            "Q<sub>norm</sub> = Q<sub>mis</sub> × "
            "(P<sub>ass</sub>/P<sub>n</sub>) × (T<sub>n</sub>/T).<br/>"
            "P<sub>ass</sub> = P<sub>gauge</sub> + 1,01325 bar. "
            f"Temperatura impostata: {self.temperature_c:.1f} °C.",
            small
        )]]

        note = Table(note_data, colWidths=[165*mm])
        note.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ]))
        elements.append(note)

        doc.build(
            elements,
            onFirstPage=self._draw_pdf_page,
            onLaterPages=self._draw_pdf_page
        )

        self.status.showMessage(f"Report salvato: {path}", 5000)
        QMessageBox.information(
            self,
            "PDF",
            f"Report creato:\n{path}"
        )

    except Exception as e:
        QMessageBox.critical(
            self,
            "Errore PDF",
            str(e)
        )

    finally:
        if temp_graph and os.path.exists(temp_graph):
            try:
                os.remove(temp_graph)
            except Exception:
                pass
