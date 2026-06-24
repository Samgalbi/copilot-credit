import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import streamlit as st
from pathlib import Path
from orchestration.graph import process_dossier
from orchestration.upload_pipeline import process_upload

st.set_page_config(
    page_title="Copilot Credit - Attijari Bank",
    page_icon="🏦",
    layout="wide",
)

# ── STYLE PRO ──────────────────────────────────────────────────────────────
st.markdown('''
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .header-bar {
        background: linear-gradient(90deg, #042C53 0%, #0C447C 100%);
        padding: 18px 28px; border-radius: 12px; margin-bottom: 20px;
        display: flex; align-items: center; justify-content: space-between;
    }
    .header-left { display: flex; align-items: center; gap: 14px; }
    .header-logo {
        width: 44px; height: 44px; border-radius: 10px; background: #F0997B;
        display: flex; align-items: center; justify-content: center;
        font-size: 24px;
    }
    .header-title { color: white; font-size: 20px; font-weight: 600; margin: 0; }
    .header-sub { color: #85B7EB; font-size: 13px; margin: 0; }
    .header-user { color: white; font-size: 13px; text-align: right; }
    .stat-card {
        background: #F8F9FB; border-radius: 10px; padding: 14px 18px;
        border: 1px solid #E8ECF2;
    }
    .stat-label { font-size: 12px; color: #6B7280; }
    .stat-value { font-size: 24px; font-weight: 600; }
    .badge-vert { background:#E1F5EE; color:#0F6E56; padding:6px 16px;
                  border-radius:20px; font-weight:600; font-size:15px; }
    .badge-orange { background:#FAEEDA; color:#854F0B; padding:6px 16px;
                    border-radius:20px; font-weight:600; font-size:15px; }
    .badge-rouge { background:#FAECE7; color:#993C1D; padding:6px 16px;
                   border-radius:20px; font-weight:600; font-size:15px; }
    .hitl-banner { background:#FAEEDA; border-left:4px solid #EF9F27;
                   padding:14px 18px; border-radius:6px; margin:12px 0;
                   color:#633806; }
    .agent-box {
        background: white; border: 1px solid #E8ECF2; border-radius: 10px;
        padding: 16px; text-align: center;
    }
</style>
''', unsafe_allow_html=True)

# ── HEADER ─────────────────────────────────────────────────────────────────
st.markdown('''
<div class="header-bar">
    <div class="header-left">
        <div class="header-logo">🏦</div>
        <div>
            <p class="header-title">Copilot Credit</p>
            <p class="header-sub">Attijari Bank Tunisie — Credit a la consommation</p>
        </div>
    </div>
    <div class="header-user">
        <b>Charge de credit</b><br>S. Galbi
    </div>
</div>
''', unsafe_allow_html=True)

# ── STATS RAPIDES ──────────────────────────────────────────────────────────
@st.cache_data
def load_profiles():
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        return json.load(f)

profiles = load_profiles()
nb_approuves = sum(1 for p in profiles if p["label"] == "approuve")
nb_refuses = sum(1 for p in profiles if p["label"] == "refuse")

s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Dossiers total</div>'
                f'<div class="stat-value" style="color:#0C447C;">{len(profiles)}</div></div>',
                unsafe_allow_html=True)
with s2:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Approuves</div>'
                f'<div class="stat-value" style="color:#0F6E56;">{nb_approuves}</div></div>',
                unsafe_allow_html=True)
with s3:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Refuses</div>'
                f'<div class="stat-value" style="color:#993C1D;">{nb_refuses}</div></div>',
                unsafe_allow_html=True)
with s4:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Temps moyen</div>'
                f'<div class="stat-value" style="color:#854F0B;">~24s</div></div>',
                unsafe_allow_html=True)

st.write("")

