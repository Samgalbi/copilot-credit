import json
import re
from pathlib import Path
from pdf2image import convert_from_path
import easyocr
import numpy as np
from PIL import Image

# Initialisation EasyOCR (francais + arabe)
reader_fr = easyocr.Reader(['fr', 'en'], gpu=False)
reader_ar = easyocr.Reader(['ar', 'en'], gpu=False)


POPPLER_PATH = r"C:\Users\GIGABYTE\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"

def _pdf_to_images(pdf_path: str) -> list:
    images = convert_from_path(pdf_path, dpi=200, poppler_path=POPPLER_PATH)
    return images


def _image_to_array(img: Image.Image) -> np.ndarray:
    return np.array(img)


def _extract_text_blocks(image_array: np.ndarray) -> list:
    results_fr = reader_fr.readtext(image_array)
    results_ar = reader_ar.readtext(image_array)
    results = results_fr + results_ar
    blocks = []
    for (bbox, text, confidence) in results:
        blocks.append({
            "text": text.strip(),
            "confidence": round(confidence, 3),
            "bbox": bbox
        })
    return blocks


def _parse_payslip(blocks: list) -> dict:
    texts = [b["text"] for b in blocks]
    data = {
        "type_document": "fiche_de_paie",
        "employe": None,
        "cin": None,
        "employeur": None,
        "poste": None,
        "periode": None,
        "salaire_brut": None,
        "salaire_net": None,
        "cnss": None,
        "irpp": None,
        "confidence_moyenne": round(
            sum(b["confidence"] for b in blocks) / len(blocks), 3
        ) if blocks else 0,
    }

    for i, t in enumerate(texts):
        next_val = texts[i+1].strip() if i+1 < len(texts) else ""
        next_next = texts[i+2].strip() if i+2 < len(texts) else ""

        # Employeur = premier bloc (nom entreprise avant "Bulletin de Paie")
        if re.search(r"bulletin de paie", t, re.IGNORECASE) and i > 0:
            data["employeur"] = texts[i-1].strip()

        # Employe
        if re.search(r"^Employe$", t, re.IGNORECASE):
            data["employe"] = next_val

        # CIN
        cin_match = re.search(r"\b(\d{8})\b", t)
        if cin_match and not data["cin"]:
            data["cin"] = cin_match.group(1)
        if re.search(r"^CIN$", t, re.IGNORECASE):
            cin_match2 = re.search(r"\d{8}", next_val)
            if cin_match2:
                data["cin"] = cin_match2.group()

        # Poste
        if re.search(r"^Poste$", t, re.IGNORECASE):
            data["poste"] = next_val

        # Periode
        if re.search(r"^Periode$", t, re.IGNORECASE):
            data["periode"] = next_val

        # Salaire brut (bloc "Salaire de base" suivi du montant)
        if re.search(r"Salaire de base", t, re.IGNORECASE):
            montant = re.search(r"\d+[\.,]\d+", next_val)
            if montant:
                data["salaire_brut"] = float(montant.group().replace(",", "."))
            else:
                montant2 = re.search(r"\d+[\.,]\d+", next_next)
                if montant2:
                    data["salaire_brut"] = float(montant2.group().replace(",", "."))

        # Net a payer
        if re.search(r"NET A PAYER", t, re.IGNORECASE):
            for j in range(i+1, min(i+4, len(texts))):
                montant = re.search(r"\d+[\.,]\d+", texts[j])
                if montant:
                    data["salaire_net"] = float(montant.group().replace(",", "."))
                    break

        # CNSS
        if re.search(r"CNSS", t, re.IGNORECASE):
            for j in range(i+1, min(i+4, len(texts))):
                montant = re.search(r"\d+[\.,]\d+", texts[j])
                if montant:
                    data["cnss"] = float(montant.group().replace(",", "."))
                    break

        # IRPP
        if re.search(r"^IRPP$", t, re.IGNORECASE):
            for j in range(i+1, min(i+4, len(texts))):
                montant = re.search(r"\d+[\.,]\d+", texts[j])
                if montant:
                    data["irpp"] = float(montant.group().replace(",", "."))
                    break

    return data


