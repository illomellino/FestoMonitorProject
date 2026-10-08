from datetime import datetime
import numpy as np
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from config import REF_CONDITIONS
from converters import convert_flow

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def generate_pdf_report(parent_widget, press_data, time_data, flow_raw_data, flow_unit, temperature_c):
    if not REPORTLAB_AVAILABLE:
        QMessageBox.warning(parent_widget, "Manca reportlab", "Installa con:\npip install reportlab")
        return
    if len(press_data) < 5:
        QMessageBox.warning(parent_widget, "Dati insufficienti", "Servono più campioni.")
        return

    path, _ = QFileDialog.getSaveFileName(
        parent_widget, "Salva Report PDF",
        f"report_air_{datetime.now():%Y%m%d_%H%M%S}.pdf", "PDF (*.pdf)")
    if not path:
        return

    try:
        p = np.array(press_data)
        t = np.array(time_data)
        raw = np.array(flow_raw_data)
        duration = t[-1] - t[0] if len(t) > 1 else 0

        unit_keys = list(REF_CONDITIONS.keys())
        flows_by_unit = {}
        totals_by_unit = {}
        for uk in unit_keys:
            fl = np.array([convert_flow(raw[i], p[i], uk, temperature_c) for i in range(len(raw))])
            flows_by_unit[uk] = fl
            total_u = 0.0
            for i in range(1, len(t)):
                if fl[i] >= 0:
                    dt_min = (t[i] - t[i - 1]) / 60.0
                    if dt_min > 0:
                        total_u += fl[i] * dt_min
            totals_by_unit[uk] = total_u

        doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, spaceAfter=10, textColor=colors.HexColor('#89b4fa'))
        h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor('#b4befe'))

        elements = [Paragraph("Air Consumption Meter – Report Analisi", title_style)]

        header = [
            ["Logger:", "AirFlow (ESP32 + ADS1115)"],
            ["Unità di misura corrente:", flow_unit],
            ["Temperatura impostata:", f"{temperature_c:.1f} °C"],
            ["Durata sessione:", f"{duration:.1f} s"],
            ["Campioni totali:", str(len(p))],
        ]
        ht = Table(header, colWidths=[60*mm, 114*mm])
        ht.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#a6adc8')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#cdd6f4')),
        ]))
        elements.append(ht)
        elements.append(Spacer(1, 10))

        elements.append(Paragraph("<b>Statistiche Pressione</b>", h2))
        stats_p = [
            ["Grandezza", "Minimo", "Massimo", "Media", "Dev.Std"],
            ["Pressione (bar)", f"{np.min(p):.4f}", f"{np.max(p):.4f}", f"{np.mean(p):.4f}", f"{np.std(p):.4e}"],
        ]
        st_p = Table(stats_p, colWidths=[45*mm, 30*mm, 30*mm, 30*mm, 39*mm])
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
        elements.append(Spacer(1, 10))

        elements.append(Paragraph("<b>Statistiche Portata (Confronto Standard)</b>", h2))
        stats_f = [["Unità Standard", "Min", "Max", "Media", "Dev.Std", "Consumo Tot."]]
        for uk in unit_keys:
            fl = flows_by_unit[uk]
            ref = REF_CONDITIONS[uk]
            short = ref["unit"] if ref else "l/min"
            vol_unit = short.replace("/min", "")
            stats_f.append([
                uk, f"{np.min(fl):.2f}", f"{np.max(fl):.2f}", f"{np.mean(fl):.2f}",
                f"{np.std(fl):.2e}", f"{totals_by_unit[uk]:.2f} {vol_unit}"
            ])

        st_f = Table(stats_f, colWidths=[52*mm, 23*mm, 23*mm, 23*mm, 35*mm, 38*mm])
        st_f.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#313244')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#45475a')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#1e1e2e')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#cdd6f4')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(st_f)

        doc.build(elements)
        QMessageBox.information(parent_widget, "Report PDF", f"Salvato correttamente in:\n{path}")
    except Exception as e:
        QMessageBox.critical(parent_widget, "Errore PDF", str(e))