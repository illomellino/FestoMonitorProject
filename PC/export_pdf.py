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


def generate_pdf_report(parent_widget, press_data, time_data, flow_data):
    """
    Genera un report PDF con i valori già normalizzati dallo strumento
    (Nl/min DIN 1343 – 1,01325 bar / 0 °C).
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

    path, _ = QFileDialog.getSaveFileName(
        parent_widget, "Salva Report PDF",
        f"report_air_{datetime.now():%Y%m%d_%H%M%S}.pdf",
        "PDF (*.pdf)"
    )
    if not path:
        return

    try:
        p = np.array(press_data)
        t = np.array(time_data)
        f = np.array(flow_data)
        duration = t[-1] - t[0] if len(t) > 1 else 0.0

        # Consumo totale (Nl)
        total_nl = 0.0
        for i in range(1, len(t)):
            if f[i] >= 0:
                dt_min = (t[i] - t[i - 1]) / 60.0
                if dt_min > 0:
                    total_nl += f[i] * dt_min

        doc = SimpleDocTemplate(
            path, pagesize=A4,
            rightMargin=18 * mm, leftMargin=18 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title', parent=styles['Heading1'],
            fontSize=16, spaceAfter=10,
            textColor=colors.HexColor('#89b4fa')
        )
        h2 = ParagraphStyle(
            'H2', parent=styles['Heading2'],
            fontSize=12, spaceBefore=8, spaceAfter=4,
            textColor=colors.HexColor('#b4befe')
        )
        note_style = ParagraphStyle(
            'Note', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#a6adc8'),
            spaceAfter=8
        )

        elements = [
            Paragraph("Air Consumption Meter – Report Analisi", title_style),
            Paragraph(
                "Valori già normalizzati dallo strumento secondo <b>DIN 1343</b> "
                "(Pn = 1,01325 bar · Tn = 0 °C).",
                note_style
            ),
        ]

        # Header sessione
        header = [
            ["Logger:", "AirFlow (ESP32 + ADS1115)"],
            ["Unità di misura:", "Nl/min  (DIN 1343)"],
            ["Durata sessione:", f"{duration:.1f} s"],
            ["Campioni totali:", str(len(p))],
            ["Consumo totale:", f"{total_nl:.2f} Nl"],
        ]
        ht = Table(header, colWidths=[55 * mm, 119 * mm])
        ht.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#a6adc8')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#cdd6f4')),
        ]))
        elements.append(ht)
        elements.append(Spacer(1, 12))

        # Statistiche pressione
        elements.append(Paragraph("<b>Statistiche Pressione</b>", h2))
        stats_p = [
            ["Grandezza", "Minimo", "Massimo", "Media", "Dev.Std"],
            [
                "Pressione (bar)",
                f"{np.min(p):.4f}",
                f"{np.max(p):.4f}",
                f"{np.mean(p):.4f}",
                f"{np.std(p):.4e}",
            ],
        ]
        st_p = Table(stats_p, colWidths=[45 * mm, 30 * mm, 30 * mm, 30 * mm, 39 * mm])
        st_p.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#313244')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#45475a')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#1e1e2e')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#cdd6f4')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(st_p)
        elements.append(Spacer(1, 12))

        # Statistiche portata (unica unità)
        elements.append(Paragraph("<b>Statistiche Portata</b>", h2))
        # filtra eventuali valori di fault (-999 / -998)
        valid = f[f >= 0]
        if len(valid) == 0:
            valid = f
        stats_f = [
            ["Grandezza", "Minimo", "Massimo", "Media", "Dev.Std", "Consumo Tot."],
            [
                "Portata (Nl/min)",
                f"{np.min(valid):.2f}",
                f"{np.max(valid):.2f}",
                f"{np.mean(valid):.2f}",
                f"{np.std(valid):.2e}",
                f"{total_nl:.2f} Nl",
            ],
        ]
        st_f = Table(stats_f, colWidths=[42 * mm, 25 * mm, 25 * mm, 25 * mm, 32 * mm, 35 * mm])
        st_f.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#313244')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#45475a')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#1e1e2e')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#cdd6f4')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(st_f)

        doc.build(elements)
        QMessageBox.information(
            parent_widget, "Report PDF",
            f"Salvato correttamente in:\n{path}"
        )
    except Exception as e:
        QMessageBox.critical(parent_widget, "Errore PDF", str(e))
