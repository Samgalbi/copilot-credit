import re
import json
from datetime import date, datetime


def _valider_format_cin(cin: str) -> dict:
    result = {"valide": False, "message": ""}
    if not cin:
        result["message"] = "CIN manquant"
        return result
    if not re.match(r"^\d{8}$", str(cin)):
        result["message"] = f"Format CIN invalide : '{cin}' (doit etre 8 chiffres)"
        return result
    result["valide"] = True
    result["message"] = "Format CIN valide"
    return result


def _valider_age(date_naissance_str: str) -> dict:
    result = {"valide": False, "age": None, "message": ""}
    if not date_naissance_str:
        result["message"] = "Date de naissance manquante"
        return result
    try:
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        dob = None
        for fmt in formats:
            try:
                dob = datetime.strptime(date_naissance_str, fmt).date()
                break
            except ValueError:
                continue
        if not dob:
            result["message"] = f"Format date non reconnu : {date_naissance_str}"
            return result
        today = date.today()
        age = (today - dob).days // 365
        result["age"] = age
        if age < 21:
            result["message"] = f"Age insuffisant : {age} ans (minimum 21 ans)"
        elif age > 65:
            result["message"] = f"Age superieur a la limite : {age} ans (maximum 65 ans)"
        else:
            result["valide"] = True
            result["message"] = f"Age valide : {age} ans"
    except Exception as e:
        result["message"] = f"Erreur calcul age : {str(e)}"
    return result


def _normaliser_nom(nom: str) -> str:
    if not nom:
        return ""
    return re.sub(r"[^a-zA-Z\s]", "", nom).strip().upper()


def _verifier_coherence_nom(nom_cin: str, prenom_cin: str,
                             nom_paie: str, prenom_paie: str) -> dict:
    result = {"coherent": False, "score": 0, "message": ""}

    nom_cin_n = _normaliser_nom(nom_cin or "")
    prenom_cin_n = _normaliser_nom(prenom_cin or "")
    nom_paie_n = _normaliser_nom(nom_paie or "")
    prenom_paie_n = _normaliser_nom(prenom_paie or "")

    if not nom_cin_n or not nom_paie_n:
        result["message"] = "Nom manquant dans un des documents - verification humaine requise"
        result["coherent"] = True
        result["score"] = 0.5
        return result

    # Correspondance exacte
    if nom_cin_n == nom_paie_n:
        result["score"] += 0.5
    elif nom_cin_n in nom_paie_n or nom_paie_n in nom_cin_n:
        result["score"] += 0.3

    if prenom_cin_n and prenom_paie_n:
        if prenom_cin_n == prenom_paie_n:
            result["score"] += 0.5
        elif prenom_cin_n in prenom_paie_n or prenom_paie_n in prenom_cin_n:
            result["score"] += 0.3
    else:
        result["score"] += 0.3

    result["coherent"] = result["score"] >= 0.5
    if result["coherent"]:
        result["message"] = f"Identite coherente (score: {result['score']:.1f})"
    else:
        result["message"] = (
            f"Incoherence identite : CIN='{nom_cin_n} {prenom_cin_n}' "
            f"vs Paie='{nom_paie_n} {prenom_paie_n}' (score: {result['score']:.1f})"
        )
    return result


def _verifier_cin_expiree(date_expiration_str: str) -> dict:
    result = {"valide": True, "message": ""}
    if not date_expiration_str:
        result["message"] = "Date expiration non disponible - supposee valide"
        return result
    try:
        formats = ["%d/%m/%Y", "%Y-%m-%d"]
        exp_date = None
        for fmt in formats:
            try:
                exp_date = datetime.strptime(date_expiration_str, fmt).date()
                break
            except ValueError:
                continue
        if not exp_date:
            result["message"] = "Format date expiration non reconnu"
            return result
        if exp_date < date.today():
            result["valide"] = False
            result["message"] = f"CIN expiree depuis le {date_expiration_str}"
        else:
            result["message"] = f"CIN valide jusqu'au {date_expiration_str}"
    except Exception as e:
        result["message"] = f"Erreur verification expiration : {str(e)}"
    return result


def _verifier_coherence_cin(cin_ocr: str, cin_paie: str,
                             cin_releve: str) -> dict:
    result = {"coherent": False, "message": "", "valeurs": {}}
    result["valeurs"] = {
        "cin_cin": cin_ocr,
        "cin_paie": cin_paie,
        "cin_releve": cin_releve,
    }
    cins = [c for c in [cin_ocr, cin_paie, cin_releve] if c]
    if not cins:
        result["message"] = "Aucun CIN trouve dans les documents"
        return result
    unique = set(cins)
    if len(unique) == 1:
        result["coherent"] = True
        result["message"] = f"CIN coherent sur tous les documents : {cins[0]}"
    else:
        result["coherent"] = False
        result["message"] = f"Incoherence CIN entre documents : {unique}"
    return result


