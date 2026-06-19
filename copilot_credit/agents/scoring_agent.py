import json
import os
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score, classification_report,
                              confusion_matrix)
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import shap
import joblib
import warnings
warnings.filterwarnings('ignore')


FEATURES = [
    "salaire_brut", "salaire_net", "anciennete_annees",
    "solde_moyen_3mois", "nb_credits_en_cours",
    "incidents_bancaires", "montant_demande", "duree_mois",
    "mensualite_calculee", "taux_interet",
    "ratio_net_brut", "taux_endettement",
    "capacite_disponible", "ratio_montant_salaire",
]

MODEL_PATH = "output/scoring_model.pkl"
EXPLAINER_PATH = "output/shap_explainer.pkl"


def _build_features(profile: dict) -> dict:
    salaire_brut = float(profile.get("salaire_brut", 0))
    salaire_net  = float(profile.get("salaire_net", 0))
    montant      = float(profile.get("montant_demande", 0))
    duree        = int(profile.get("duree_mois", 36))
    mensualite   = float(profile.get("mensualite_calculee", 0))
    nb_credits   = int(profile.get("nb_credits_en_cours", 0))

    ratio_net_brut = round(salaire_net / salaire_brut, 4) \
        if salaire_brut > 0 else 0
    charges_actuelles = nb_credits * salaire_net * 0.15
    capacite_max = salaire_net * 0.33
    capacite_disponible = capacite_max - charges_actuelles
    taux_endettement = round(
        (charges_actuelles + mensualite) / salaire_net, 4
    ) if salaire_net > 0 else 999
    ratio_montant_salaire = round(
        montant / salaire_net, 4
    ) if salaire_net > 0 else 999

    return {
        "salaire_brut":          salaire_brut,
        "salaire_net":           salaire_net,
        "anciennete_annees":     float(profile.get("anciennete_annees", 0)),
        "solde_moyen_3mois":     float(profile.get("solde_moyen_3mois", 0)),
        "nb_credits_en_cours":   float(nb_credits),
        "incidents_bancaires":   float(profile.get("incidents_bancaires", 0)),
        "montant_demande":       float(montant),
        "duree_mois":            float(duree),
        "mensualite_calculee":   float(mensualite),
        "taux_interet":          float(profile.get("taux_interet", 0.095)),
        "ratio_net_brut":        ratio_net_brut,
        "taux_endettement":      taux_endettement,
        "capacite_disponible":   round(capacite_disponible, 2),
        "ratio_montant_salaire": ratio_montant_salaire,
    }


def train_model(profiles_path: str = "output/profiles.json") -> dict:
    with open(profiles_path, "r", encoding="utf-8") as f:
        profiles = json.load(f)

    print(f"Entrainement sur {len(profiles)} profils...")

    rows = []
    labels = []
    for p in profiles:
        feats = _build_features(p)
        rows.append(feats)
        labels.append(1 if p["label"] == "approuve" else 0)

    df = pd.DataFrame(rows, columns=FEATURES)
    y  = np.array(labels)

    print(f"Distribution : {sum(y)} approuves / "
          f"{len(y)-sum(y)} refuses")

    X_train, X_test, y_train, y_test = train_test_split(
        df, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    # Evaluation
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)

    print(f"\nResultats sur test set :")
    print(f"AUC  : {round(auc, 4)}")
    print(f"Rapport :\n{classification_report(y_test, y_pred)}")

    # SHAP explainer
    explainer = shap.TreeExplainer(model)

    # Sauvegarder
    Path("output").mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(explainer, EXPLAINER_PATH)
    print(f"\nModele sauvegarde : {MODEL_PATH}")

    return {
        "auc": round(auc, 4),
        "nb_profiles": len(profiles),
        "model_path": MODEL_PATH,
    }


def score_dossier(profile: dict,
                  ocr_results: dict = None) -> dict:
    if not Path(MODEL_PATH).exists():
        print("Modele non trouve, entrainement...")
        train_model()

    model    = joblib.load(MODEL_PATH)
    explainer = joblib.load(EXPLAINER_PATH)

    # Si OCR a extrait le salaire, on l'utilise
    if ocr_results:
        paie = ocr_results.get("fiche_de_paie", {})
        if paie.get("salaire_net"):
            profile = dict(profile)
            profile["salaire_net"] = paie["salaire_net"]
        if paie.get("salaire_brut"):
            profile = dict(profile)
            profile["salaire_brut"] = paie["salaire_brut"]

    feats = _build_features(profile)
    df    = pd.DataFrame([feats], columns=FEATURES)

    # Score
    proba      = model.predict_proba(df)[0][1]
    prediction = model.predict(df)[0]

    # SHAP
    shap_vals = explainer.shap_values(df)
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]
    shap_arr = shap_vals[0]

    # Top 5 features les plus influentes
    indices  = np.argsort(np.abs(shap_arr))[::-1][:5]
    top_shap = []
    for i in indices:
        feat_name = FEATURES[i]
        val       = round(float(feats[feat_name]), 3)
        shap_val  = round(float(shap_arr[i]), 4)
        direction = "favorable" if shap_val > 0 else "defavorable"
        top_shap.append({
            "feature":   feat_name,
            "valeur":    val,
            "shap":      shap_val,
            "impact":    direction,
        })

    # Seuils de decision
    if proba >= 0.70:
        decision = "VERT"
        recommandation = "Score favorable - approbation recommandee"
    elif proba >= 0.50:
        decision = "ORANGE"
        recommandation = "Score limite - verification humaine requise"
    else:
        decision = "ROUGE"
        recommandation = "Score defavorable - refus recommande"

    return {
        "score":           round(float(proba), 4),
        "decision":        decision,
        "recommandation":  recommandation,
        "hitl_requis":     decision == "ORANGE",
        "top_shap":        top_shap,
        "label_reel":      profile.get("label", "inconnu"),
    }


if __name__ == "__main__":
    import sys
    sys.path.append(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    # 1. Entrainer le modele
    print("=" * 55)
    print("ENTRAINEMENT DU MODELE XGBoost")
    print("=" * 55)
    result = train_model()
    print(f"\nAUC final : {result['auc']}")

    # 2. Tester sur quelques profils
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)

    approuves = [p for p in profiles if p["label"] == "approuve"]
    refuses   = [p for p in profiles if p["label"] == "refuse"]

    print("\n" + "=" * 55)
    print("TEST DE SCORING")
    print("=" * 55)

    for label, sample in [("APPROUVE", approuves[0]),
                           ("REFUSE",   refuses[0])]:
        result = score_dossier(sample)
        print(f"\nDossier {label} : "
              f"{sample['prenom']} {sample['nom']}")
        print(f"  Score     : {result['score']}")
        print(f"  Decision  : {result['decision']}")
        print(f"  HITL      : {result['hitl_requis']}")
        print(f"  Conseil   : {result['recommandation']}")
        print(f"  Top SHAP  :")
        for s in result["top_shap"]:
            print(f"    - {s['feature']:30s} "
                  f"{s['shap']:+.4f}  ({s['impact']})")