import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from orchestration.graph import process_dossier
from orchestration.upload_pipeline import process_upload

app = FastAPI(title="Copilot Credit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir le frontend statique
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
ASSETS_DIR = Path(__file__).parent.parent / "assets"


@app.get("/")
def home():
    index = FRONTEND_DIR / "index.html"
    return FileResponse(str(index))


@app.get("/logo")
def logo():
    logo_path = ASSETS_DIR / "logo_attijari.png"
    if logo_path.exists():
        return FileResponse(str(logo_path))
    return JSONResponse({"error": "logo introuvable"}, status_code=404)


@app.get("/api/stats")
def get_stats():
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    return {
        "total": len(profiles),
        "approuves": sum(1 for p in profiles if p["label"] == "approuve"),
        "refuses": sum(1 for p in profiles if p["label"] == "refuse"),
        "temps_moyen": "~24s",
    }


@app.get("/api/profiles")
def get_profiles():
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    # Retourne une liste simplifiee pour le selecteur
    return [
        {
            "cin": p["cin"],
            "nom": p["nom"],
            "prenom": p["prenom"],
            "montant_demande": p["montant_demande"],
            "duree_mois": p["duree_mois"],
            "salaire_net": p["salaire_net"],
            "motif": p["motif"],
            "label": p["label"],
        }
        for p in profiles
    ]


@app.post("/api/process-demo")
def process_demo(cin: str = Form(...)):
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    profile = next((p for p in profiles if p["cin"] == cin), None)
    if not profile:
        return JSONResponse({"error": "Dossier introuvable"}, status_code=404)

    result = process_dossier(cin, profile)
    return _clean_result(result)


@app.post("/api/process-upload")
async def process_upload_endpoint(
    montant_demande: float = Form(...),
    duree_mois: int = Form(...),
    motif: str = Form(...),
    anciennete_annees: int = Form(...),
    nb_credits_en_cours: int = Form(...),
    incidents_bancaires: int = Form(...),
    cin_file: UploadFile = File(None),
    paie_file: UploadFile = File(None),
    releve_file: UploadFile = File(None),
):
    saisie = {
        "montant_demande": montant_demande,
        "duree_mois": duree_mois,
        "motif": motif,
        "anciennete_annees": anciennete_annees,
        "nb_credits_en_cours": nb_credits_en_cours,
        "incidents_bancaires": incidents_bancaires,
    }

    # Wrapper pour compatibilite avec process_upload
    class FileWrapper:
        def __init__(self, upload_file):
            self.name = upload_file.filename
            self._content = upload_file.file.read()
        def getbuffer(self):
            return self._content

    cin_w = FileWrapper(cin_file) if cin_file and cin_file.filename else None
    paie_w = FileWrapper(paie_file) if paie_file and paie_file.filename else None
    releve_w = FileWrapper(releve_file) if releve_file and releve_file.filename else None

    result = process_upload(cin_w, paie_w, releve_w, saisie)
    return _clean_result(result)


@app.get("/api/memo-pdf/{cin}")
def get_memo_pdf(cin: str):
    pdf_path = Path(f"output/reports/memo_credit_{cin}.pdf")
    if pdf_path.exists():
        return FileResponse(str(pdf_path), media_type="application/pdf",
                            filename=f"memo_credit_{cin}.pdf")
    return JSONResponse({"error": "PDF introuvable"}, status_code=404)


def _clean_result(result: dict) -> dict:
    """Nettoie le resultat pour la serialisation JSON."""
    return {
        "decision_finale": result.get("decision_finale"),
        "hitl_requis": result.get("hitl_requis"),
        "hitl_raison": result.get("hitl_raison"),
        "profile": result.get("profile"),
        "identity_report": result.get("identity_report"),
        "financial_report": result.get("financial_report"),
        "scoring_report": result.get("scoring_report"),
        "memo_result": {
            "memo_text": result.get("memo_result", {}).get("memo_text"),
            "pdf_path": result.get("memo_result", {}).get("pdf_path"),
            "cin": result.get("memo_result", {}).get("cin"),
        } if result.get("memo_result") else None,
        "erreurs": result.get("erreurs", []),
    }