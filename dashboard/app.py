"""
Streamlit dashboard — Estonian Vehicle Roadworthiness Analysis
Run with: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

import streamlit as st


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Tehnoülevaatuste analüüs")
        password = st.text_input("Sisesta parool:", type="password")
        if st.button("Sisene"):
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Vale parool.")
        st.stop()


check_password()

import plotly.express as px
import plotly.graph_objects as go

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
        "🧓 Vanim sõiduk ülevaatusel kuus",
        "📈 Vanuse mõju läbimisele",
        "🔧 Rikete analüüs",
        "🔍 Otsi margi järgi",
        "🤖 Ennustamine",
        "📦 Klastrid",
    ],
)

st.sidebar.divider()
st.sidebar.caption(f"Andmed: {min(AVAILABLE_YEARS)}–{max(AVAILABLE_YEARS)}")
st.sidebar.caption("Allikas: andmed.eesti.ee / Transpordiamet")


def year_selector(key: str) -> list:
    selected = st.multiselect(
        "Vali aastad:",
        options=AVAILABLE_YEARS,
        default=[],
        key=key,
    )
    if not selected:
        st.info("Vali vähemalt üks aasta, et päring käivitada.")
        st.stop()
    return selected


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Most popular mark
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏆 Populaarseim mark":
    st.title("🏆 Populaarseim automark tehnoülevaatustel")
    st.write(
        "Top 3 sagedamini tehnoülevaatusele tulnud automarki ja nende top 5 mudelit — "
        "kõik valitud aastad kokku summeerituna."
    )

    years = year_selector("mark_years")

    with st.spinner("Pärin andmeid... - aega võib kuluda kuni 1 minut"):
        mark_df, models_df = q_top_mark_and_models(years)

    if mark_df.empty:
        st.error("Andmeid ei leitud.")
        st.stop()

    fig = px.bar(
        mark_df,
        x="MARK",
        y="arv",
        color="MARK",
        text="arv",
        title="Top 3 populaarsemat automarki (kokku valitud aastate peale)",
        labels={"MARK": "Mark", "arv": "Ülevaatuste arv"},
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(showlegend=False, yaxis_title="Ülevaatuste arv")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 5 mudelit iga populaarse automargi hulgas")
    for _, row in mark_df.iterrows():
        mark = row["MARK"]
        mark_models = models_df[models_df["MARK"] == mark]
        with st.expander(f"{mark} — {int(row['arv']):,} ülevaatust"):
            if mark_models.empty:
                st.write("Mudelite andmed puuduvad.")
            else:
                fig2 = px.bar(
                    mark_models.sort_values("arv"),
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
    st.write("Läbimise % = KORRAS / (KORRAS + KORDUVALE) * KORRALINE ülevaatus.")

    years = year_selector("inspector_years")
    tab1, tab2 = st.tabs(["🏢 Ülevaatuspunktid", "🧑 Inspektorid"])

    with tab1:
        st.subheader("Ülevaatuspunktide läbimise määr")
        st.caption("Miinimum 100 ülevaatust tehnoülevaatuspunkti kohta.")
        with st.spinner("Pärin andmeid... - aega võib kuluda kuni 1 minut"):
            station_df = q_station_strictness(years)
        if station_df.empty:
            st.error("Andmeid ei leitud.")
        else:
            mode_s = st.radio(
                "Sorteeri:",
                ["🔴 Rangeimad", "🟢 Leebeimad"],
                horizontal=True,
                key="station_mode",
            )
            top_n_s = st.slider("Mitu punkti näitan?", 5, 30, 15, key="station_n")
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
                yaxis={
                    "categoryorder": (
                        "total descending"
                        if "Rangeimad" in mode_s
                        else "total ascending"
                    )
                },
            )
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("📋 Kõik punktid tabelina"):
                st.dataframe(
                    station_df.rename(
                        columns={
                            "jaam": "Punkt",
                            "jaama_kood": "Kood",
                            "kokku": "Kokku",
                            "labis_esimesel": "Läbis esimesel korral",
                            "kukkus_esimesel": "Kukkus läbi esimesel korral",
                            "labimise_protsent": "Läbimise %",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab2:
        st.subheader("Inspektorite läbimise määr")
        st.caption("Miinimum 50 ülevaatust inspektori kohta.")
        with st.spinner("Pärin andmeid... - aega võib kuluda kuni 1 minut"):
            insp_df = q_inspector_strictness(years)
        if insp_df.empty:
            st.error("Andmeid ei leitud.")
        else:
            all_stations = sorted(insp_df["jaam"].dropna().unique().tolist())
            sel_station = st.selectbox(
                "Filtreeri punkti järgi:",
                ["Kõik punktid"] + all_stations,
                key="insp_station",
            )
            filtered_insp = (
                insp_df[insp_df["jaam"] == sel_station].copy()
                if sel_station != "Kõik punktid"
                else insp_df.copy()
            )

            TOP_N = 10
            toughest = filtered_insp.nsmallest(TOP_N, "labimise_protsent").sort_values(
                "labimise_protsent"
            )
            easiest = filtered_insp.nlargest(TOP_N, "labimise_protsent").sort_values(
                "labimise_protsent", ascending=False
            )
            # Force x-axis to treat codes as categories in the sorted order
            toughest["kood_str"] = toughest["inspektori_kood"].astype(str)
            easiest["kood_str"] = easiest["inspektori_kood"].astype(str)

            col_l, col_r = st.columns(2)
            with col_l:
                fig_t = px.bar(
                    toughest,
                    x="kood_str",
                    y="labimise_protsent",
                    color="labimise_protsent",
                    color_continuous_scale="Reds_r",
                    text="labimise_protsent",
                    title="Top 10 rangeimad inspektorid",
                    hover_data=["jaam", "kokku", "labis_esimesel", "kukkus_esimesel"],
                    labels={
                        "kood_str": "Inspektori kood",
                        "labimise_protsent": "Läbimise %",
                    },
                    category_orders={"kood_str": toughest["kood_str"].tolist()},
                )
                fig_t.update_traces(texttemplate="%{text}%", textposition="outside")
                fig_t.update_layout(
                    coloraxis_showscale=False,
                    yaxis_range=[0, 105],
                )
                st.plotly_chart(fig_t, use_container_width=True)

            with col_r:
                fig_e = px.bar(
                    easiest,
                    x="kood_str",
                    y="labimise_protsent",
                    color="labimise_protsent",
                    color_continuous_scale="Greens",
                    text="labimise_protsent",
                    title="Top 10 leebemad inspektorid",
                    hover_data=["jaam", "kokku", "labis_esimesel", "kukkus_esimesel"],
                    labels={
                        "kood_str": "Inspektori kood",
                        "labimise_protsent": "Läbimise %",
                    },
                    category_orders={"kood_str": easiest["kood_str"].tolist()},
                )
                fig_e.update_traces(texttemplate="%{text}%", textposition="outside")
                fig_e.update_layout(
                    coloraxis_showscale=False,
                    yaxis_range=[0, 105],
                )
                st.plotly_chart(fig_e, use_container_width=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Inspektoreid kokku", len(filtered_insp))
            c2.metric(
                "Keskmine läbimise %",
                f"{filtered_insp['labimise_protsent'].mean():.1f}%",
            )
            c3.metric("Madalaim %", f"{filtered_insp['labimise_protsent'].min()}%")
            c4.metric("Kõrgeim %", f"{filtered_insp['labimise_protsent'].max()}%")

            with st.expander("📋 Kõik inspektorid tabelina"):
                st.dataframe(
                    filtered_insp.sort_values("labimise_protsent").rename(
                        columns={
                            "inspektori_kood": "Inspektori kood",
                            "jaam": "Punkt",
                            "jaama_kood": "Jaama kood",
                            "kokku": "Kokku",
                            "labis_esimesel": "Läbis",
                            "kukkus_esimesel": "Kukkus",
                            "labimise_protsent": "Läbimise %",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Oldest car per month
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧓 Vanim sõiduk ülevaatusel kuus":
    st.title("🧓 Vanim tehnoülevaatuse läbinud sõiduk kuude kaupa")
    st.write(
        "Iga kuu vanim sõiduk, mis läbis KORRALISE ülevaatuse esimesel korral (KORRAS)."
    )

    year = st.selectbox(
        "Vali aasta:",
        options=[None] + AVAILABLE_YEARS,
        index=0,
        format_func=lambda x: "— vali aasta —" if x is None else str(x),
    )
    if year is None:
        st.info("Vali aasta, et päring käivitada.")
        st.stop()
    with st.spinner(f"Pärin {year} andmeid... - aega võib kuluda kuni 1 minut"):
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
        title=f"{year} — vanima läbinud sõiduki vanus kuvatuna kuude kaupa",
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

    years = year_selector("age_years")
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
    y_min = max(0, df["labimise_protsent"].min() - 5)
    fig2.update_layout(yaxis_range=[y_min, 100])
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
        "Analüüsitakse KORRALINE ülevaatustel leitud rikked margi ja mudeli "
        "ning väljalaskeaasta kaupa."
    )
    st.caption(
        "RIKKED veerg kujul: 'VO:100101460,OV:100103882' — "
        "VO = väheoluline, OV = oluline viga, EOV = eriti oluline viga."
    )

    years = year_selector("defects_years")

    # ── Overview metrics ──────────────────────────────────────────────────────
    with st.spinner("Laen rikete ülevaadet..."):
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
    top_n = st.slider("Mitu riket näidata?", 5, 30, 15, key="top_n_defects")

    with st.spinner("Laen enim esinevaid rikked..."):
        top_df = q_top_defects(years, top_n=top_n)

    if top_df.empty:
        st.warning("Rikete andmeid ei leitud.")
    else:
        if "nimetus" in top_df.columns and top_df["nimetus"].any():
            top_df["label"] = top_df["raskusaste"] + ": " + top_df["nimetus"]
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

    st.divider()

    # ── Defects by mark, model, year ─────────────────────────────────────────
    st.subheader("Rikked margi, mudeli ja väljalaskeaasta kaupa")

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
            "Väljalaskeaasta (valikuline, 0 = kõik):",
            min_value=0,
            max_value=2025,
            value=0,
            step=1,
            key="defect_year",
        )
        reg_aasta_filter = int(year_filter) if year_filter > 0 else None

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
            if "nimetus" in detail_df.columns and detail_df["nimetus"].any():
                detail_df["label"] = (
                    detail_df["raskusaste"] + ": " + detail_df["nimetus"]
                )
            else:
                detail_df["label"] = (
                    detail_df["raskusaste"] + ":" + detail_df["rike_id"]
                )

            with st.expander("📋 Detailne tabel"):
                st.dataframe(
                    detail_df.rename(
                        columns={
                            "MARK": "Mark",
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
    st.subheader("Rikete arv margi kaupa")
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
    st.title("🔍 Otsi automargi järgi")
    st.write("Sisesta automärk ja vaata läbimise tõenäosust eri vanusegruppides.")
    st.caption("Läbimise % = KORRAS / (KORRAS + KORDUVALE) KORRALINE ülevaatustel.")

    years = year_selector("search_years")

    mark_input = (
        st.text_input(
            "Sisesta automärk (nt VOLKSWAGEN, BMW, TOYOTA):",
            placeholder="VOLKSWAGEN",
        )
        .strip()
        .upper()
    )

    if not mark_input:
        st.info("Sisesta soiduki mark ülal.")
        st.stop()

    with st.spinner(f"Otsin {mark_input}..."):
        df = q_mark_pass_by_age(years, mark_input)

    if df.empty:
        with st.spinner("Otsin sarnaseid marke..."):
            all_marks = q_available_marks(years)
        similar = [m for m in all_marks if mark_input[:3] in m][:8]
        st.error(f"Märki **{mark_input}** ei leitud.")
        if similar:
            st.write("Sarnased margid: " + " · ".join(similar))
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


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — Prediction (Ennustamine)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 Ennustamine":
    import pickle
    import json as _json
    import numpy as _np
    import pandas as _pd

    st.title("🤖 Ennusta tehnoülevaatuse tulemus")
    st.write(
        "Sisesta sõiduki andmed ja mudel ennustab, kui tõenäoliselt sõiduk läbib "
        "KORRALISE tehnoülevaatuse esimesel korral."
    )

    MODEL_PATH = Path(__file__).parent.parent / "models" / "random_forest.pkl"
    META_PATH = Path(__file__).parent.parent / "models" / "model_metadata.json"

    if not MODEL_PATH.exists():
        st.warning(
            "Mudeli fail (`models/random_forest.pkl`) puudub. "
            "Käivita esmalt `python src/prediction.py`, et mudel treenida."
        )
        st.stop()

    @st.cache_resource
    def load_model():
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        with open(META_PATH, "r", encoding="utf-8") as f:
            meta = _json.load(f)
        return model, meta

    model, meta = load_model()
    feature_names = meta["features"]
    metrics = meta.get("metrics", {})

    with st.expander("📊 Mudeli täpsus"):
        cols = st.columns(4)
        for col, (k, label) in zip(
            cols,
            [("accuracy", "Täpsus"), ("f1", "F1"), ("roc_auc", "ROC AUC"), ("precision", "Precision")],
        ):
            if k in metrics:
                col.metric(label, f"{metrics[k]:.3f}")

    st.divider()
    st.subheader("Sisesta sõiduki andmed")

    KERETYYP_MAP = {
        "Sedaan": 0, "Universaal": 1, "Luukpära": 2,
        "Mahtuniversaal": 3, "Kaubik": 4, "Kupee": 5,
        "Lahtine": 6, "Pikap": 7, "Mootorratas": 8,
        "Mitmeotstarbeline": 9, "Madel": 10,
        "Elamu": 11, "Sadul": 12, "Paadiveok": 13, "Kvadrik": 14,
    }

    col1, col2 = st.columns(2)
    with col1:
        vanus = st.number_input("Sõiduki vanus (aastat)", min_value=0, max_value=60, value=10, step=1)
        keretyyp_label = st.selectbox("Keretüüp", list(KERETYYP_MAP.keys()), index=0)
        keretyyp_kood = KERETYYP_MAP[keretyyp_label]
    with col2:
        punkti_rangus = st.slider(
            "Ülevaatuspunkti rangus (% kukkumisi, 0=leebe, 40=range)",
            min_value=0.0, max_value=50.0, value=20.0, step=0.5,
        )
        eelmised_yv = st.number_input(
            "Varasemaid ülevaatusi sellel sõidukil", min_value=0, max_value=30, value=0, step=1
        )

    # Month selector for seasonality features
    kuu = st.select_slider(
        "Ülevaatuse kuu",
        options=list(range(1, 13)),
        value=6,
        format_func=lambda x: MONTH_NAMES[x],
    )

    input_vals = {
        "VANUS": float(vanus),
        "VANUS_RUUT": float(vanus ** 2),
        "ON_VANA": float(1 if vanus > 10 else 0),
        "KUU_SIN": float(_np.sin(2 * _np.pi * kuu / 12)),
        "KUU_COS": float(_np.cos(2 * _np.pi * kuu / 12)),
        "MARK_SAGEDUS": 50000.0,
        "MARK_LABIMISE_MAAR": 0.75,
        "KERETYYP_KOOD": float(keretyyp_kood),
        "PUNKTI_RANGUS": float(punkti_rangus),
        "EELMISED_YV": float(eelmised_yv),
    }

    if st.button("Ennusta", type="primary"):
        row = _pd.DataFrame([[input_vals[f] for f in feature_names]], columns=feature_names)
        prob = model.predict_proba(row)[0][1] * 100

        st.divider()
        if prob >= 75:
            st.success(f"### ✅ Läbimise tõenäosus: **{prob:.1f}%**")
        elif prob >= 50:
            st.warning(f"### ⚠️ Läbimise tõenäosus: **{prob:.1f}%**")
        else:
            st.error(f"### ❌ Läbimise tõenäosus: **{prob:.1f}%**")

        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=prob,
            number={"suffix": "%"},
            title={"text": "Läbimise tõenäosus"},
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
        ))
        gauge.update_layout(height=300)
        st.plotly_chart(gauge, use_container_width=True)

    with st.expander("ℹ️ Mudeli tunnuste tähtsus"):
        fi = meta.get("feature_importance", [])
        if fi:
            fi_df = _pd.DataFrame(fi).sort_values("importance", ascending=True)
            fig_fi = px.bar(
                fi_df, x="importance", y="feature", orientation="h",
                labels={"importance": "Olulisus", "feature": "Tunnus"},
                title="Tunnuste olulisus (Random Forest)",
            )
            st.plotly_chart(fig_fi, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 8 — Clusters (Klastrid)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📦 Klastrid":
    import json as _json
    import pandas as _pd

    st.title("📦 Sõidukite klastrid")
    st.write(
        "K-Means klasterdamine grupeerib ülevaatused sarnaste profiilide järgi "
        "(sõiduki vanus, keretüüp, ülevaatuspunkti rangus)."
    )

    PROFILES_PATH = Path(__file__).parent.parent / "data" / "processed" / "cluster_profiles.json"
    ELBOW_PATH = Path(__file__).parent.parent / "data" / "processed" / "elbow_plot.png"

    if not PROFILES_PATH.exists():
        st.warning(
            "Klastrite fail (`data/processed/cluster_profiles.json`) puudub. "
            "Käivita esmalt `python src/clustering.py`."
        )
        st.stop()

    with open(PROFILES_PATH, "r", encoding="utf-8") as f:
        profiles = _json.load(f)

    st.subheader(f"Leiti {len(profiles)} klastrit")

    cols = st.columns(len(profiles))
    for col, p in zip(cols, profiles):
        with col:
            st.metric(f"Klaster {p['cluster']}", p["pct"])
            st.write(f"**Keskmine vanus:** {p['avg_age']:.1f} a")
            st.write(f"**Rangus:** {p['avg_strictness']:.1f}%")
            if p.get("pass_rate") is not None:
                st.write(f"**Läbimise %:** {p['pass_rate']:.1f}%")
            if p.get("top_makes"):
                top = list(p["top_makes"].keys())[:3]
                st.write(f"**Top margid:** {', '.join(top)}")

    st.divider()

    import pandas as _pd
    profile_df = _pd.DataFrame([
        {
            "Klaster": p["cluster"],
            "Suurus": p["pct"],
            "Keskmine vanus (a)": round(p["avg_age"], 1),
            "Punkti rangus (%)": round(p["avg_strictness"], 1),
            "Läbimise % (esimesel)": round(p["pass_rate"], 1) if p.get("pass_rate") is not None else "—",
            "Top margid": ", ".join(list(p.get("top_makes", {}).keys())[:3]),
        }
        for p in profiles
    ])
    st.dataframe(profile_df, use_container_width=True, hide_index=True)

    if ELBOW_PATH.exists():
        st.divider()
        st.subheader("Optimaalse k leidmine")
        st.image(str(ELBOW_PATH), caption="Elbow-meetod ja siluetiskoor")

    st.divider()
    st.subheader("Klastrite võrdlus")
    if len(profiles) > 1 and all(p.get("pass_rate") is not None for p in profiles):
        fig_cluster = px.bar(
            profile_df,
            x="Klaster",
            y="Läbimise % (esimesel)",
            color="Läbimise % (esimesel)",
            color_continuous_scale="RdYlGn",
            text="Läbimise % (esimesel)",
            title="Läbimise % klastri järgi",
            labels={"Klaster": "Klaster", "Läbimise % (esimesel)": "Läbimise %"},
        )
        fig_cluster.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_cluster.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_cluster, use_container_width=True)

    fig_scatter = px.scatter(
        profile_df,
        x="Keskmine vanus (a)",
        y="Punkti rangus (%)",
        size=[float(str(p["pct"]).rstrip("%")) for p in profiles],
        color=[f"Klaster {p['cluster']}" for p in profiles],
        text=[f"K{p['cluster']}" for p in profiles],
        title="Klastrid: vanus vs punkti rangus (suurus = klastri osakaal)",
        labels={"x": "Keskmine vanus (a)", "y": "Punkti rangus (%)"},
    )
    fig_scatter.update_traces(textposition="top center")
    st.plotly_chart(fig_scatter, use_container_width=True)
