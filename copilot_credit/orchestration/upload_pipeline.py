import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil
import json
from pathlib import Path
from agents.ocr_agent import process_document
from agents.identity_agent import verify_identity
from agents.financial_agent import analyze_finances
from agents.scoring_agent import score_dossier
from agents.memo_agent import generate_memo, save_memo_pdf


UPLOAD_DIR = Path("output/uploads")


def _save_uploaded_file(uploaded_file, prefix: str) -> str:
    """Sauvegarde un fichier uploade et retourne son chemin."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(uploaded_file.name).suffix
    dest = UPLOAD_DIR / f"{prefix}{ext}"
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(dest)


def build_profile_from_ocr(ocr_cin: dict, ocr_paie: dict,
                            ocr_releve: dict, saisie_manuelle: dict) -> dict:
    """
    Construit un profil JSON depuis les donnees OCR extraites
    et les champs saisis manuellement par le banquier.
    """
    paie = ocr_paie or {}
    cin_data = ocr_cin or {}
    releve = ocr_releve or {}

    # CIN : priorite fiche de paie > CIN > releve
    cin = (paie.get("cin") or cin_data.get("cin")
           or releve.get("cin") or "00000000")

    # Nom / prenom : depuis fiche de paie (employe) ou CIN
    employe = paie.get("employe", "")
    if employe and " " in employe:
        parts = employe.split(" ", 1)
        prenom = cin_data.get("prenom") or parts[0]
        nom    = cin_data.get("nom") or parts[1]
    else:
        prenom = cin_data.get("prenom") or ""
        nom    = cin_data.get("nom") or employe or ""

    # Salaire : depuis OCR fiche de paie
    salaire_net  = paie.get("salaire_net") or 0
    salaire_brut = paie.get("salaire_brut") or (
        round(salaire_net / 0.78, 2) if salaire_net else 0
    )

    # Mensualite calculee depuis montant + duree saisis
    montant = float(saisie_manuelle.get("montant_demande", 0))
    duree   = int(saisie_manuelle.get("duree_mois", 36))
    taux    = 0.095
    taux_m  = taux / 12
    if montant > 0 and duree > 0:
        mensualite = round(
            (montant * taux_m) / (1 - (1 + taux_m) ** (-duree)), 2
        )
    else:
        mensualite = 0

    profile = {
        "cin": cin,
        "nom": nom,
        "prenom": prenom,
        "date_naissance": cin_data.get("date_naissance", ""),
        "adresse": cin_data.get("adresse") or releve.get("adresse", ""),
        "employeur": paie.get("employeur", ""),
        "poste": paie.get("poste", ""),
        "salaire_brut": salaire_brut,
        "salaire_net": salaire_net,
        "solde_moyen_3mois": releve.get("solde_final") or 0,

        # Champs saisis manuellement par le banquier
        "anciennete_annees": int(saisie_manuelle.get("anciennete_annees", 1)),
        "nb_credits_en_cours": int(saisie_manuelle.get("nb_credits_en_cours", 0)),
        "incidents_bancaires": int(saisie_manuelle.get("incidents_bancaires", 0)),
        "montant_demande": montant,
        "duree_mois": duree,
        "taux_interet": taux,
        "mensualite_calculee": mensualite,
        "motif": saisie_manuelle.get("motif", "Non specifie"),

        # Marqueur : profil reconstruit depuis upload
        "source": "upload",
    }
    return profile


def process_upload(cin_recto_file, paie_file, releve_file,
                   saisie_manuelle: dict) -> dict:
    """
    Pipeline complet pour un dossier uploade.
    Retourne le state final avec tous les rapports.
    """
    result = {
        "ocr_cin": None,
        "ocr_paie": None,
        "ocr_releve": None,
        "profile": None,
        "identity_report": None,
        "financial_report": None,
        "scoring_report": None,
        "memo_result": None,
        "decision_finale": None,
        "hitl_requis": False,
        "hitl_raison": None,
        "erreurs": [],
    }

    # 1. Sauvegarder et OCR chaque document
    try:
        if cin_recto_file:
            cin_path = _save_uploaded_file(cin_recto_file, "cin_recto_upload")
            result["ocr_cin"] = process_document(cin_path)
    except Exception as e:
        result["erreurs"].append(f"OCR CIN : {str(e)}")

    try:
        if paie_file:
            paie_path = _save_uploaded_file(paie_file, "payslip_upload")
            result["ocr_paie"] = process_document(paie_path)
    except Exception as e:
        result["erreurs"].append(f"OCR Paie : {str(e)}")

    try:
        if releve_file:
            releve_path = _save_uploaded_file(releve_file, "statement_upload")
            result["ocr_releve"] = process_document(releve_path)
    except Exception as e:
        result["erreurs"].append(f"OCR Releve : {str(e)}")

    # 2. Construire le profil
    profile = build_profile_from_ocr(
        result["ocr_cin"], result["ocr_paie"],
        result["ocr_releve"], saisie_manuelle
    )
    result["profile"] = profile

    # 3. Verification identite
    ocr_results = {
        "cin": result["ocr_cin"] or {},
        "fiche_de_paie": result["ocr_paie"] or {},
        "releve_bancaire": result["ocr_releve"] or {},
    }
    result["identity_report"] = verify_identity(ocr_results)
    if result["identity_report"].get("hitl_requis"):
        result["hitl_requis"] = True
        result["hitl_raison"] = "Identite : " + result["identity_report"].get("recommandation", "")

    # 4. Analyse financiere
    result["financial_report"] = analyze_finances(ocr_results, profile)
    if result["financial_report"].get("hitl_requis"):
        result["hitl_requis"] = True
        if not result["hitl_raison"]:
            result["hitl_raison"] = "Finance : " + result["financial_report"].get("recommandation", "")

    # 5. Scoring
    result["scoring_report"] = score_dossier(profile, ocr_results)
    result["decision_finale"] = result["scoring_report"].get("decision")
    if result["scoring_report"].get("hitl_requis"):
        result["hitl_requis"] = True
        if not result["hitl_raison"]:
            result["hitl_raison"] = "Scoring : zone orange - verification requise"

    # 6. Memo
    result["memo_result"] = generate_memo(
        profile, result["identity_report"],
        result["financial_report"], result["scoring_report"]
    )
    if not result["memo_result"].get("erreur"):
        try:
            pdf_path = save_memo_pdf(result["memo_result"])
            result["memo_result"]["pdf_path"] = pdf_path
        except Exception as e:
            result["erreurs"].append(f"PDF : {str(e)}")

    return result