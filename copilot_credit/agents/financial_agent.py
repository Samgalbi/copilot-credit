import json
from pathlib import Path


def _calculer_mensualite(montant: float, duree_mois: int,
                          taux_annuel: float = 0.095) -> float:
    taux_mensuel = taux_annuel / 12
    mensualite = (montant * taux_mensuel) / (
        1 - (1 + taux_mensuel) ** (-duree_mois)
    )
    return round(mensualite, 2)


def _detecter_signaux_negatifs(transactions: dict) -> list:
    signaux = []
    total_credits = transactions.get("total_credits", 0)
    total_debits  = transactions.get("total_debits", 0)
    nb_trans      = transactions.get("nb_transactions", 0)

    if total_debits > total_credits * 0.9:
        signaux.append("Debits tres proches des credits sur 3 mois")

    if nb_trans > 0 and total_debits / max(nb_trans, 1) > 500:
        signaux.append("Montant moyen des debits eleve")

    solde = transactions.get("solde_final")
    if solde is not None and solde < 0:
        signaux.append(f"Solde final negatif : {solde} DT")

    if solde is not None and solde < 200:
        signaux.append("Solde final tres faible (< 200 DT)")

    return signaux


def _evaluer_stabilite_emploi(anciennete: int) -> dict:
    if anciennete >= 5:
        return {"niveau": "STABLE",
                "score": 1.0,
                "message": f"Anciennete solide : {anciennete} ans"}
    elif anciennete >= 2:
        return {"niveau": "MOYEN",
                "score": 0.6,
                "message": f"Anciennete acceptable : {anciennete} ans"}
    else:
        return {"niveau": "FAIBLE",
                "score": 0.3,
                "message": f"Anciennete faible : {anciennete} ans"}


def _calculer_taux_endettement(mensualites_actuelles: float,
                                salaire_net: float) -> dict:
    if salaire_net <= 0:
        return {"taux": None,
                "valide": False,
                "message": "Salaire net nul ou negatif"}
    taux = round(mensualites_actuelles / salaire_net, 3)
    return {
        "taux": taux,
        "taux_pct": f"{round(taux*100, 1)}%",
        "valide": taux < 0.33,
        "message": (
            f"Taux endettement actuel {round(taux*100,1)}% "
            f"({'OK' if taux < 0.33 else 'DEPASSE'} seuil BCT 33%)"
        )
    }


