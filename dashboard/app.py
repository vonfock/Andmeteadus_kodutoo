"""
Streamlit dashboard — Estonian Vehicle Roadworthiness Analysis
Run with: streamlit run dashboard/app.py
"""

import sys
import math
from pathlib import Path

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data_loader import (
    get_available_years,
    q_top_mark_and_models,
    q_station_strictness,
    q_inspector_strictness,
    q_oldest_car_per_month,
    q_age_effect,
    q_mark_pass_by_age,
    q_available_marks,
    q_defect_overview,
    q_top_defects,
    q_defects_by_mark_model_year,
    q_defects_summary_by_mark,
    rike_df,
    rike_metadata_df,
    yv_metadata,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tehnoülevaatuste analüüs",
    page_icon="🚗",
    layout="wide",
)

AVAILABLE_YEARS = get_available_years()

MONTH_NAMES = {
    1: "Jaanuar",
    2: "Veebruar",
    3: "Märts",
    4: "Aprill",
    5: "Mai",
    6: "Juuni",
    7: "Juuli",
    8: "August",
    9: "September",
    10: "Oktoober",
    11: "November",
    12: "Detsember",
}

SEVERITY_LABELS = {
    "VO": "Väheoluline (VO)",
    "OV": "Oluline viga (OV)",
    "EOV": "Eriti ohtlik (EOV)",
}
SEVERITY_COLORS = {"VO": "#ffd93d", "OV": "#ff922b", "EOV": "#e03131"}

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🚗 Tehnoülevaatused")
st.sidebar.caption("Eesti sõidukite tehnoülevaatuste andmeanalüüs")

page = st.sidebar.radio(
    "Vali leht",
    [
        "🏆 Populaarseim mark",
        "👤 Inspektorite rangus",
        "🧓 Vanim auto kuus",
        "📈 Vanuse mõju läbimisele",
        "🔧 Rikete analüüs",
        "🔍 Otsi margi järgi",
    ],
)

st.sidebar.divider()
st.sidebar.caption(f"Andmed: {min(AVAILABLE_YEARS)}–{max(AVAILABLE_YEARS)}")
st.sidebar.caption("Allikas: andmed.eesti.ee / Transpordiamet")


