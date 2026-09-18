import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "Scripts"
sys.path.append(str(SCRIPTS_DIR))

from common.db import get_engine



st.set_page_config(
    page_title="Météo & Risques Livraison — Maroc",
    page_icon="🌦️",
    layout="wide",
)


COULEURS_RISQUE = {
    "faible": "#2ecc71",
    "moyen": "#f39c12",
    "élevé": "#e74c3c",
}



@st.cache_data(ttl=600)
def charger_donnees():
    requete = text(
        """
        WITH dernieres_previsions AS (
            SELECT
                p.*,
                ROW_NUMBER() OVER (
                    PARTITION BY p.ville_id, p.date_prevision
                    ORDER BY p.retrieved_at DESC
                ) AS rang
            FROM previsions p
        )
        SELECT
            v.city,
            v.latitude,
            v.longitude,
            dp.date_prevision,
            dp.temperature_max,
            dp.temperature_min,
            dp.precipitation_sum,
            dp.precipitation_probability_max,
            dp.wind_speed_max,
            dp.wind_gusts_max,
            dp.risk_score,
            dp.risk_level
        FROM dernieres_previsions dp
        JOIN villes v ON v.id = dp.ville_id
        WHERE dp.rang = 1
        ORDER BY dp.date_prevision, v.city;
        """
    )

    engine = get_engine()
    df = pd.read_sql(requete, engine)
    return df




def afficher_filtres(df):
    st.sidebar.header("Filtres")

    toutes_les_villes = sorted(df["city"].unique())
    villes_choisies = st.sidebar.multiselect(
        "Ville(s)",
        options=toutes_les_villes,
        default=[],
        help="Laisser vide pour inclure toutes les villes.",
    )

    periode_choisie = st.sidebar.radio(
        "Période",
        options=["Toute la période disponible", "3 prochains jours", "7 prochains jours"],
    )

    toutes_les_dates = sorted(df["date_prevision"].unique())
    dates_choisies = st.sidebar.multiselect(
        "Date(s) précise(s)",
        options=toutes_les_dates,
        default=[],
        help="Laisser vide pour ne pas filtrer sur une date précise.",
    )

    niveaux_choisis = st.sidebar.multiselect(
        "Niveau de risque",
        options=["faible", "moyen", "élevé"],
        default=["faible", "moyen", "élevé"],
    )

    df_filtre = df.copy()

    if villes_choisies:
        df_filtre = df_filtre[df_filtre["city"].isin(villes_choisies)]

    if periode_choisie == "3 prochains jours":
        date_limite = df_filtre["date_prevision"].min() + pd.Timedelta(days=2)
        df_filtre = df_filtre[df_filtre["date_prevision"] <= date_limite]
    elif periode_choisie == "7 prochains jours":
        date_limite = df_filtre["date_prevision"].min() + pd.Timedelta(days=6)
        df_filtre = df_filtre[df_filtre["date_prevision"] <= date_limite]

    if dates_choisies:
        df_filtre = df_filtre[df_filtre["date_prevision"].isin(dates_choisies)]

    if niveaux_choisis:
        df_filtre = df_filtre[df_filtre["risk_level"].isin(niveaux_choisis)]

    return df_filtre



def afficher_kpi(df):
    if df.empty:
        st.warning("Aucune donnée ne correspond aux filtres sélectionnés.")
        return

    nombre_villes = df["city"].nunique()
    temperature_max = df["temperature_max"].max()
    precipitation_max = df["precipitation_sum"].max()
    nombre_periodes_a_risque = (df["risk_level"] == "élevé").sum()


    risque_moyen_par_ville = df.groupby("city")["risk_score"].mean()
    ville_plus_a_risque = risque_moyen_par_ville.idxmax()

    colonne1, colonne2, colonne3, colonne4, colonne5 = st.columns(5)
    colonne1.metric("Nombre de villes", nombre_villes)
    colonne2.metric("Température max", f"{temperature_max:.1f} °C")
    colonne3.metric("Précipitations max", f"{precipitation_max:.1f} mm")
    colonne4.metric("Périodes à risque élevé", int(nombre_periodes_a_risque))
    colonne5.metric("Ville la plus à risque", ville_plus_a_risque)




def afficher_carte(df):
    st.subheader("Carte des risques par ville")

    if df.empty:
        st.info("Pas de données à afficher sur la carte avec ces filtres.")
        return

    df_carte = df.loc[df.groupby("city")["risk_score"].idxmax()]

    figure = px.scatter_map(
        df_carte,
        lat="latitude",
        lon="longitude",
        color="risk_level",
        color_discrete_map=COULEURS_RISQUE,
        size="risk_score",
        hover_name="city",
        hover_data={"risk_score": True, "date_prevision": True, "latitude": False, "longitude": False},
        zoom=4.2,
        height=550,
        category_orders={"risk_level": ["faible", "moyen", "élevé"]},
    )
    figure.update_layout(map_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})

    st.plotly_chart(figure, use_container_width=True)




def afficher_top_villes(df):
    st.subheader("Top 10 des villes les plus à risque (moyenne sur la période filtrée)")

    if df.empty:
        return

    top_villes = (
        df.groupby("city")["risk_score"]
        .mean()
        .round(1)
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )

    figure = px.bar(
        top_villes,
        x="risk_score",
        y="city",
        orientation="h",
        labels={"risk_score": "Risque moyen", "city": "Ville"},
    )
    figure.update_layout(yaxis={"categoryorder": "total ascending"})

    st.plotly_chart(figure, use_container_width=True)



def afficher_tableau(df):
    st.subheader("Détail des prévisions")

    colonnes_a_afficher = [
        "city", "date_prevision", "temperature_max", "temperature_min",
        "precipitation_sum", "wind_gusts_max", "risk_score", "risk_level",
    ]
    df_affichage = df[colonnes_a_afficher].sort_values("risk_score", ascending=False)

    st.dataframe(df_affichage, use_container_width=True, hide_index=True)





def main():
    st.title("🌦️ Météo & Risques Livraison — Maroc")
    st.caption("Où et quand faut-il être particulièrement vigilant dans les prochains jours ?")

    df = charger_donnees()

    if df.empty:
        st.error("Aucune donnée trouvée en base. As-tu déjà lancé load_postgres.py ?")
        return

    df_filtre = afficher_filtres(df)

    afficher_kpi(df_filtre)
    st.divider()
    afficher_carte(df_filtre)
    st.divider()
    afficher_top_villes(df_filtre)
    st.divider()
    afficher_tableau(df_filtre)


if __name__ == "__main__":
    main()