def _parse_cin(blocks: list) -> dict:
    full_text = " ".join([b["text"] for b in blocks])
    data = {
        "type_document": "cin",
        "cin": None,
        "nom": None,
        "prenom": None,
        "date_naissance": None,
        "adresse": None,
        "confidence_moyenne": round(
            sum(b["confidence"] for b in blocks) / len(blocks), 3
        ) if blocks else 0,
    }

    for b in blocks:
        t = b["text"]
        cin_match = re.search(r"\b(\d{8})\b", t)
        if cin_match and not data["cin"]:
            data["cin"] = cin_match.group(1)
        if re.search(r"CIN\s*:", t, re.IGNORECASE):
            cin_match2 = re.search(r"\d{8}", t)
            if cin_match2:
                data["cin"] = cin_match2.group()
        if re.search(r"الاسم|NOM", t, re.IGNORECASE):
            parts = re.split(r"[:：]", t)
            if len(parts) > 1:
                data["nom"] = parts[-1].strip()
        if re.search(r"اللقب|PRENOM", t, re.IGNORECASE):
            parts = re.split(r"[:：]", t)
            if len(parts) > 1:
                data["prenom"] = parts[-1].strip()
        date_match = re.search(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", t)
        if date_match and not data["date_naissance"]:
            data["date_naissance"] = date_match.group()
        if re.search(r"مكان|ADRESSE|Ville", t, re.IGNORECASE):
            parts = re.split(r"[:：]", t)
            if len(parts) > 1:
                data["adresse"] = parts[-1].strip()

    return data


def _parse_statement(blocks: list) -> dict:
    texts = [b["text"] for b in blocks]
    data = {
        "type_document": "releve_bancaire",
        "titulaire": None,
        "cin": None,
        "adresse": None,
        "periode": None,
        "solde_final": None,
        "nb_transactions": 0,
        "total_credits": 0.0,
        "total_debits": 0.0,
        "confidence_moyenne": round(
            sum(b["confidence"] for b in blocks) / len(blocks), 3
        ) if blocks else 0,
    }

    total_credits = 0.0
    total_debits = 0.0
    transactions_count = 0

    for i, t in enumerate(texts):
        next_val = texts[i+1].strip() if i+1 < len(texts) else ""

        # Titulaire
        if re.search(r"^Titulaire$", t, re.IGNORECASE):
            data["titulaire"] = next_val

        # CIN
        if re.search(r"^CIN$", t, re.IGNORECASE):
            cin_match = re.search(r"\d{8}", next_val)
            if cin_match:
                data["cin"] = cin_match.group()
        cin_match2 = re.search(r"\b(\d{8})\b", t)
        if cin_match2 and not data["cin"]:
            data["cin"] = cin_match2.group(1)

        # Adresse
        if re.search(r"^Adresse$", t, re.IGNORECASE):
            data["adresse"] = next_val

        # Periode
        if re.search(r"^Periode$", t, re.IGNORECASE):
            data["periode"] = next_val

        # Solde final
        if re.search(r"Solde final", t, re.IGNORECASE):
            for j in range(i, min(i+3, len(texts))):
                montant = re.search(r"-?\d+[\.,]\d+", texts[j])
                if montant:
                    data["solde_final"] = float(montant.group().replace(",", "."))
                    break

        # Transactions (montants isolés)
        montant_match = re.search(r"^-?\d+[\.,]\d{2}$", t.strip())
        if montant_match:
            val = float(t.strip().replace(",", "."))
            if val > 0:
                total_credits += val
                transactions_count += 1
            elif val < 0:
                total_debits += abs(val)

    data["nb_transactions"] = transactions_count
    data["total_credits"] = round(total_credits, 2)
    data["total_debits"] = round(total_debits, 2)
    return data


def detect_document_type(blocks: list) -> str:
    full_text = " ".join([b["text"] for b in blocks]).lower()
    if any(k in full_text for k in ["releve de compte", "releve", "titulaire", "3 derniers mois"]):
        return "releve_bancaire"
    if any(k in full_text for k in ["bulletin de paie", "salaire", "net a payer", "cnss"]):
        return "fiche_de_paie"
    if any(k in full_text for k in ["cin :", "carte nationale", "idtun", "mrz"]):
        return "cin"
    return "inconnu"


def process_document(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        return {"error": f"Fichier introuvable : {file_path}"}

    # Conversion en image
    if path.suffix.lower() == ".pdf":
        images = _pdf_to_images(str(path))
        image_array = _image_to_array(images[0])
    else:
        img = Image.open(path).convert("RGB")
        image_array = _image_to_array(img)

    # Extraction OCR
    blocks = _extract_text_blocks(image_array)

    if not blocks:
        return {"error": "Aucun texte detecte", "confidence_moyenne": 0}

    # Detection type + parsing
    doc_type = detect_document_type(blocks)

    if doc_type == "fiche_de_paie":
        result = _parse_payslip(blocks)
    elif doc_type == "cin":
        result = _parse_cin(blocks)
    elif doc_type == "releve_bancaire":
        result = _parse_statement(blocks)
    else:
        result = {
            "type_document": "inconnu",
            "texte_brut": " ".join([b["text"] for b in blocks])[:500],
            "confidence_moyenne": round(
                sum(b["confidence"] for b in blocks) / len(blocks), 3
            ),
        }

    result["fichier_source"] = str(path.name)
    result["nb_blocs_ocr"] = len(blocks)

    # Alerte si confiance faible
    if result.get("confidence_moyenne", 1) < 0.80:
        result["alerte_hitl"] = True
        result["message_hitl"] = "Confiance OCR faible - verification humaine requise"
    else:
        result["alerte_hitl"] = False

    return result


if __name__ == "__main__":
    import sys
    import os

    # Test sur les 3 types de documents
    test_files = [
        ("output/payslips", "fiche de paie"),
        ("output/cin", "CIN recto"),
        ("output/statements", "releve bancaire"),
    ]

    for folder, label in test_files:
        folder_path = Path(folder)
        if not folder_path.exists():
            print(f"Dossier introuvable : {folder}")
            continue
        files = list(folder_path.iterdir())
        if not files:
            continue
        test_file = files[0]
        print(f"\n--- Test {label} : {test_file.name} ---")
        result = process_document(str(test_file))

        # Debug texte brut OCR
        if test_file.suffix.lower() == ".pdf":
            from pdf2image import convert_from_path
            imgs = convert_from_path(str(test_file), dpi=200, poppler_path=POPPLER_PATH)
            arr = np.array(imgs[0])
            blocks_debug = reader_fr.readtext(arr)
            print("=== TEXTE BRUT OCR (10 premiers blocs) ===")
            for b in blocks_debug[:10]:
                print(f"  '{b[1]}' (conf: {round(b[2],2)})")
            print("==========================================")

        print(json.dumps(result, ensure_ascii=False, indent=2))
