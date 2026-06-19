import os
import json
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from mistralai import Mistral

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL = "mistral-large-latest"


def _construire_prompt(profile: dict, identity_report: dict,
                        financial_report: dict,
                        scoring_report: dict) -> str:
    nom_complet = f"{profile.get('prenom','')} {profile.get('nom','')}"
    cin = profile.get("cin", "N/A")

    top_shap_text = "\n".join([
        f"  - {s['feature']} : impact {s['impact']} (valeur SHAP {s['shap']:+.3f})"
        for s in scoring_report.get("top_shap", [])
    ])

    prompt = f"""Tu es un assistant expert en analyse de credit bancaire pour Attijari Bank Tunisie.
Tu dois rediger un MEMO DE CREDIT structure et professionnel en francais,
destine a un charge de credit qui doit prendre une decision finale.

INFORMATIONS CLIENT :
- Nom complet : {nom_complet}
- CIN : {cin}
- Employeur : {profile.get('employeur', 'N/A')}
- Poste : {profile.get('poste', 'N/A')}
- Anciennete : {profile.get('anciennete_annees', 'N/A')} ans
- Salaire net : {profile.get('salaire_net', 'N/A')} DT

DEMANDE DE CREDIT :
- Montant demande : {profile.get('montant_demande', 'N/A')} DT
- Duree : {profile.get('duree_mois', 'N/A')} mois
- Motif : {profile.get('motif', 'N/A')}
- Mensualite calculee : {profile.get('mensualite_calculee', 'N/A')} DT

VERIFICATION IDENTITE :
- Statut : {identity_report.get('statut', 'N/A')}
- Score de confiance : {identity_report.get('score_confiance', 'N/A')}
- Alertes : {', '.join(identity_report.get('alertes', [])) or 'Aucune'}

ANALYSE FINANCIERE :
- Statut : {financial_report.get('statut', 'N/A')}
- Capacite de remboursement : {financial_report.get('capacite_remboursement', {}).get('message', 'N/A')}
- Stabilite emploi : {financial_report.get('stabilite_emploi', {}).get('message', 'N/A')}
- Alertes : {', '.join(financial_report.get('alertes', [])) or 'Aucune'}

SCORE ML DE CREDIT :
- Score : {scoring_report.get('score', 'N/A')} (echelle 0 a 1)
- Decision algorithmique : {scoring_report.get('decision', 'N/A')}
- Facteurs les plus influents (SHAP) :
{top_shap_text}

INSTRUCTIONS DE REDACTION :
Redige un memo de credit avec exactement cette structure :

1. SYNTHESE DU DOSSIER (3-4 phrases resumant la situation du client et la demande)
2. ANALYSE DE L'IDENTITE (1-2 phrases sur la fiabilite de la verification)
3. ANALYSE FINANCIERE (un paragraphe sur la capacite de remboursement et la stabilite)
4. ANALYSE DU SCORE DE CREDIT (explique en langage clair pourquoi le score est ce qu'il est,
   en t'appuyant sur les facteurs SHAP, sans jargon technique)
5. RECOMMANDATION FINALE (une phrase claire : favorable, defavorable, ou necessite verification humaine)

IMPORTANT :
- Reste factuel, base uniquement sur les donnees fournies
- N'invente aucune information non presente ci-dessus
- Le memo doit etre comprehensible par un charge de credit non technique
- Termine TOUJOURS par : "Cette recommandation est generee par IA et necessite
  la validation finale d'un charge de credit autorise."
- Ne depasse pas 350 mots
"""
    return prompt


def generate_memo(profile: dict,
                  identity_report: dict,
                  financial_report: dict,
                  scoring_report: dict) -> dict:
    if not MISTRAL_API_KEY:
        return {
            "erreur": "Cle API Mistral manquante dans .env",
            "memo_text": None,
        }

    client = Mistral(api_key=MISTRAL_API_KEY)
    prompt = _construire_prompt(
        profile, identity_report, financial_report, scoring_report
    )

    try:
        response = client.chat.complete(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800,
        )
        memo_text = response.choices[0].message.content

        return {
            "memo_text": memo_text,
            "date_generation": date.today().isoformat(),
            "cin": profile.get("cin"),
            "client": f"{profile.get('prenom')} {profile.get('nom')}",
            "decision_algo": scoring_report.get("decision"),
            "score": scoring_report.get("score"),
            "erreur": None,
        }
    except Exception as e:
        return {
            "erreur": f"Erreur API Mistral : {str(e)}",
            "memo_text": None,
        }


def save_memo_pdf(memo_result: dict, output_dir: str = "output/reports") -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    cin = memo_result.get("cin", "unknown")
    filename = f"{output_dir}/memo_credit_{cin}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=2.5*cm, leftMargin=2.5*cm,
                            topMargin=2.5*cm, bottomMargin=2.5*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('title', parent=styles['Heading1'],
                                  fontSize=15, textColor=colors.HexColor('#003366'))
    normal = ParagraphStyle('normal', parent=styles['Normal'],
                             fontSize=10, leading=15)

    story.append(Paragraph("ATTIJARI BANK TUNISIE", title_style))
    story.append(Paragraph("MEMO DE CREDIT - COPILOT CREDIT", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Client : {memo_result.get('client', 'N/A')} | "
        f"CIN : {memo_result.get('cin', 'N/A')} | "
        f"Date : {memo_result.get('date_generation', 'N/A')}",
        normal
    ))
    story.append(Spacer(1, 0.5*cm))

    memo_text = memo_result.get("memo_text", "")
    for paragraphe in memo_text.split("\n\n"):
        if paragraphe.strip():
            story.append(Paragraph(paragraphe.strip().replace("\n", "<br/>"), normal))
            story.append(Spacer(1, 0.3*cm))

    doc.build(story)
    return filename


if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.ocr_agent import process_document
    from agents.identity_agent import verify_identity
    from agents.financial_agent import analyze_finances
    from agents.scoring_agent import score_dossier

    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)

    profile = profiles[0]
    cin = profile["cin"]
    print(f"Test memo pour : {profile['prenom']} {profile['nom']} (CIN {cin})")

    ocr_results = {}
    paie_file = Path(f"output/payslips/payslip_{cin}.pdf")
    if paie_file.exists():
        ocr_results["fiche_de_paie"] = process_document(str(paie_file))

    releve_file = Path(f"output/statements/statement_{cin}.pdf")
    if releve_file.exists():
        ocr_results["releve_bancaire"] = process_document(str(releve_file))

    cin_file = Path(f"output/cin/cin_recto_{cin}.png")
    if cin_file.exists():
        ocr_results["cin"] = process_document(str(cin_file))

    identity_report  = verify_identity(ocr_results)
    financial_report = analyze_finances(ocr_results, profile)
    scoring_report    = score_dossier(profile, ocr_results)

    print("\nGeneration du memo via Mistral...")
    memo_result = generate_memo(
        profile, identity_report, financial_report, scoring_report
    )

    if memo_result.get("erreur"):
        print(f"ERREUR : {memo_result['erreur']}")
    else:
        print("\n" + "=" * 60)
        print(memo_result["memo_text"])
        print("=" * 60)

        pdf_path = save_memo_pdf(memo_result)
        print(f"\nMemo PDF sauvegarde : {pdf_path}")