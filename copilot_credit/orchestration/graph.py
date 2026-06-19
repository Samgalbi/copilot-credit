import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from langgraph.graph import StateGraph, END

from orchestration.state import DossierState, init_state
from agents.ocr_agent import process_document
from agents.identity_agent import verify_identity
from agents.financial_agent import analyze_finances
from agents.scoring_agent import score_dossier
from agents.memo_agent import generate_memo, save_memo_pdf


# ── NOEUDS DU GRAPHE ───────────────────────────────────────────────────────

def node_ocr(state: DossierState) -> DossierState:
    """Extrait les donnees des 3 documents via OCR."""
    cin = state["cin"]
    erreurs = list(state.get("erreurs", []))

    cin_file = Path(f"output/cin/cin_recto_{cin}.png")
    if cin_file.exists():
        state["ocr_cin"] = process_document(str(cin_file))
    else:
        erreurs.append(f"CIN introuvable : {cin_file}")

    paie_file = Path(f"output/payslips/payslip_{cin}.pdf")
    if paie_file.exists():
        state["ocr_paie"] = process_document(str(paie_file))
    else:
        erreurs.append(f"Fiche de paie introuvable : {paie_file}")

    releve_file = Path(f"output/statements/statement_{cin}.pdf")
    if releve_file.exists():
        state["ocr_releve"] = process_document(str(releve_file))
    else:
        erreurs.append(f"Releve introuvable : {releve_file}")

    state["erreurs"] = erreurs
    state["statut_pipeline"] = "OCR_TERMINE"
    return state


def node_identity(state: DossierState) -> DossierState:
    """Verifie l'identite du client."""
    ocr_results = {
        "cin": state.get("ocr_cin") or {},
        "fiche_de_paie": state.get("ocr_paie") or {},
        "releve_bancaire": state.get("ocr_releve") or {},
    }
    rapport = verify_identity(ocr_results)
    state["identity_report"] = rapport
    state["statut_pipeline"] = "IDENTITE_VERIFIEE"

    if rapport.get("hitl_requis"):
        state["hitl_requis"] = True
        state["hitl_raison"] = (
            state.get("hitl_raison") or "Identite : " + rapport.get("recommandation", "")
        )
    return state


def node_financial(state: DossierState) -> DossierState:
    """Analyse la situation financiere du client."""
    ocr_results = {
        "fiche_de_paie": state.get("ocr_paie") or {},
        "releve_bancaire": state.get("ocr_releve") or {},
    }
    rapport = analyze_finances(ocr_results, state.get("profile"))
    state["financial_report"] = rapport
    state["statut_pipeline"] = "ANALYSE_FINANCIERE_TERMINEE"

    if rapport.get("hitl_requis"):
        state["hitl_requis"] = True
        if not state.get("hitl_raison"):
            state["hitl_raison"] = "Finance : " + rapport.get("recommandation", "")
    return state


def node_scoring(state: DossierState) -> DossierState:
    """Calcule le score ML de credit."""
    ocr_results = {
        "fiche_de_paie": state.get("ocr_paie") or {},
    }
    rapport = score_dossier(state.get("profile"), ocr_results)
    state["scoring_report"] = rapport
    state["statut_pipeline"] = "SCORING_TERMINE"

    if rapport.get("hitl_requis"):
        state["hitl_requis"] = True
        if not state.get("hitl_raison"):
            state["hitl_raison"] = "Scoring : zone orange - verification requise"
    return state


def node_memo(state: DossierState) -> DossierState:
    """Genere le memo de credit final."""
    profile = state.get("profile")
    identity_report = state.get("identity_report", {})
    financial_report = state.get("financial_report", {})
    scoring_report = state.get("scoring_report", {})

    memo_result = generate_memo(
        profile, identity_report, financial_report, scoring_report
    )
    state["memo_result"] = memo_result
    state["statut_pipeline"] = "MEMO_GENERE"

    if not memo_result.get("erreur"):
        try:
            pdf_path = save_memo_pdf(memo_result)
            state["memo_result"]["pdf_path"] = pdf_path
        except Exception as e:
            state["erreurs"] = list(state.get("erreurs", [])) + [
                f"Erreur sauvegarde PDF : {str(e)}"
            ]

    return state


def node_decision(state: DossierState) -> DossierState:
    """Noeud final : prepare la decision avant validation humaine."""
    scoring = state.get("scoring_report", {})
    decision_algo = scoring.get("decision", "INCONNU")

    state["decision_finale"] = decision_algo
    state["statut_pipeline"] = "EN_ATTENTE_VALIDATION_HUMAINE"

    return state


# ── ROUTING CONDITIONNEL ───────────────────────────────────────────────────

def route_apres_ocr(state: DossierState) -> str:
    """Si trop d'erreurs OCR, on arrete le pipeline."""
    if len(state.get("erreurs", [])) >= 3:
        return "stop"
    return "continue"


# ── CONSTRUCTION DU GRAPHE ─────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(DossierState)

    graph.add_node("ocr", node_ocr)
    graph.add_node("identity", node_identity)
    graph.add_node("financial", node_financial)
    graph.add_node("scoring", node_scoring)
    graph.add_node("memo", node_memo)
    graph.add_node("decision", node_decision)

    graph.set_entry_point("ocr")

    graph.add_conditional_edges(
        "ocr",
        route_apres_ocr,
        {
            "continue": "identity",
            "stop": END,
        }
    )

    graph.add_edge("identity", "financial")
    graph.add_edge("financial", "scoring")
    graph.add_edge("scoring", "memo")
    graph.add_edge("memo", "decision")
    graph.add_edge("decision", END)

    return graph.compile()


def process_dossier(cin: str, profile: dict) -> DossierState:
    """Point d'entree principal : traite un dossier complet."""
    app = build_graph()
    initial_state = init_state(cin, profile)
    final_state = app.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    import json

    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)

    # Test sur 1 dossier approuve et 1 refuse
    approuves = [p for p in profiles if p["label"] == "approuve"]
    refuses = [p for p in profiles if p["label"] == "refuse"]

    for label, sample in [("APPROUVE", approuves[0]), ("REFUSE", refuses[0])]:
        print("\n" + "=" * 60)
        print(f"TRAITEMENT DOSSIER {label} : "
              f"{sample['prenom']} {sample['nom']} (CIN {sample['cin']})")
        print("=" * 60)

        result = process_dossier(sample["cin"], sample)

        print(f"\nStatut pipeline   : {result['statut_pipeline']}")
        print(f"HITL requis       : {result['hitl_requis']}")
        print(f"Raison HITL       : {result.get('hitl_raison')}")
        print(f"Decision finale   : {result['decision_finale']}")
        print(f"Erreurs           : {result.get('erreurs')}")

        if result.get("memo_result", {}).get("pdf_path"):
            print(f"Memo PDF          : {result['memo_result']['pdf_path']}")