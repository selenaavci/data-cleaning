import streamlit as st
import pandas as pd
import numpy as np
import io
from cleaning import CleaningEngine

st.set_page_config(page_title="Data Cleaning Agent", page_icon="🧹", layout="wide")

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .metric-card {
        background: #f0f2f6;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-card h3 { margin: 0; font-size: 1.8rem; color: #0e1117; }
    .metric-card p { margin: 0; font-size: 0.85rem; color: #555; }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("🧹 Data Cleaning Agent")
st.caption("Upload your dataset, select cleaning operations, and download the cleaned version.")

# ── Session State ────────────────────────────────────────────────────
if "engine" not in st.session_state:
    st.session_state.engine = None
if "cleaned" not in st.session_state:
    st.session_state.cleaned = False

# ── Sidebar: File Upload ─────────────────────────────────────────────
with st.sidebar:
    st.header("📁 Upload Dataset")
    uploaded = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx", "xls"])

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)

            if st.session_state.engine is None or st.session_state.get("_file_name") != uploaded.name:
                st.session_state.engine = CleaningEngine(df)
                st.session_state.cleaned = False
                st.session_state._file_name = uploaded.name

            st.success(f"**{uploaded.name}** loaded — {len(df)} rows, {len(df.columns)} columns")
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()
    else:
        st.info("Upload a file to get started.")
        st.stop()

engine = st.session_state.engine

# ── Dataset Preview ──────────────────────────────────────────────────
st.header("📊 Dataset Preview")
tab_preview, tab_info = st.tabs(["Data", "Column Info"])

with tab_preview:
    st.dataframe(engine.df.head(100), use_container_width=True, height=300)

with tab_info:
    info_data = []
    for col in engine.df.columns:
        info_data.append({
            "Column": col,
            "Type": str(engine.df[col].dtype),
            "Non-Null": int(engine.df[col].notna().sum()),
            "Null": int(engine.df[col].isnull().sum()),
            "Null %": round(engine.df[col].isnull().sum() / len(engine.df) * 100, 1),
            "Unique": int(engine.df[col].nunique()),
        })
    st.dataframe(pd.DataFrame(info_data), use_container_width=True, hide_index=True)

# ── Detected Issues ──────────────────────────────────────────────────
st.header("🔍 Detected Issues")
issues = engine.detect_issues()

if not issues:
    st.success("No issues detected in the dataset!")
else:
    cols = st.columns(4)
    with cols[0]:
        missing_count = len(issues.get("missing_values", {}))
        st.metric("Missing Value Columns", missing_count)
    with cols[1]:
        st.metric("Duplicate Rows", issues.get("duplicates", 0))
    with cols[2]:
        st.metric("Type Issues", len(issues.get("type_issues", {})))
    with cols[3]:
        st.metric("Outlier Columns", len(issues.get("outliers", {})))

    if "missing_values" in issues:
        with st.expander(f"Missing Values — {missing_count} column(s)"):
            for col, info in issues["missing_values"].items():
                st.write(f"- **{col}**: {info['count']} missing ({info['pct']}%)")

    if "duplicates" in issues:
        with st.expander(f"Duplicates — {issues['duplicates']} row(s)"):
            st.write(f"Found **{issues['duplicates']}** fully duplicated rows.")

    if "type_issues" in issues:
        with st.expander(f"Type Issues — {len(issues['type_issues'])} column(s)"):
            for col, kind in issues["type_issues"].items():
                label = "Numeric stored as text" if kind == "numeric_as_text" else "Date stored as text"
                st.write(f"- **{col}**: {label}")

    if "text_issues" in issues:
        with st.expander(f"Text Issues — {len(issues['text_issues'])} column(s)"):
            for col, info in issues["text_issues"].items():
                st.write(f"- **{col}**: {info['whitespace']} whitespace issues, {info['extra_spaces']} extra spaces")

    if "placeholder_values" in issues:
        with st.expander(f"Placeholder Values — {len(issues['placeholder_values'])} column(s)"):
            for col, count in issues["placeholder_values"].items():
                st.write(f"- **{col}**: {count} placeholder values (e.g. N/A, null, -, unknown)")

    if "outliers" in issues:
        with st.expander(f"Outliers — {len(issues['outliers'])} column(s)"):
            for col, info in issues["outliers"].items():
                st.write(f"- **{col}**: {info['count']} outliers (bounds: {info['lower_bound']} – {info['upper_bound']})")

# ── Cleaning Options ─────────────────────────────────────────────────
st.header("⚙️ Cleaning Options")

numeric_cols = list(engine.df.select_dtypes(include=["number"]).columns)
text_cols = list(engine.df.select_dtypes(include=["object"]).columns)
all_cols = list(engine.df.columns)

# -- Missing Values
with st.expander("🔧 Missing Value Handling", expanded=True):
    missing_cols = [col for col in all_cols if engine.df[col].isnull().sum() > 0]
    missing_settings = {}

    if not missing_cols:
        st.write("No missing values found.")
    else:
        st.write("Configure how to handle missing values for each column:")
        drop_threshold = st.slider(
            "Drop columns with missing rate above (%)",
            0, 100, 80, 5,
            key="drop_threshold",
            help="Columns exceeding this threshold will be dropped entirely."
        )
        st.divider()
        for col in missing_cols:
            pct = round(engine.df[col].isnull().sum() / len(engine.df) * 100, 1)
            is_numeric = col in numeric_cols
            c1, c2 = st.columns([2, 3])
            with c1:
                st.write(f"**{col}** ({pct}% missing)")
            with c2:
                if is_numeric:
                    strategy = st.selectbox(
                        f"Strategy for {col}",
                        ["skip", "mean", "median", "zero", "drop_rows"],
                        key=f"missing_{col}",
                        label_visibility="collapsed",
                    )
                else:
                    strategy = st.selectbox(
                        f"Strategy for {col}",
                        ["skip", "mode", "placeholder", "drop_rows"],
                        key=f"missing_{col}",
                        label_visibility="collapsed",
                    )
                missing_settings[col] = strategy

# -- Duplicates
with st.expander("🔧 Duplicate Removal"):
    dup_count = int(engine.df.duplicated().sum())
    remove_dups = False
    if dup_count > 0:
        remove_dups = st.checkbox(f"Remove {dup_count} duplicate rows", value=True)
    else:
        st.write("No duplicates found.")

# -- Type Conversions
with st.expander("🔧 Data Type Conversions"):
    type_issues = issues.get("type_issues", {})
    type_settings = {}
    if not type_issues:
        st.write("No type issues detected.")
    else:
        for col, kind in type_issues.items():
            label = "Convert to numeric" if kind == "numeric_as_text" else "Convert to datetime"
            type_settings[col] = st.checkbox(label + f" — **{col}**", value=True, key=f"type_{col}")

    st.divider()
    st.subheader("Boolean Normalization")
    bool_candidates = []
    for col in text_cols:
        unique_lower = set(engine.df[col].dropna().astype(str).str.strip().str.lower().unique())
        bool_vals = {"yes", "no", "true", "false", "1", "0", "evet", "hayır", "hayir"}
        if unique_lower and unique_lower.issubset(bool_vals):
            bool_candidates.append(col)
    bool_settings = {}
    if bool_candidates:
        for col in bool_candidates:
            bool_settings[col] = st.checkbox(f"Normalize boolean — **{col}**", value=True, key=f"bool_{col}")
    else:
        st.write("No boolean-like columns detected.")

# -- Text Cleaning
with st.expander("🔧 Text Standardization"):
    if not text_cols:
        st.write("No text columns found.")
    else:
        text_settings = {}
        selected_text_cols = st.multiselect("Select text columns to clean", text_cols, default=text_cols, key="text_cols_select")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            do_trim = st.checkbox("Trim whitespace", value=True, key="do_trim")
        with c2:
            do_extra_spaces = st.checkbox("Remove extra spaces", value=True, key="do_extra_spaces")
        with c3:
            case_option = st.selectbox("Case conversion", ["none", "lower", "upper", "title"], key="case_option")
        with c4:
            do_punctuation = st.checkbox("Remove punctuation", value=False, key="do_punctuation")

# -- Placeholder Cleanup
with st.expander("🔧 Placeholder / Invalid Value Cleanup"):
    placeholder_issues = issues.get("placeholder_values", {})
    placeholder_settings = {}
    if not placeholder_issues:
        st.write("No placeholder values detected.")
    else:
        st.write("Replace common placeholder values (N/A, null, -, unknown, etc.) with empty/NaN:")
        for col, count in placeholder_issues.items():
            placeholder_settings[col] = st.checkbox(
                f"Clean **{col}** ({count} placeholders)",
                value=True,
                key=f"placeholder_{col}",
            )

# -- Outliers
with st.expander("🔧 Outlier Handling"):
    outlier_issues = issues.get("outliers", {})
    outlier_settings = {}
    if not outlier_issues:
        st.write("No outliers detected.")
    else:
        for col, info in outlier_issues.items():
            c1, c2 = st.columns([2, 2])
            with c1:
                do_outlier = st.checkbox(
                    f"Handle outliers in **{col}** ({info['count']} outliers)",
                    value=False,
                    key=f"outlier_do_{col}",
                )
            with c2:
                method = st.selectbox(
                    f"Method for {col}",
                    ["iqr", "winsorize"],
                    key=f"outlier_method_{col}",
                    label_visibility="collapsed",
                )
            if do_outlier:
                outlier_settings[col] = method

# ── Apply Cleaning ───────────────────────────────────────────────────
st.divider()

if st.button("🚀 Apply Cleaning", type="primary", use_container_width=True):
    # Reset to original data for fresh cleaning
    engine.df = engine.original_df.copy()
    engine.log = []

    # 1. Drop high-missing columns
    if missing_cols:
        engine.drop_high_missing_columns(threshold=drop_threshold / 100)

    # 2. Placeholder cleanup (before missing value handling so they become NaN)
    for col, do_it in placeholder_settings.items():
        if do_it and col in engine.df.columns:
            engine.replace_placeholders(col)

    # 3. Missing values
    for col, strategy in missing_settings.items():
        if strategy == "skip" or col not in engine.df.columns:
            continue
        if col in numeric_cols:
            engine.handle_missing_numeric(col, strategy)
        else:
            engine.handle_missing_categorical(col, strategy)

    # 4. Duplicates
    if remove_dups:
        engine.remove_duplicates()

    # 5. Type conversions
    for col, do_it in type_settings.items():
        if do_it and col in engine.df.columns:
            kind = type_issues[col]
            if kind == "numeric_as_text":
                engine.convert_to_numeric(col)
            else:
                engine.convert_to_datetime(col)

    for col, do_it in bool_settings.items():
        if do_it and col in engine.df.columns:
            engine.normalize_boolean(col)

    # 6. Text cleaning
    if text_cols:
        for col in selected_text_cols:
            if col not in engine.df.columns:
                continue
            if engine.df[col].dtype != "object":
                continue
            if do_trim:
                engine.trim_whitespace(col)
            if do_extra_spaces:
                engine.remove_extra_spaces(col)
            if case_option != "none":
                engine.change_case(col, case_option)
            if do_punctuation:
                engine.remove_punctuation(col)

    # 7. Outliers
    for col, method in outlier_settings.items():
        if col in engine.df.columns:
            engine.cap_outliers(col, method)

    st.session_state.cleaned = True
    st.rerun()

# ── Results ──────────────────────────────────────────────────────────
if st.session_state.cleaned and engine.log:
    st.header("✅ Cleaning Results")

    metrics = engine.get_metrics()

    m_cols = st.columns(4)
    with m_cols[0]:
        st.metric("Rows Before", metrics["rows_before"])
    with m_cols[1]:
        st.metric("Rows After", metrics["rows_after"], delta=-metrics["rows_removed"] if metrics["rows_removed"] else None)
    with m_cols[2]:
        st.metric("Missing Before", metrics["missing_before"])
    with m_cols[3]:
        st.metric("Missing After", metrics["missing_after"], delta=-(metrics["missing_before"] - metrics["missing_after"]) if metrics["missing_before"] != metrics["missing_after"] else None)

    st.subheader("Transformation Log")
    summary_df = engine.get_summary_df()
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.subheader("Cleaned Data Preview")
    st.dataframe(engine.df.head(100), use_container_width=True, height=300)

    # ── Downloads ────────────────────────────────────────────────────
    st.header("📥 Download")

    col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)

    with col_dl1:
        csv_buffer = io.BytesIO()
        engine.df.to_csv(csv_buffer, index=False)
        st.download_button(
            "⬇ Cleaned Data (CSV)",
            csv_buffer.getvalue(),
            "cleaned_dataset.csv",
            "text/csv",
            use_container_width=True,
        )

    with col_dl2:
        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine="xlsxwriter") as writer:
            engine.df.to_excel(writer, index=False, sheet_name="Cleaned Data")
        st.download_button(
            "⬇ Cleaned Data (Excel)",
            xlsx_buffer.getvalue(),
            "cleaned_dataset.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col_dl3:
        summary_csv = io.BytesIO()
        summary_df.to_csv(summary_csv, index=False)
        st.download_button(
            "⬇ Summary (CSV)",
            summary_csv.getvalue(),
            "cleaning_summary.csv",
            "text/csv",
            use_container_width=True,
        )

    with col_dl4:
        summary_xlsx = io.BytesIO()
        with pd.ExcelWriter(summary_xlsx, engine="xlsxwriter") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Cleaning Summary")
        st.download_button(
            "⬇ Summary (Excel)",
            summary_xlsx.getvalue(),
            "cleaning_summary.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

elif st.session_state.cleaned and not engine.log:
    st.info("No cleaning actions were applied. Adjust the options above and try again.")
