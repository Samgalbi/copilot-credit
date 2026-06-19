from typing import TypedDict, Optional, Any
from typing_extensions import NotRequired


class DossierState(TypedDict):
    # Identifiants
    cin: str
    profile: dict

    # Resultats OCR par document
    ocr_cin: NotRequired[Optional[dict]]
    ocr_paie: NotRequired[Optional[dict]]
    ocr_releve: NotRequired[Optional[dict]]

    # Rapports des agents
    identity_report: NotRequired[Optional[dict]]
    financial_report: NotRequired[Optional[dict]]
    scoring_report: NotRequired[Optional[dict]]
    memo_result: NotRequired[Optional[dict]]

    # Controle de flux
    statut_pipeline: NotRequired[str]
    hitl_requis: NotRequired[bool]
    hitl_raison: NotRequired[Optional[str]]
    erreurs: NotRequired[list]

    # Decision finale
    decision_finale: NotRequired[Optional[str]]
    validee_par_humain: NotRequired[bool]


def init_state(cin: str, profile: dict) -> DossierState:
    return {
        "cin": cin,
        "profile": profile,
        "ocr_cin": None,
        "ocr_paie": None,
        "ocr_releve": None,
        "identity_report": None,
        "financial_report": None,
        "scoring_report": None,
        "memo_result": None,
        "statut_pipeline": "INITIALISE",
        "hitl_requis": False,
        "hitl_raison": None,
        "erreurs": [],
        "decision_finale": None,
        "validee_par_humain": False,
    }
