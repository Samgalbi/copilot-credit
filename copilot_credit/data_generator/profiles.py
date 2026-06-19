# -*- coding: utf-8 -*-
"""
Generation de profils clients synthetiques pour credits a la consommation.
Banque Attijari Tunisie - Copilot Credit
"""

import json
import random
from pathlib import Path
from faker import Faker

faker = Faker("fr_FR")

VILLES = [
    "Tunis", "Sfax", "Sousse", "Monastir", "Bizerte", "Nabeul",
    "Gabes", "Kairouan", "Gafsa", "Medenine", "Mahdia", "Beja",
]

NOMS = [
    "Ben Ali", "Trabelsi", "Gharbi", "Mansouri", "Hadj Ahmed",
    "Ben Salah", "Mzali", "Jaziri", "Kefi", "Bouazizi",
    "Chaari", "Jammeli", "Dakhlaoui", "Ben Amor", "Ltaief",
    "Fakhfakh", "Chemli", "Slimi", "Riahi", "Jallouli",
    "Makni", "Barhoumi", "Nasri", "Zammouri", "Bennour",
]

PRENOMS = [
    "Mohamed", "Ahmed", "Sami", "Karim", "Houssem",
    "Nour", "Amine", "Mehdi", "Walid", "Youssef",
    "Amel", "Nadia", "Samia", "Leila", "Ines",
    "Sarra", "Mouna", "Henda", "Rym", "Salma",
]

EMPLOYEURS = [
    "STEG", "Tunisie Telecom", "Banque Centrale de Tunisie",
    "Societe Generale Tunisie", "BIAT", "ATB",
    "Groupe Chimique Tunisien", "Poulina Group Holding",
    "Tunisair", "SOMOCER", "SFBT", "Carthage Cement",
    "COFAT", "Vermeg", "Sage Tunisie",
]

POSTES = [
    "Ingenieur", "Technicien superieur", "Comptable",
    "Commercial", "Responsable RH", "Chef de projet",
    "Analyste financier", "Agent de maitrise", "Cadre superieur",
    "Directeur commercial", "Assistant administratif",
]

MOTIFS = [
    "Achat vehicule", "Achat electromenager", "Voyage",
    "Mariage", "Frais medicaux", "Financement etudes",
    "Amenagement logement", "Projet personnel",
]

DUREES_MOIS = [6, 12, 18, 24, 36, 48, 60, 72, 84]

TAUX_ANNUEL = 0.095


def _generer_cin():
    return f"{random.randint(0, 99999999):08d}"


def _generer_telephone():
    indicatifs = ["20", "22", "23", "24", "25", "50", "52", "54", "55", "56", "58"]
    return f"+216 {random.choice(indicatifs)} {random.randint(100,999)} {random.randint(100,999)}"


def _generer_email(nom, prenom):
    nom_clean = nom.lower().replace(" ", "").replace("'", "")
    prenom_clean = prenom.lower().replace(" ", "")
    return f"{prenom_clean}.{nom_clean}@email.com"


def _calculer_mensualite(montant, duree_mois):
    taux_mensuel = TAUX_ANNUEL / 12
    mensualite = (montant * taux_mensuel) / (1 - (1 + taux_mensuel) ** (-duree_mois))
    return round(mensualite, 2)


def _calculer_label(salaire_net, incidents_bancaires, nb_credits_en_cours, mensualite):
    """
    Regles metier credit conso Attijari avec bruit realiste :
    - REFUSE si salaire_net < 800 DT
    - REFUSE si incidents ET nb_credits >= 2
    - REFUSE si mensualite > 33% salaire_net
    - APPROUVE sinon
    - 8% de cas exceptionnels (decision manuelle banquier qui deroge a la regle)
    """
    # Decision de base selon les regles
    if salaire_net < 800:
        decision_base = "refuse"
    elif incidents_bancaires == 1 and nb_credits_en_cours >= 2:
        decision_base = "refuse"
    elif mensualite > salaire_net * 0.33:
        decision_base = "refuse"
    else:
        decision_base = "approuve"

    # Bruit realiste : 8% de cas ou le banquier deroge a la regle
    # (garanties supplementaires, historique relationnel, etc.)
    if random.random() < 0.08:
        decision_base = "refuse" if decision_base == "approuve" else "approuve"

    return decision_base


def generer_un_profil():
    nom = random.choice(NOMS)
    prenom = random.choice(PRENOMS)
    salaire_brut = round(random.uniform(800, 6000), 2)
    salaire_net = round(salaire_brut * 0.78, 2)
    montant_demande = random.randint(1000, 30000)
    duree_mois = random.choice(DUREES_MOIS)
    mensualite = _calculer_mensualite(montant_demande, duree_mois)
    nb_credits = random.randint(0, 3)
    incidents = random.choices([0, 1], weights=[0.8, 0.2])[0]

    return {
        "cin": _generer_cin(),
        "nom": nom,
        "prenom": prenom,
        "date_naissance": faker.date_of_birth(minimum_age=21, maximum_age=65).isoformat(),
        "adresse": random.choice(VILLES),
        "telephone": _generer_telephone(),
        "email": _generer_email(nom, prenom),
        "employeur": random.choice(EMPLOYEURS),
        "poste": random.choice(POSTES),
        "anciennete_annees": random.randint(1, 25),
        "salaire_brut": salaire_brut,
        "salaire_net": salaire_net,
        "solde_moyen_3mois": round(random.uniform(-200, 8000), 2),
        "nb_credits_en_cours": nb_credits,
        "incidents_bancaires": incidents,
        "montant_demande": montant_demande,
        "duree_mois": duree_mois,
        "taux_interet": TAUX_ANNUEL,
        "mensualite_calculee": mensualite,
        "motif": random.choice(MOTIFS),
        "label": _calculer_label(salaire_net, incidents, nb_credits, mensualite),
    }


def generate_profiles(n=50):
    return [generer_un_profil() for _ in range(n)]


def save_profiles(profiles, path="output/profiles.json"):
    chemin = Path(path)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    print(f"{len(profiles)} profils sauvegardes dans {chemin}")


if __name__ == "__main__":
    profils = generate_profiles(250)
    save_profiles(profils)
    approuves = sum(1 for p in profils if p["label"] == "approuve")
    refuses = sum(1 for p in profils if p["label"] == "refuse")
    print(f"Approuves : {approuves} | Refuses : {refuses}")
