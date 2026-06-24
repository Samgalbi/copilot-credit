import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_generator.cin_generator import generate_cin
from data_generator.payslip_generator import generate_payslip
from data_generator.statement_generator import generate_statement
from pathlib import Path

# Nouveau client de test (n'existe pas dans les 250 profils)
nouveau_client = {
    "cin": "99887766",
    "nom": "Bouzid",
    "prenom": "Yassine",
    "date_naissance": "1990-04-15",
    "adresse": "Sousse",
    "telephone": "+216 55 123 456",
    "email": "yassine.bouzid@email.com",
    "employeur": "Tunisie Telecom",
    "poste": "Ingenieur",
    "anciennete_annees": 8,
    "salaire_brut": 3200.00,
    "salaire_net": 2496.00,
    "solde_moyen_3mois": 3500.00,
    "nb_credits_en_cours": 0,
    "incidents_bancaires": 0,
    "montant_demande": 15000,
    "duree_mois": 36,
    "taux_interet": 0.095,
    "mensualite_calculee": 480.50,
    "motif": "Achat vehicule",
}

# Dossier de sortie separe pour les tests
output_dir = "output/test_client"
Path(output_dir).mkdir(parents=True, exist_ok=True)

print(f"Generation du dossier test pour : "
      f"{nouveau_client['prenom']} {nouveau_client['nom']}")
print(f"CIN : {nouveau_client['cin']}")
print()

# Generer les 3 documents
cin_paths = generate_cin(nouveau_client, output_dir)
print(f"CIN recto : {cin_paths['recto']}")
print(f"CIN verso : {cin_paths['verso']}")

paie_path = generate_payslip(nouveau_client, output_dir)
print(f"Fiche paie : {paie_path}")

releve_path = generate_statement(nouveau_client, output_dir)
print(f"Releve    : {releve_path}")

print()
print("Dossier de test genere dans output/test_client/")
print("Tu peux maintenant uploader ces 3 fichiers dans le dashboard.")