# ── FONCTION D'AFFICHAGE DES RESULTATS ─────────────────────────────────────
def afficher_resultats(result):
    decision = result.get("decision_finale", "INCONNU")
    badge_class = {"VERT": "badge-vert", "ORANGE": "badge-orange",
                   "ROUGE": "badge-rouge"}.get(decision, "badge-orange")

    st.markdown(f'### Decision algorithmique : '
                f'<span class="{badge_class}">{decision}</span>',
                unsafe_allow_html=True)

    if result.get("hitl_requis"):
        st.markdown(f'<div class="hitl-banner">⚠️ <b>Validation humaine requise</b><br>'
                    f'{result.get("hitl_raison", "")}</div>', unsafe_allow_html=True)

    # Profil reconstruit (si upload)
    profile = result.get("profile", {})
    if profile.get("source") == "upload":
        with st.expander("📋 Profil reconstruit depuis les documents"):
            st.json({k: v for k, v in profile.items()
                     if k not in ["source"]})

    # 4 agents
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        idr = result.get("identity_report", {})
        st.markdown(f'<div class="agent-box"><b>🪪 Identite</b><br>'
                    f'<span style="font-size:18px;">{idr.get("statut","N/A")}</span><br>'
                    f'<small>Score : {idr.get("score_confiance","N/A")}</small></div>',
                    unsafe_allow_html=True)
    with c2:
        fr = result.get("financial_report", {})
        cap = fr.get("capacite_remboursement", {})
        st.markdown(f'<div class="agent-box"><b>📊 Finance</b><br>'
                    f'<span style="font-size:18px;">{fr.get("statut","N/A")}</span><br>'
                    f'<small>Dispo : {cap.get("capacite_disponible","N/A")} DT</small></div>',
                    unsafe_allow_html=True)
    with c3:
        sc = result.get("scoring_report", {})
        st.markdown(f'<div class="agent-box"><b>🤖 Score ML</b><br>'
                    f'<span style="font-size:18px;">{sc.get("score","N/A")}</span><br>'
                    f'<small>{sc.get("decision","N/A")}</small></div>',
                    unsafe_allow_html=True)
    with c4:
        memo = result.get("memo_result", {})
        statut_memo = "Genere" if memo.get("pdf_path") else "Erreur"
        st.markdown(f'<div class="agent-box"><b>📝 Memo</b><br>'
                    f'<span style="font-size:18px;">{statut_memo}</span><br>'
                    f'<small>PDF disponible</small></div>',
                    unsafe_allow_html=True)

    st.write("")

    # SHAP
    sc = result.get("scoring_report", {})
    top_shap = sc.get("top_shap", [])
    if top_shap:
        st.markdown("#### 🔍 Facteurs de decision (SHAP)")
        for s in top_shap:
            icon = "🟢" if s["impact"] == "favorable" else "🔴"
            st.write(f"{icon} **{s['feature']}** : {s['impact']} "
                     f"(impact {s['shap']:+.3f})")

    # Memo
    memo = result.get("memo_result", {})
    if memo.get("memo_text"):
        st.markdown("#### 📄 Memo de credit")
        st.markdown(memo["memo_text"])

    # Validation HITL
    st.write("")
    st.markdown("#### ✅ Validation finale")
    commentaire = st.text_area("Commentaire du charge de credit", key="comment")
    v1, v2, v3 = st.columns(3)
    with v1:
        if st.button("✅ APPROUVER", type="primary", use_container_width=True):
            st.success(f"Dossier APPROUVE. {commentaire or ''}")
    with v2:
        if st.button("⚠️ COMPLEMENT", use_container_width=True):
            st.warning("Demande de complement envoyee.")
    with v3:
        if st.button("❌ REJETER", use_container_width=True):
            st.error(f"Dossier REJETE. {commentaire or ''}")


# ── ONGLETS ────────────────────────────────────────────────────────────────
tab_upload, tab_demo = st.tabs(["📤 Nouveau dossier", "🎬 Mode demo"])

# ─── ONGLET UPLOAD (PRODUCTION) ───
with tab_upload:
    st.markdown("### Deposer les documents du client")

    u1, u2, u3 = st.columns(3)
    with u1:
        cin_file = st.file_uploader("🪪 CIN (recto)", type=["png", "jpg", "jpeg"])
    with u2:
        paie_file = st.file_uploader("📄 Fiche de paie", type=["pdf"])
    with u3:
        releve_file = st.file_uploader("🏦 Releve bancaire", type=["pdf"])

    st.markdown("### Informations complementaires (saisie banquier)")
    f1, f2, f3 = st.columns(3)
    with f1:
        montant = st.number_input("Montant demande (DT)", min_value=1000,
                                   max_value=30000, value=10000, step=500)
        anciennete = st.number_input("Anciennete (annees)", min_value=0,
                                     max_value=40, value=5)
    with f2:
        duree = st.selectbox("Duree (mois)", [6,12,18,24,36,48,60,72,84], index=4)
        nb_credits = st.number_input("Credits en cours", min_value=0,
                                     max_value=10, value=0)
    with f3:
        motif = st.selectbox("Motif", ["Achat vehicule","Achat electromenager",
                "Voyage","Mariage","Frais medicaux","Financement etudes",
                "Amenagement logement","Projet personnel"])
        incidents = st.selectbox("Incident bancaire", ["Non","Oui"])

    if st.button("🚀 Analyser le dossier", type="primary"):
        if not (cin_file or paie_file or releve_file):
            st.error("Veuillez uploader au moins un document.")
        else:
            saisie = {
                "montant_demande": montant,
                "duree_mois": duree,
                "motif": motif,
                "anciennete_annees": anciennete,
                "nb_credits_en_cours": nb_credits,
                "incidents_bancaires": 1 if incidents == "Oui" else 0,
            }
            with st.spinner("Traitement par les agents IA..."):
                result = process_upload(cin_file, paie_file, releve_file, saisie)
            st.session_state["result_upload"] = result

    if "result_upload" in st.session_state:
        st.divider()
        afficher_resultats(st.session_state["result_upload"])

# ─── ONGLET DEMO ───
with tab_demo:
    st.markdown("### Selectionner un dossier de demonstration")
    profiles_dict = {
        f"{p['prenom']} {p['nom']} (CIN {p['cin']}) - {p['motif']}": p
        for p in profiles
    }
    selected_label = st.selectbox("Dossier client", list(profiles_dict.keys()))
    selected_profile = profiles_dict[selected_label]

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Montant", f"{selected_profile['montant_demande']} DT")
    d2.metric("Duree", f"{selected_profile['duree_mois']} mois")
    d3.metric("Salaire net", f"{selected_profile['salaire_net']} DT")
    d4.metric("Label reel", selected_profile['label'])

    if st.button("🚀 Traiter le dossier", type="primary", key="demo_btn"):
        with st.spinner("Traitement par les agents IA..."):
            result = process_dossier(selected_profile["cin"], selected_profile)
        st.session_state["result_demo"] = result

    if "result_demo" in st.session_state:
        st.divider()
        afficher_resultats(st.session_state["result_demo"])