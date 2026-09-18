"""Interactive data-quality dashboard for panel / cross-sectional CSVs.

Run with:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from scipy import stats

from data_utils import diagnose_missing, profile_dataframe

BIGMAC_URL = (
    "https://raw.githubusercontent.com/TheEconomist/big-mac-data/"
    "master/output-data/big-mac-full-index.csv"
)

st.set_page_config(page_title="Data Quality Profiler", layout="wide")
st.title("Data Quality Profiler")
st.caption(
    "Upload any CSV, or use the Big Mac Index, to auto-detect its structure "
    "and quantify the bias a naive missing-data filter would introduce."
)

# --------------------------------------------------------------- load data
source = st.radio("Data source", ["Big Mac Index (default)", "Upload a CSV"])


@st.cache_data
def load_bigmac() -> pd.DataFrame:
    return pd.read_csv(BIGMAC_URL, parse_dates=["date"])


if source == "Upload a CSV":
    uploaded = st.file_uploader("CSV file", type="csv")
    if uploaded is None:
        st.info("Upload a file to continue, or switch to the Big Mac Index.")
        st.stop()
    df = pd.read_csv(uploaded)
else:
    df = load_bigmac()

st.write(f"Loaded **{df.shape[0]:,} rows** x **{df.shape[1]} columns**")


# ------------------------------------------------- auto-detect structure
# Heuristic, not a verdict -- both guesses are overridable in the sidebar.
# TIME column: the one that parses as a date and has more than one value.
# UNIT column: a repeating, non-time categorical column (a "unit" must
# appear more than once for this to be a panel rather than one row/unit).
def guess_time_col(data: pd.DataFrame) -> str | None:
    for col in data.columns:
        if pd.api.types.is_datetime64_any_dtype(data[col]):
            return col
    for col in data.columns:
        try:
            parsed = pd.to_datetime(data[col], errors="raise")
            if parsed.nunique() > 1:
                return col
        except (ValueError, TypeError):
            continue
    return None


def guess_unit_col(data: pd.DataFrame, time_col: str | None) -> str | None:
    candidates = [c for c in data.columns if c != time_col]
    repeating = [c for c in candidates if 1 < data[c].nunique() < len(data)]
    if not repeating:
        return candidates[0] if candidates else None
    # prefer the categorical (non-numeric) column with the most distinct values
    repeating.sort(
        key=lambda c: (pd.api.types.is_numeric_dtype(data[c]), -data[c].nunique())
    )
    return repeating[0]


guessed_time = guess_time_col(df)
guessed_unit = guess_unit_col(df, guessed_time)

st.sidebar.header("Structure (auto-detected, override if wrong)")
cols = list(df.columns)
time_col = st.sidebar.selectbox(
    "Time column", options=cols,
    index=cols.index(guessed_time) if guessed_time in cols else 0,
)
unit_col = st.sidebar.selectbox(
    "Unit column", options=cols,
    index=cols.index(guessed_unit) if guessed_unit in cols else 0,
)

if not pd.api.types.is_datetime64_any_dtype(df[time_col]):
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

profile = profile_dataframe(df, unit_col=unit_col, time_col=time_col)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Structure", profile["structure"])
c2.metric("Units", profile["n_units"])
c3.metric("Periods", profile["n_periods"])
c4.metric("Balanced panel?", "Yes" if profile["balanced"] else "No")

# ------------------------------------------------------------- missingness
st.header("Missing data")
missing_df = (
    pd.Series(profile["missing"], name="pct_missing")
    .sort_values(ascending=False)
    .reset_index()
    .rename(columns={"index": "column"})
)
fig = px.bar(
    missing_df, x="pct_missing", y="column", orientation="h",
    title="Share missing by column (%)",
)
fig.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

if profile["structure"] == "panel":
    st.subheader("Per-unit coverage")
    coverage = diagnose_missing(df, unit_col=unit_col, time_col=time_col)
    st.dataframe(coverage, use_container_width=True)

    fig2 = px.histogram(
        coverage, x="pct_missing", color="mcar_flag",
        title="Per-unit missingness by likely mechanism",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ------------------------------------------------- balanced vs. available
    st.header("Balanced-only vs. all-available")
    st.write(
        "Restricting to units present in every period is a common but "
        "silent filter (Lab 1, Part 2). Toggle below to see whether it "
        "moves a downstream average, and in which direction."
    )
    numeric_cols = df.select_dtypes("number").columns.tolist()
    if numeric_cols:
        metric_col = st.selectbox("Metric to average", numeric_cols)
        mode = st.radio(
            "Analysis", ["All available (honest)", "Balanced-only (naive)"]
        )

        complete_units = coverage.loc[coverage["mcar_flag"] == "complete", unit_col]
        plot_df = (
            df[df[unit_col].isin(complete_units)]
            if mode == "Balanced-only (naive)"
            else df
        )
        st.line_chart(plot_df.groupby(time_col)[metric_col].mean())

        # ------------------------------------------------------- bias
        complete_only = (
            df[df[unit_col].isin(complete_units)]
            .groupby(time_col)[metric_col]
            .mean()
        )
        all_available = df.groupby(time_col)[metric_col].mean()
        gap = complete_only - all_available

        st.subheader("Bias from the balanced-only filter")
        colA, colB = st.columns(2)
        colA.metric("Mean overstatement", f"{gap.mean():+.3f}")
        colB.metric(
            "Higher in balanced-only",
            f"{int((gap > 0).sum())} / {len(gap)} periods",
        )

        latest = df[time_col].max()
        cross = df[df[time_col] == latest]
        g1 = cross[cross[unit_col].isin(complete_units)][metric_col].dropna()
        g2 = cross[~cross[unit_col].isin(complete_units)][metric_col].dropna()
        if len(g1) > 1 and len(g2) > 1:
            t_stat, p_val = stats.ttest_ind(g1, g2, equal_var=False)
            st.write(
                f"Welch's t-test, most recent period ({latest.date()}): "
                f"t = {t_stat:.2f}, p = {p_val:.3f} (n = {len(g1)} vs {len(g2)})"
            )
else:
    st.info("Balanced-vs-available comparison applies to panel data only.")