def year_selector(key: str, default: list = None) -> list:
    if default is None:
        default = [AVAILABLE_YEARS[-1]]
    selected = st.multiselect(
        "Vali aastad:",
        options=AVAILABLE_YEARS,
        default=default,
        key=key,
    )
    if not selected:
        st.warning("Vali vähemalt üks aasta.")
        st.stop()
    return selected


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Most popular mark
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏆 Populaarseim mark":
    st.title("🏆 Populaarseim automärk tehnoülevaatustel")
    st.write(
        "Kõige sagedamini tehnoülevaatusele tulnud automärk ja selle top 5 mudelit valitud aastatel."
    )

    years = year_selector("mark_years", default=AVAILABLE_YEARS)

    with st.spinner("Pärin andmeid..."):
        mark_df, models_df = q_top_mark_and_models(years)

    if mark_df.empty:
        st.error("Andmeid ei leitud.")
        st.stop()

    fig = px.bar(
        mark_df,
        x="aasta",
        y="arv",
        color="MARK",
        text="MARK",
        title="Populaarseim märk aasta kaupa",
        labels={"aasta": "Aasta", "arv": "Ülevaatuste arv", "MARK": "Märk"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, xaxis=dict(tickmode="linear"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 5 mudelit — populaarseima märgi hulgas")
    for year in sorted(years):
        year_mark = mark_df[mark_df["aasta"] == year]
        if year_mark.empty:
            continue
        winner = year_mark.iloc[0]["MARK"]
        year_models = models_df[models_df["aasta"] == year]
        with st.expander(f"{year} — {winner}"):
            if year_models.empty:
                st.write("Mudelite andmed puuduvad.")
            else:
                fig2 = px.bar(
                    year_models,
                    x="arv",
                    y="MUDEL",
                    orientation="h",
                    labels={"arv": "Arv", "MUDEL": "Mudel"},
                    color="arv",
                    color_continuous_scale="Blues",
                )
                fig2.update_layout(
                    yaxis={"categoryorder": "total ascending"},
                    coloraxis_showscale=False,
                    height=280,
                )
                st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Inspector strictness
# ══════════════════════════════════════════════════════════════════════════════
elif page == "👤 Inspektorite rangus":
    st.title("👤 Inspektorite ja ülevaatuspunktide rangus")
    st.write("Läbimise % = KORRAS / (KORRAS + KORDUVALE) KORRALINE ülevaatustel.")

    years = year_selector("inspector_years", default=AVAILABLE_YEARS)
    tab1, tab2 = st.tabs(["🏢 Ülevaatuspunktid", "🧑 Inspektorid"])

    with tab1:
        st.subheader("Ülevaatuspunktide läbimise määr")
        st.caption("Miinimum 100 ülevaatust punkti kohta.")
        with st.spinner("Pärin punktide andmeid..."):
            station_df = q_station_strictness(years)
        if station_df.empty:
            st.error("Andmeid ei leitud.")
        else:
            mode_s = st.radio(
                "Sorteeri:",
                ["🔴 Rangeimad", "🟢 Leebemad"],
                horizontal=True,
                key="station_mode",
            )
            top_n_s = st.slider("Mitu punkti?", 5, 30, 15, key="station_n")
            if "Rangeimad" in mode_s:
                show = station_df.nsmallest(top_n_s, "labimise_protsent").sort_values(
                    "labimise_protsent"
                )
                title = f"Top {top_n_s} rangemat punkti"
                cscale = "Reds_r"
            else:
                show = station_df.nlargest(top_n_s, "labimise_protsent").sort_values(
                    "labimise_protsent"
                )
                title = f"Top {top_n_s} leebeimat punkti"
                cscale = "Greens"
            fig = px.bar(
                show,
                x="labimise_protsent",
                y="jaam",
                orientation="h",
                color="labimise_protsent",
                color_continuous_scale=cscale,
                hover_data=["jaama_kood", "kokku", "labis_esimesel", "kukkus_esimesel"],
                text="labimise_protsent",
                title=title,
                labels={"labimise_protsent": "Läbimise %", "jaam": "Punkt"},
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            fig.update_layout(
                coloraxis_showscale=False,
                height=max(400, top_n_s * 35),
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("📋 Kõik punktid tabelina"):
                st.dataframe(
                    station_df.rename(
                        columns={
                            "jaam": "Punkt",
                            "jaama_kood": "Kood",
                            "kokku": "Kokku",
                            "labis_esimesel": "Läbis",
                            "kukkus_esimesel": "Kukkus",
                            "labimise_protsent": "Läbimise %",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab2:
        st.subheader("Inspektorite läbimise määr")
        st.caption("Miinimum 50 ülevaatust inspektori kohta. 20 inspektorit lehel.")
        with st.spinner("Pärin inspektorite andmeid..."):
            insp_df = q_inspector_strictness(years)
        if insp_df.empty:
            st.error("Andmeid ei leitud.")
        else:
            mode_i = st.radio(
                "Sorteeri:",
                ["🔴 Rangeimad ees", "🟢 Leebemad ees"],
                horizontal=True,
                key="insp_mode",
            )
            all_stations = sorted(insp_df["jaam"].dropna().unique().tolist())
            sel_station = st.selectbox(
                "Filtreeri punkti järgi:",
                ["Kõik punktid"] + all_stations,
                key="insp_station",
            )
            if sel_station != "Kõik punktid":
                insp_df = insp_df[insp_df["jaam"] == sel_station]

            ascending = "Rangeimad" in mode_i
            insp_sorted = insp_df.sort_values(
                "labimise_protsent", ascending=ascending
            ).reset_index(drop=True)
            PAGE_SIZE = 20
            total_pages = max(1, math.ceil(len(insp_sorted) / PAGE_SIZE))
            _, col_mid, _ = st.columns([1, 2, 1])
            with col_mid:
                current_page = st.number_input(
                    f"Leht (1–{total_pages})",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                    key="insp_page",
                )
            start = (current_page - 1) * PAGE_SIZE
            page_df = insp_sorted.iloc[start : start + PAGE_SIZE]
            cscale = "Reds_r" if ascending else "Greens"
            fig = px.bar(
                page_df.sort_values("labimise_protsent"),
                x="labimise_protsent",
                y="inspektori_kood",
                orientation="h",
                color="labimise_protsent",
                color_continuous_scale=cscale,
                hover_data=["jaam", "kokku", "labis_esimesel", "kukkus_esimesel"],
                text="labimise_protsent",
                title=f"Inspektorid — leht {current_page}/{total_pages} "
                f"({len(insp_sorted)} inspektorit kokku)",
                labels={
                    "labimise_protsent": "Läbimise %",
                    "inspektori_kood": "Inspektori kood",
                },
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            fig.update_layout(
                coloraxis_showscale=False,
                height=max(500, len(page_df) * 30),
                yaxis={"categoryorder": "total ascending"},
                xaxis_range=[0, 105],
            )
            st.plotly_chart(fig, use_container_width=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Inspektoreid kokku", len(insp_sorted))
            c2.metric(
                "Keskmine läbimise %", f"{insp_sorted['labimise_protsent'].mean():.1f}%"
            )
            c3.metric("Madalaim %", f"{insp_sorted['labimise_protsent'].min()}%")
            c4.metric("Kõrgeim %", f"{insp_sorted['labimise_protsent'].max()}%")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Oldest car per month
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧓 Vanim auto kuus":
    st.title("🧓 Vanim tehnoülevaatuse läbinud auto kuude kaupa")
    st.write(
        "Iga kuu vanim sõiduk, mis läbis KORRALINE ülevaatuse esimesel korral (KORRAS)."
    )

    year = st.selectbox(
        "Vali aasta:", options=AVAILABLE_YEARS, index=len(AVAILABLE_YEARS) - 1
    )
    with st.spinner(f"Pärin {year} andmeid..."):
        df = q_oldest_car_per_month(year)
    if df.empty:
        st.error("Andmeid ei leitud.")
        st.stop()

    df["kuu_nimi"] = df["kuu"].map(MONTH_NAMES)
    fig = px.bar(
        df,
        x="kuu_nimi",
        y="vanus",
        color="vanus",
        color_continuous_scale="Oranges",
        text="vanus",
        hover_data=["MARK", "MUDEL", "reg_aasta", "KERETYYP"],
        title=f"{year} — vanima läbinud auto vanus kuude kaupa",
        labels={"kuu_nimi": "Kuu", "vanus": "Vanus (aastat)"},
    )
    fig.update_traces(texttemplate="%{text}a", textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        xaxis={"categoryorder": "array", "categoryarray": list(MONTH_NAMES.values())},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Detailne tabel")
    st.dataframe(
        df[["kuu_nimi", "MARK", "MUDEL", "reg_aasta", "vanus", "KERETYYP"]].rename(
            columns={
                "kuu_nimi": "Kuu",
                "MARK": "Märk",
                "MUDEL": "Mudel",
                "reg_aasta": "Esmaregistreerimine",
                "vanus": "Vanus (aastat)",
                "KERETYYP": "Keretüüp",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Age effect
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📈 Vanuse mõju läbimisele":
    st.title("📈 Vanuse mõju tehnoülevaatuse läbimisele")
    st.write(
        "Hüpotees: mida vanem sõiduk, seda väiksem tõenäosus esimesel korral läbida."
    )
    st.caption("KORRALINE ülevaatused. Läbimise % = KORRAS / (KORRAS + KORDUVALE).")

    years = year_selector("age_years", default=AVAILABLE_YEARS)
    with st.spinner("Arvutan..."):
        df = q_age_effect(years)
    if df.empty:
        st.error("Andmeid ei leitud.")
        st.stop()

    fig = px.bar(
        df,
        x="vanusegrupp",
        y="labimise_protsent",
        color="labimise_protsent",
        color_continuous_scale="RdYlGn",
        text="labimise_protsent",
        hover_data=["kokku", "labis_arv"],
        title="Esmakordse läbimise % vanusegrupi järgi",
        labels={
            "vanusegrupp": "Vanusegrupp (aastat)",
            "labimise_protsent": "Läbimise %",
        },
        range_y=[0, 105],
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.line(
        df,
        x="vanusegrupp",
        y="labimise_protsent",
        markers=True,
        title="Trend",
        labels={"vanusegrupp": "Vanusegrupp", "labimise_protsent": "Läbimise %"},
    )
    fig2.update_layout(yaxis_range=[0, 105])
    st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(
        df[["vanusegrupp", "kokku", "labis_arv", "labimise_protsent"]].rename(
            columns={
                "vanusegrupp": "Vanusegrupp",
                "kokku": "Ülevaatusi",
                "labis_arv": "Läbis esimesel",
                "labimise_protsent": "Läbimise %",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    if len(df) > 1:
        newest = df.iloc[0]["labimise_protsent"]
        oldest_val = df.iloc[-1]["labimise_protsent"]
        st.info(
            f"**Tulemus:** Uusimad ({df.iloc[0]['vanusegrupp']} a): **{newest}%** vs "
            f"vanad ({df.iloc[-1]['vanusegrupp']} a): **{oldest_val}%** "
            f"— erinevus **{newest - oldest_val:.1f}%**."
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — Defect analysis
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔧 Rikete analüüs":
    st.title("🔧 Rikete analüüs")
    st.write(
        "Analüüsitakse KORRALINE ülevaatustel leitud rikked märgi, mudeli "
        "ja väljalaskeaasta kaupa."
    )
    st.caption(
        "RIKKED veerg kujul: 'VO:100101460,OV:100103882' — "
        "VO = väheoluline, OV = oluline viga, EOV = eriti ohtlik."
    )

    years = year_selector("defects_years", default=[AVAILABLE_YEARS[-1]])

    # ── Overview metrics ──────────────────────────────────────────────────────
    with st.spinner("Laen rikete ülevaate..."):
        overview_df = q_defect_overview(years)

    if not overview_df.empty:
        totals = overview_df.sum(numeric_only=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ülevaatusi kokku", f"{int(totals['kokku_ylevaatusi']):,}")
        c2.metric("Riketega ülevaatusi", f"{int(totals['riketega_ylevaatusi']):,}")
        c3.metric("VO rikked", f"{int(totals['vo_arv']):,}")
        c4.metric("OV rikked", f"{int(totals['ov_arv']):,}")
        c5.metric("EOV rikked", f"{int(totals['eov_arv']):,}")

        # Stacked bar: severity by year
        if len(years) > 1:
            fig_ov = px.bar(
                overview_df,
                x="aasta",
                y=["vo_arv", "ov_arv", "eov_arv"],
                title="Rikete raskusaste aastate lõikes",
                labels={"aasta": "Aasta", "value": "Arv", "variable": "Raskusaste"},
                color_discrete_map={
                    "vo_arv": SEVERITY_COLORS["VO"],
                    "ov_arv": SEVERITY_COLORS["OV"],
                    "eov_arv": SEVERITY_COLORS["EOV"],
                },
                barmode="stack",
            )
            fig_ov.for_each_trace(
                lambda t: t.update(
                    name={
                        "vo_arv": "VO (väheoluline)",
                        "ov_arv": "OV (oluline)",
                        "eov_arv": "EOV (eriti ohtlik)",
                    }.get(t.name, t.name)
                )
            )
            st.plotly_chart(fig_ov, use_container_width=True)

    st.divider()

    # ── Top defects overall ───────────────────────────────────────────────────
    st.subheader("Enim esinevad rikked")
    top_n = st.slider("Mitu rikkeid näidata?", 5, 30, 15, key="top_n_defects")

    with st.spinner("Laen enim esinevaid rikked..."):
        top_df = q_top_defects(years, top_n=top_n)

    if top_df.empty:
        st.warning("Rikete andmeid ei leitud.")
    else:
        top_df["label"] = top_df["raskusaste"] + ":" + top_df["rike_id"]
        fig_top = px.bar(
            top_df.sort_values("esinemisi"),
            x="esinemisi",
            y="label",
            orientation="h",
            color="raskusaste",
            color_discrete_map=SEVERITY_COLORS,
            hover_data=["rike_id", "raskusaste", "esinemisi"],
            title=f"Top {top_n} sagedasemat riket (KORRALINE ülevaatused)",
            labels={
                "esinemisi": "Esinemisi",
                "label": "Rike (tase:ID)",
                "raskusaste": "Raskusaste",
            },
        )
        fig_top.update_layout(
            yaxis={"categoryorder": "total ascending"}, height=max(400, top_n * 30)
        )
        st.plotly_chart(fig_top, use_container_width=True)
        st.caption(
            "💡 Rikke ID tähenduse leidmiseks otsi ID numbreid failist rike.csv "
            "(veerg ID → NIMETUS)."
        )

    st.divider()

    # ── Defects by mark, model, year ─────────────────────────────────────────
    st.subheader("Rikked märgi, mudeli ja väljalaskeaasta kaupa")

    col1, col2, col3 = st.columns(3)
    with col1:
        mark_filter = (
            st.text_input(
                "Automärk (valikuline):", placeholder="nt VOLKSWAGEN", key="defect_mark"
            )
            .strip()
            .upper()
            or None
        )
    with col2:
        model_filter = (
            st.text_input(
                "Mudel (valikuline):", placeholder="nt GOLF", key="defect_model"
            )
            .strip()
            .upper()
            or None
        )
    with col3:
        year_filter = st.number_input(
            "Väljalaskeaasta (valikuline):",
            min_value=1900,
            max_value=2025,
            value=0,
            step=1,
            key="defect_year",
        )
        reg_aasta_filter = int(year_filter) if year_filter > 1900 else None

    if top_df.empty:
        st.info("Rikete andmed puuduvad.")
    else:
        top_ids = top_df["rike_id"].tolist()

        with st.spinner("Pärin rikke detaile..."):
            detail_df = q_defects_by_mark_model_year(
                years,
                top_ids,
                mark=mark_filter,
                mudel=model_filter,
                reg_aasta=reg_aasta_filter,
            )

        if detail_df.empty:
            st.warning("Valitud filtritega andmeid ei leitud.")
        else:
            detail_df["label"] = detail_df["raskusaste"] + ":" + detail_df["rike_id"]

            # Heatmap: mark vs defect ID
            pivot = (
                detail_df.groupby(["MARK", "label"])["esinemisi"].sum().reset_index()
            )
            if len(pivot["MARK"].unique()) > 1:
                pivot_wide = pivot.pivot(
                    index="MARK", columns="label", values="esinemisi"
                ).fillna(0)
                fig_heat = px.imshow(
                    pivot_wide,
                    title="Rikete esinemine märkide kaupa (heatmap)",
                    labels={"x": "Rike (tase:ID)", "y": "Märk", "color": "Esinemisi"},
                    color_continuous_scale="YlOrRd",
                    aspect="auto",
                )
                fig_heat.update_layout(height=max(300, len(pivot_wide) * 25))
                st.plotly_chart(fig_heat, use_container_width=True)

            # Bar chart: top defects for filtered selection
            top_detail = (
                detail_df.groupby(["label", "raskusaste"])["esinemisi"]
                .sum()
                .reset_index()
            )
            top_detail = top_detail.sort_values("esinemisi", ascending=True)
            fig_detail = px.bar(
                top_detail,
                x="esinemisi",
                y="label",
                orientation="h",
                color="raskusaste",
                color_discrete_map=SEVERITY_COLORS,
                title="Rikete sagedus (filtri põhjal)",
                labels={
                    "esinemisi": "Esinemisi",
                    "label": "Rike",
                    "raskusaste": "Raskusaste",
                },
            )
            fig_detail.update_layout(
                yaxis={"categoryorder": "total ascending"},
                height=max(400, len(top_detail) * 30),
            )
            st.plotly_chart(fig_detail, use_container_width=True)

            # Detailed table
            with st.expander("📋 Detailne tabel"):
                st.dataframe(
                    detail_df.rename(
                        columns={
                            "MARK": "Märk",
                            "MUDEL": "Mudel",
                            "reg_aasta": "Väljalaskeaasta",
                            "rike_id": "Rike ID",
                            "raskusaste": "Tase",
                            "esinemisi": "Esinemisi",
                        }
                    ).sort_values("Esinemisi", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )

    st.divider()

    # ── Defects by mark summary ───────────────────────────────────────────────
    st.subheader("Rikete arv märgi kaupa")
    with st.spinner("Laen rikete kokkuvõtet..."):
        mark_def_df = q_defects_summary_by_mark(years, top_n=20)

    if not mark_def_df.empty:
        fig_marks = px.bar(
            mark_def_df.sort_values("rikeid_kokku"),
            x="rikeid_kokku",
            y="MARK",
            orientation="h",
            color="rikeid_kokku",
            color_continuous_scale="Reds",
            hover_data=["vo", "ov", "eov"],
            title="Top 20 märki rikete arvu järgi",
            labels={"rikeid_kokku": "Rikeid kokku", "MARK": "Märk"},
        )
        fig_marks.update_layout(
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
            height=500,
        )
        st.plotly_chart(fig_marks, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — Search by mark
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Otsi margi järgi":
    st.title("🔍 Otsi automärgi järgi")
    st.write("Sisesta automärk ja vaata läbimise tõenäosust eri vanusegruppides.")
    st.caption("Läbimise % = KORRAS / (KORRAS + KORDUVALE) KORRALINE ülevaatustel.")

    years = year_selector("search_years", default=AVAILABLE_YEARS)

    mark_input = (
        st.text_input(
            "Sisesta automärk (nt VOLKSWAGEN, BMW, TOYOTA):",
            placeholder="VOLKSWAGEN",
        )
        .strip()
        .upper()
    )

    if not mark_input:
        st.info("Sisesta automärk ülal.")
        st.stop()

    with st.spinner(f"Otsin {mark_input}..."):
        df = q_mark_pass_by_age(years, mark_input)

    if df.empty:
        with st.spinner("Otsin sarnaseid marke..."):
            all_marks = q_available_marks(years)
        similar = [m for m in all_marks if mark_input[:3] in m][:8]
        st.error(f"Märki **{mark_input}** ei leitud.")
        if similar:
            st.write("Sarnased märgid: " + " · ".join(similar))
        st.stop()

    total = int(df["kokku"].sum())
    avg_pass = (
        round((df["kokku"] * df["labimise_protsent"]).sum() / total, 1)
        if total > 0
        else 0
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Märk", mark_input)
    c2.metric("Ülevaatusi (KORRALINE)", f"{total:,}")
    c3.metric("Keskmine läbimise %", f"{avg_pass}%")

    fig = px.bar(
        df,
        x="vanusegrupp",
        y="labimise_protsent",
        color="labimise_protsent",
        color_continuous_scale="RdYlGn",
        text="labimise_protsent",
        hover_data=["kokku"],
        title=f"{mark_input} — läbimise % vanusegrupi järgi",
        labels={"vanusegrupp": "Vanusegrupp", "labimise_protsent": "Läbimise %"},
        range_y=[0, 105],
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    fig2 = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=avg_pass,
            title={"text": f"{mark_input} — keskmine läbimise tõenäosus"},
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "darkblue"},
                "steps": [
                    {"range": [0, 50], "color": "#ff6b6b"},
                    {"range": [50, 75], "color": "#ffd93d"},
                    {"range": [75, 100], "color": "#6bcb77"},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 3},
                    "thickness": 0.75,
                    "value": 75,
                },
            },
        )
    )
    fig2.update_layout(height=300)
    st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(
        df[["vanusegrupp", "kokku", "labimise_protsent"]].rename(
            columns={
                "vanusegrupp": "Vanusegrupp",
                "kokku": "Ülevaatusi",
                "labimise_protsent": "Läbimise %",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
