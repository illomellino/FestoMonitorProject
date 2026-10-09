from datetime import datetime
import numpy as np
from PyQt6.QtWidgets import QMessageBox, QFileDialog

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def _fmt_ts(ts):
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(ts)


def generate_pdf_report(parent_widget, press_data, time_data, flow_data,
                        cursor_range=None):
    """
    Report PDF B/N.
    Se cursor_range=(t_lo, t_hi) è fornito, filtra solo quell'intervallo.
    """
    if not REPORTLAB_AVAILABLE:
        QMessageBox.warning(
            parent_widget, "Manca reportlab",
            "Installa con:\npip install reportlab"
        )
        return
    if len(press_data) < 5:
        QMessageBox.warning(parent_widget, "Dati insufficienti", "Servono più campioni.")
        return

    p = np.array(press_data)
    t = np.array(time_data)
    f = np.array(flow_data)

    interval_note = "Registrazione completa"
    if cursor_range is not None:
        t_lo, t_hi = cursor_range
        mask = (t >= t_lo) & (t <= t_hi)
        if np.sum(mask) < 5:
            QMessageBox.warning(
                parent_widget, "Intervallo insufficiente",
                "L'intervallo tra i cursori contiene meno di 5 campioni."
            )
            return
        p = p[mask]
        t = t[mask]
        f = f[mask]
        interval_note = "Solo intervallo cursori C1–C2"

    path, _ = QFileDialog.getSaveFileName(
        parent_widget, "Salva Report PDF",
        f"report_air_{datetime.now():%Y%m%d_%H%M%S}.pdf",
        "PDF (*.pdf)"
    )
    if not path:
        return

    try:
        duration = float(t[-1] - t[0]) if len(t) > 1 else 0.0

        total_nl = 0.0
        for i in range(1, len(t)):
            if f[i] >= 0:
                dt_min = (t[i] - t[i - 1]) / 60.0
                if 0 < dt_min < 10:
                    total_nl += f[i] * dt_min

        valid_f = f[f >= 0]
        if len(valid_f) == 0:
            valid_f = f

        doc = SimpleDocTemplate(
            path, pagesize=A4,
            rightMargin=18 * mm, leftMargin=18 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title', parent=styles['Heading1'],
            fontSize=16, spaceAfter=8, textColor=colors.black
        )
        h2 = ParagraphStyle(
            'H2', parent=styles['Heading2'],
            fontSize=12, spaceBefore=10, spaceAfter=4, textColor=colors.black
        )
        note_style = ParagraphStyle(
            'Note', parent=styles['Normal'],
            fontSize=9, textColor=colors.black, spaceAfter=6
        )

        elements = [
            Paragraph("AirFlowTrace | Pneumatic Data Logger | Report", title_style),
            Paragraph(
                "Valori già normalizzati dallo strumento secondo DIN 1343 "
                "(Pn = 1,01325 bar · Tn = 0 °C).",
                note_style
            ),
        ]

        header = [
            ["Logger", "AirFlow (ESP32 + ADS1115)"],
            ["Unità di misura", "Nl/min (DIN 1343)"],
            ["Ambito report", interval_note],
            ["Inizio", _fmt_ts(t[0])],
            ["Fine", _fmt_ts(t[-1])],
            ["Durata", f"{duration:.1f} s"],
            ["Campioni", str(len(p))],
            ["Consumo totale", f"{total_nl:.2f} Nl"],
            ["Report generato", datetime.now().strftime("%d/%m/%Y %H:%M:%S")],
        ]
        ht = Table(header, colWidths=[50 * mm, 124 * mm])
        ht.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('LINEBELOW', (0, 0), (-1, -2), 0.3, colors.grey),
        ]))
        elements.append(ht)
        elements.append(Spacer(1, 14))

        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.black),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ])

        elements.append(Paragraph("Statistiche Pressione", h2))
        stats_p = [
            ["Grandezza", "Minimo", "Massimo", "Media"],
            [
                "Pressione (bar)",
                f"{np.min(p):.4f}",
                f"{np.max(p):.4f}",
                f"{np.mean(p):.4f}",
            ],
        ]
        st_p = Table(stats_p, colWidths=[50 * mm, 40 * mm, 40 * mm, 44 * mm])
        st_p.setStyle(table_style)
        elements.append(st_p)
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Statistiche Portata", h2))
        stats_f = [
            ["Grandezza", "Minimo", "Massimo", "Media"],
            [
                "Portata (Nl/min)",
                f"{np.min(valid_f):.2f}",
                f"{np.max(valid_f):.2f}",
                f"{np.mean(valid_f):.2f}",
            ],
        ]
        st_f = Table(stats_f, colWidths=[50 * mm, 40 * mm, 40 * mm, 44 * mm])
        st_f.setStyle(table_style)
        elements.append(st_f)

        doc.build(elements)
        QMessageBox.information(
            parent_widget, "Report PDF",
            f"Salvato correttamente in:\n{path}"
        )
    except Exception as e:
        QMessageBox.critical(parent_widget, "Errore PDF", str(e))