def analyze_finances(ocr_results: dict, profile: dict = None) -> dict:
    payslip = ocr_results.get("fiche_de_paie", {})
    releve  = ocr_results.get("releve_bancaire", {})

    rapport = {
        "statut": "VALIDE",
        "alertes": [],
        "revenus": {},
        "charges": {},
        "capacite_remboursement": {},
        "stabilite_emploi": {},
        "signaux_negatifs": [],
        "recommandation": "",
        "hitl_requis": False,
    }

    # ── REVENUS ───────────────────────────────────────────────────────
    salaire_brut = None
    salaire_net  = None

    # Depuis OCR fiche de paie
    if payslip.get("salaire_brut"):
        salaire_brut = float(payslip["salaire_brut"])
    if payslip.get("salaire_net"):
        salaire_net = float(payslip["salaire_net"])

    # Fallback depuis profil JSON si OCR a rate
    if profile:
        if not salaire_brut and profile.get("salaire_brut"):
            salaire_brut = float(profile["salaire_brut"])
        if not salaire_net and profile.get("salaire_net"):
            salaire_net = float(profile["salaire_net"])

    # Verification coherence brut/net
    if salaire_brut and salaire_net:
        ratio = salaire_net / salaire_brut
        coherent = 0.70 <= ratio <= 0.85
        rapport["revenus"] = {
            "salaire_brut": salaire_brut,
            "salaire_net": salaire_net,
            "ratio_net_brut": round(ratio, 3),
            "coherence_ok": coherent,
        }
        if not coherent:
            rapport["alertes"].append(
                f"Ratio net/brut anormal : {round(ratio*100,1)}% "
                f"(attendu 70-85%)"
            )
    elif salaire_net:
        rapport["revenus"] = {
            "salaire_brut": salaire_brut,
            "salaire_net": salaire_net,
        }
    else:
        rapport["alertes"].append(
            "Salaire net non extrait - verification humaine requise"
        )
        rapport["hitl_requis"] = True

    # ── CHARGES ───────────────────────────────────────────────────────
    nb_credits    = profile.get("nb_credits_en_cours", 0) if profile else 0
    mensualite_moy_credit = (salaire_net * 0.15) if salaire_net else 0
    charges_actuelles = round(nb_credits * mensualite_moy_credit, 2)

    rapport["charges"] = {
        "nb_credits_en_cours": nb_credits,
        "estimation_charges_mensuelles": charges_actuelles,
        "incidents_bancaires": (
            profile.get("incidents_bancaires", 0) if profile else 0
        ),
    }

    if profile and profile.get("incidents_bancaires") == 1:
        rapport["alertes"].append(
            "Incident bancaire detecte sur le profil"
        )

    # ── TAUX ENDETTEMENT ACTUEL ───────────────────────────────────────
    taux_end = _calculer_taux_endettement(
        charges_actuelles, salaire_net or 0
    )
    rapport["charges"]["taux_endettement_actuel"] = taux_end

    # ── CAPACITE DE REMBOURSEMENT ─────────────────────────────────────
    if salaire_net:
        capacite_max = round(salaire_net * 0.33, 2)
        capacite_disponible = round(
            capacite_max - charges_actuelles, 2
        )

        # Calculer mensualite de la demande
        montant_demande = profile.get("montant_demande", 0) if profile else 0
        duree_mois      = profile.get("duree_mois", 36) if profile else 36
        mensualite_demandee = _calculer_mensualite(
            montant_demande, duree_mois
        ) if montant_demande else 0

        faisable = mensualite_demandee <= capacite_disponible

        rapport["capacite_remboursement"] = {
            "salaire_net": salaire_net,
            "capacite_max_33pct": capacite_max,
            "charges_actuelles": charges_actuelles,
            "capacite_disponible": capacite_disponible,
            "montant_demande": montant_demande,
            "duree_mois": duree_mois,
            "mensualite_demandee": mensualite_demandee,
            "faisable": faisable,
            "message": (
                f"Mensualite {mensualite_demandee} DT "
                f"{'<= OK' if faisable else '> DEPASSE'} "
                f"capacite disponible {capacite_disponible} DT"
            )
        }

        if not faisable:
            rapport["alertes"].append(
                f"Capacite insuffisante : mensualite "
                f"{mensualite_demandee} DT > "
                f"disponible {capacite_disponible} DT"
            )

    # ── STABILITE EMPLOI ──────────────────────────────────────────────
    anciennete = profile.get("anciennete_annees", 0) if profile else 0
    rapport["stabilite_emploi"] = _evaluer_stabilite_emploi(anciennete)

    # ── SIGNAUX NEGATIFS RELEVE ───────────────────────────────────────
    rapport["signaux_negatifs"] = _detecter_signaux_negatifs(releve)
    if rapport["signaux_negatifs"]:
        rapport["alertes"].append(
            f"{len(rapport['signaux_negatifs'])} signal(s) "
            f"negatif(s) sur le releve bancaire"
        )

    # ── STATUT FINAL ──────────────────────────────────────────────────
    nb_alertes = len(rapport["alertes"])

    if nb_alertes == 0:
        rapport["statut"] = "FAVORABLE"
        rapport["recommandation"] = (
            "Profil financier solide - scoring recommande"
        )
        rapport["hitl_requis"] = False
    elif nb_alertes <= 2:
        rapport["statut"] = "ACCEPTABLE"
        rapport["recommandation"] = (
            "Profil acceptable avec reserves - "
            "verification humaine recommandee"
        )
        rapport["hitl_requis"] = True
    else:
        rapport["statut"] = "RISQUE"
        rapport["recommandation"] = (
            "Profil a risque - analyse approfondie requise"
        )
        rapport["hitl_requis"] = True

    return rapport


if __name__ == "__main__":
    import sys
    import os
    sys.path.append(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    from agents.ocr_agent import process_document
    from pathlib import Path

    # Charger profils
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)

    # Tester sur 3 profils : 1 approuve, 1 refuse, 1 aleatoire
    approuves = [p for p in profiles if p["label"] == "approuve"]
    refuses   = [p for p in profiles if p["label"] == "refuse"]

    test_profiles = []
    if approuves: test_profiles.append(approuves[0])
    if refuses:   test_profiles.append(refuses[0])

    for profile in test_profiles:
        cin = profile["cin"]
        print(f"\n{'='*55}")
        print(f"Dossier : {profile['prenom']} {profile['nom']}"
              f" | CIN : {cin} | Label : {profile['label']}")
        print('='*55)

        ocr_results = {}

        paie_file = Path(f"output/payslips/payslip_{cin}.pdf")
        if paie_file.exists():
            res = process_document(str(paie_file))
            ocr_results["fiche_de_paie"] = res
            print(f"OCR Paie  -> salaire_net={res.get('salaire_net')}"
                  f" | conf={res.get('confidence_moyenne')}")

        releve_file = Path(f"output/statements/statement_{cin}.pdf")
        if releve_file.exists():
            res = process_document(str(releve_file))
            ocr_results["releve_bancaire"] = res
            print(f"OCR Releve-> transactions={res.get('nb_transactions')}"
                  f" | conf={res.get('confidence_moyenne')}")

        rapport = analyze_finances(ocr_results, profile)
        print(f"\nStatut    : {rapport['statut']}")
        print(f"HITL      : {rapport['hitl_requis']}")
        print(f"Alertes   : {rapport['alertes']}")
        cap = rapport.get("capacite_remboursement", {})
        print(f"Capacite  : {cap.get('message', 'N/A')}")
        print(f"Conseil   : {rapport['recommandation']}")