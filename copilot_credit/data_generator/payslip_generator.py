from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from pathlib import Path
import random


def generate_payslip(profile: dict, output_dir: str = "output/payslips") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{output_dir}/payslip_{profile['cin']}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Style titre
    title_style = ParagraphStyle('title', parent=styles['Heading1'],
                                  fontSize=14, textColor=colors.HexColor('#003366'),
                                  spaceAfter=6)
    normal = styles['Normal']
    normal.fontSize = 9

    # En-tete entreprise
    story.append(Paragraph(profile['employeur'].upper(), title_style))
    story.append(Paragraph("Bulletin de Paie", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))

    # Infos employe
    mois_annee = "Mai 2026"
    info_data = [
        ["Employe :", f"{profile['prenom']} {profile['nom']}", "Periode :", mois_annee],
        ["CIN :", profile['cin'], "Poste :", profile['poste']],
        ["Anciennete :", f"{profile['anciennete_annees']} ans", "Ville :", profile['adresse']],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 7*cm, 3*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#003366')),
        ('TEXTCOLOR', (2,0), (2,-1), colors.HexColor('#003366')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    # Tableau salaire
    brut = profile['salaire_brut']
    net = profile['salaire_net']
    cnss = round(brut * 0.0918, 2)
    irpp = round(brut * 0.10, 2)
    autres = round(brut - net - cnss - irpp, 2)

    sal_data = [
        ["DESIGNATION", "BASE", "TAUX", "MONTANT (DT)"],
        ["Salaire de base", f"{brut:.2f}", "100%", f"{brut:.2f}"],
        ["", "", "", ""],
        ["RETENUES", "", "", ""],
        ["Cotisation CNSS", "", "9.18%", f"-{cnss:.2f}"],
        ["IRPP", "", "10%", f"-{irpp:.2f}"],
        ["Autres retenues", "", "", f"-{autres:.2f}"],
        ["", "", "", ""],
        ["NET A PAYER", "", "", f"{net:.2f} DT"],
    ]
    sal_table = Table(sal_data, colWidths=[8*cm, 3*cm, 3*cm, 3*cm])
    sal_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor('#E8F1FB')),
        ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.white),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#F7F7F7')]),
    ]))
    story.append(sal_table)
    story.append(Spacer(1, 0.5*cm))

    # Signature
    story.append(Paragraph("Cachet et signature de l'employeur", normal))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph("_______________________________", normal))

    doc.build(story)
    return filename


if __name__ == "__main__":
    import json
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    for p in profiles:
        path = generate_payslip(p)
        print(f"Genere : {path}")
    print("Toutes les fiches de paie sont generees.")
