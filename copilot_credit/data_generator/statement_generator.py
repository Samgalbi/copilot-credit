from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from pathlib import Path
from datetime import date, timedelta
import random


DESCRIPTIONS_CREDIT = [
    "Virement salaire", "Remboursement client", "Virement famille",
    "Depot especes", "Virement entrant",
]

DESCRIPTIONS_DEBIT = [
    "Achat supermarche", "Facture STEG", "Facture SONEDE",
    "Retrait DAB", "Paiement en ligne", "Abonnement telephone",
    "Restaurant", "Carburant", "Pharmacie", "Loyer",
]


def _generer_transactions(solde_moyen: float, nb_jours: int = 90):
    transactions = []
    solde = solde_moyen * random.uniform(0.8, 1.2)
    date_courante = date.today() - timedelta(days=nb_jours)

    while date_courante <= date.today():
        nb_ops = random.randint(0, 3)
        for _ in range(nb_ops):
            if random.random() < 0.35:
                montant = round(random.uniform(500, 3000), 2)
                desc = random.choice(DESCRIPTIONS_CREDIT)
                solde += montant
                transactions.append({
                    "date": date_courante.strftime("%d/%m/%Y"),
                    "description": desc,
                    "credit": f"{montant:.2f}",
                    "debit": "",
                    "solde": f"{solde:.2f}",
                })
            else:
                montant = round(random.uniform(20, 400), 2)
                desc = random.choice(DESCRIPTIONS_DEBIT)
                solde -= montant
                transactions.append({
                    "date": date_courante.strftime("%d/%m/%Y"),
                    "description": desc,
                    "credit": "",
                    "debit": f"{montant:.2f}",
                    "solde": f"{solde:.2f}",
                })
        date_courante += timedelta(days=1)

    return transactions


def generate_statement(profile: dict, output_dir: str = "output/statements") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{output_dir}/statement_{profile['cin']}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('title', parent=styles['Heading1'],
                                  fontSize=14, textColor=colors.HexColor('#003366'))
    normal = styles['Normal']
    normal.fontSize = 9

    # En-tete banque
    story.append(Paragraph("ATTIJARI BANK TUNISIE", title_style))
    story.append(Paragraph("Releve de Compte - 3 derniers mois", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))

    # Infos client
    info_data = [
        ["Titulaire :", f"{profile['prenom']} {profile['nom']}", "CIN :", profile['cin']],
        ["Adresse :", profile['adresse'], "Tel :", profile['telephone']],
        ["Periode :", "Mars 2026 - Mai 2026", "Agence :", "Agence Principale"],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 7*cm, 2.5*cm, 4.5*cm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#003366')),
        ('TEXTCOLOR', (2,0), (2,-1), colors.HexColor('#003366')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))

    # Tableau transactions
    transactions = _generer_transactions(profile['solde_moyen_3mois'])
    table_data = [["Date", "Description", "Credit (DT)", "Debit (DT)", "Solde (DT)"]]
    for t in transactions:
        table_data.append([
            t['date'], t['description'],
            t['credit'], t['debit'], t['solde']
        ])

    col_widths = [2.5*cm, 7*cm, 3*cm, 3*cm, 3*cm]
    trans_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    trans_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7F7F7')]),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#CCCCCC')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(trans_table)
    story.append(Spacer(1, 0.5*cm))

    # Solde final
    solde_final = transactions[-1]['solde'] if transactions else "0.00"
    story.append(Paragraph(f"Solde final : {solde_final} DT", 
                           ParagraphStyle('bold', parent=normal, 
                                         fontName='Helvetica-Bold', fontSize=10,
                                         textColor=colors.HexColor('#003366'))))

    doc.build(story)
    return filename


if __name__ == "__main__":
    import json
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    for p in profiles:
        path = generate_statement(p)
        print(f"Genere : {path}")
    print("Tous les releves sont generes.")