def verify_identity(ocr_results: dict) -> dict:
    cin_data     = ocr_results.get("cin", {})
    payslip_data = ocr_results.get("fiche_de_paie", {})
    releve_data  = ocr_results.get("releve_bancaire", {})

    rapport = {
        "statut": "VALIDE",
        "score_confiance": 0,
        "alertes": [],
        "details": {},
        "recommandation": "",
        "hitl_requis": False,
    }

    checks = []

    # 1. Format CIN
    cin_principal = (cin_data.get("cin")
                     or payslip_data.get("cin")
                     or releve_data.get("cin"))
    check_cin = _valider_format_cin(cin_principal)
    rapport["details"]["format_cin"] = check_cin
    checks.append(check_cin["valide"])
    if not check_cin["valide"]:
        rapport["alertes"].append(f"FORMAT CIN : {check_cin['message']}")

    # 2. Age
    date_naissance = cin_data.get("date_naissance")
    check_age = _valider_age(date_naissance)
    rapport["details"]["age"] = check_age
    checks.append(check_age["valide"])
    if not check_age["valide"] and check_age["age"] is not None:
        rapport["alertes"].append(f"AGE : {check_age['message']}")

    # 3. CIN non expiree
    date_exp = cin_data.get("date_expiration", "31/12/2029")
    check_exp = _verifier_cin_expiree(date_exp)
    rapport["details"]["expiration_cin"] = check_exp
    checks.append(check_exp["valide"])
    if not check_exp["valide"]:
        rapport["alertes"].append(f"EXPIRATION : {check_exp['message']}")

    # 4. Coherence CIN cross-documents
    check_cin_cross = _verifier_coherence_cin(
        cin_data.get("cin"),
        payslip_data.get("cin"),
        releve_data.get("cin"),
    )
    rapport["details"]["coherence_cin"] = check_cin_cross
    checks.append(check_cin_cross["coherent"])
    if not check_cin_cross["coherent"]:
        rapport["alertes"].append(f"COHERENCE CIN : {check_cin_cross['message']}")

    # 5. Coherence nom/prenom
    nom_cin    = cin_data.get("nom")
    prenom_cin = cin_data.get("prenom")
    employe    = payslip_data.get("employe", "")
    if employe and " " in employe:
        parts = employe.split(" ", 1)
        prenom_paie, nom_paie = parts[0], parts[1]
    else:
        prenom_paie, nom_paie = "", employe or ""

    check_nom = _verifier_coherence_nom(nom_cin, prenom_cin,
                                         nom_paie, prenom_paie)
    rapport["details"]["coherence_nom"] = check_nom
    checks.append(check_nom["coherent"])
    if not check_nom["coherent"]:
        rapport["alertes"].append(f"IDENTITE : {check_nom['message']}")

    # Score global
    nb_valides = sum(1 for c in checks if c)
    rapport["score_confiance"] = round(nb_valides / len(checks), 2) if checks else 0

    # Statut final
    if rapport["score_confiance"] == 1.0:
        rapport["statut"] = "VALIDE"
        rapport["recommandation"] = "Identite verifiee - pipeline peut continuer"
        rapport["hitl_requis"] = False
    elif rapport["score_confiance"] >= 0.6:
        rapport["statut"] = "ALERTE"
        rapport["recommandation"] = "Anomalies mineures - verification humaine recommandee"
        rapport["hitl_requis"] = True
    else:
        rapport["statut"] = "REJETE"
        rapport["recommandation"] = "Identite non verifiable - dossier bloque"
        rapport["hitl_requis"] = True

    return rapport


if __name__ == "__main__":
    import json
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.ocr_agent import process_document
    from pathlib import Path

    # Charger un dossier complet
    cin_files = sorted(Path("output/cin").glob("cin_recto_*.png"))
    if not cin_files:
        print("Aucune CIN trouvee")
        sys.exit(1)

    cin_file = cin_files[0]
    cin_num = cin_file.stem.replace("cin_recto_", "")
    print(f"\nTest sur dossier CIN : {cin_num}")
    print("=" * 50)

    ocr_results = {}

    # OCR CIN
    res_cin = process_document(str(cin_file))
    ocr_results["cin"] = res_cin
    print(f"CIN OCR     -> cin={res_cin.get('cin')}, "
          f"nom={res_cin.get('nom')}, conf={res_cin.get('confidence_moyenne')}")

    # OCR Fiche de paie
    paie_file = Path(f"output/payslips/payslip_{cin_num}.pdf")
    if paie_file.exists():
        res_paie = process_document(str(paie_file))
        ocr_results["fiche_de_paie"] = res_paie
        print(f"Paie OCR    -> employe={res_paie.get('employe')}, "
              f"cin={res_paie.get('cin')}, conf={res_paie.get('confidence_moyenne')}")

    # OCR Releve
    releve_file = Path(f"output/statements/statement_{cin_num}.pdf")
    if releve_file.exists():
        res_releve = process_document(str(releve_file))
        ocr_results["releve_bancaire"] = res_releve
        print(f"Releve OCR  -> titulaire={res_releve.get('titulaire')}, "
              f"cin={res_releve.get('cin')}, conf={res_releve.get('confidence_moyenne')}")

    print("\n--- Rapport Verification Identite ---")
    rapport = verify_identity(ocr_results)
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
