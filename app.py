import streamlit as st
import pandas as pd
import numpy as np
import io
from cleaning import CleaningEngine

st.set_page_config(page_title="Data Cleaning Agent", layout="wide")

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("Data Cleaning Agent")
st.caption("Veri setinizi yukleyin, temizleme islemlerini secin ve temizlenmis versiyonu indirin.")

# ── Session State ────────────────────────────────────────────────────
if "engine" not in st.session_state:
    st.session_state.engine = None
if "cleaned" not in st.session_state:
    st.session_state.cleaned = False

# ── Sidebar: Dosya Yukleme ───────────────────────────────────────────
with st.sidebar:
    st.header("Dosya Yukle")
    uploaded = st.file_uploader(
        "CSV veya Excel dosyasi secin",
        type=["csv", "xlsx", "xls"],
    )

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

            st.success(f"**{uploaded.name}** yuklendi - {len(df)} satir, {len(df.columns)} kolon")
        except Exception as e:
            st.error(f"Dosya okunamadi: {e}")
            st.stop()
    else:
        st.info("Baslamak icin bir dosya yukleyin.")
        st.stop()

engine = st.session_state.engine

# ── Veri Seti Onizleme ──────────────────────────────────────────────
st.header("Veri Seti Onizleme")
tab_preview, tab_info = st.tabs(["Veri", "Kolon Bilgisi"])

with tab_preview:
    st.dataframe(engine.df.head(100), use_container_width=True, height=300)

with tab_info:
    info_data = []
    for col in engine.df.columns:
        info_data.append({
            "Kolon": col,
            "Tip": str(engine.df[col].dtype),
            "Dolu": int(engine.df[col].notna().sum()),
            "Bos": int(engine.df[col].isnull().sum()),
            "Bos %": round(engine.df[col].isnull().sum() / len(engine.df) * 100, 1),
            "Benzersiz": int(engine.df[col].nunique()),
        })
    st.dataframe(pd.DataFrame(info_data), use_container_width=True, hide_index=True)

# ── Tespit Edilen Sorunlar ───────────────────────────────────────────
st.header("Tespit Edilen Sorunlar")
issues = engine.detect_issues()

if not issues:
    st.success("Veri setinde herhangi bir sorun tespit edilmedi.")
else:
    cols = st.columns(4)
    with cols[0]:
        missing_count = len(issues.get("missing_values", {}))
        st.metric("Eksik Degerli Kolon", missing_count)
    with cols[1]:
        st.metric("Tekrar Eden Satir", issues.get("duplicates", 0))
    with cols[2]:
        st.metric("Tip Uyumsuzlugu", len(issues.get("type_issues", {})))
    with cols[3]:
        st.metric("Aykiri Deger Kolonu", len(issues.get("outliers", {})))

    if "missing_values" in issues:
        with st.expander(f"Eksik Degerler - {missing_count} kolon"):
            for col, info in issues["missing_values"].items():
                st.write(f"- **{col}**: {info['count']} eksik ({info['pct']}%)")

    if "duplicates" in issues:
        with st.expander(f"Tekrar Eden Satirlar - {issues['duplicates']} satir"):
            st.write(f"Toplam **{issues['duplicates']}** tam tekrar eden satir bulundu.")

    if "type_issues" in issues:
        with st.expander(f"Tip Uyumsuzluklari - {len(issues['type_issues'])} kolon"):
            for col, kind in issues["type_issues"].items():
                label = "Metin olarak saklanan sayisal deger" if kind == "numeric_as_text" else "Metin olarak saklanan tarih"
                st.write(f"- **{col}**: {label}")

    if "text_issues" in issues:
        with st.expander(f"Metin Sorunlari - {len(issues['text_issues'])} kolon"):
            for col, info in issues["text_issues"].items():
                st.write(f"- **{col}**: {info['whitespace']} bosluk sorunu, {info['extra_spaces']} fazla bosluk")

    if "placeholder_values" in issues:
        with st.expander(f"Gecersiz Yer Tutucu Degerler - {len(issues['placeholder_values'])} kolon"):
            for col, count in issues["placeholder_values"].items():
                st.write(f"- **{col}**: {count} yer tutucu deger (orn. N/A, null, -, unknown)")

    if "outliers" in issues:
        with st.expander(f"Aykiri Degerler - {len(issues['outliers'])} kolon"):
            for col, info in issues["outliers"].items():
                st.write(f"- **{col}**: {info['count']} aykiri deger (sinirlar: {info['lower_bound']} - {info['upper_bound']})")

# ── Temizleme Secenekleri ────────────────────────────────────────────
st.header("Temizleme Secenekleri")

numeric_cols = list(engine.df.select_dtypes(include=["number"]).columns)
text_cols = list(engine.df.select_dtypes(include=["object"]).columns)
all_cols = list(engine.df.columns)

# -- Eksik Degerler
with st.expander("Eksik Deger Yonetimi", expanded=True):
    missing_cols = [col for col in all_cols if engine.df[col].isnull().sum() > 0]
    missing_settings = {}

    if not missing_cols:
        st.write("Eksik deger bulunamadi.")
    else:
        st.write("Her kolon icin eksik deger stratejisini belirleyin:")
        drop_threshold = st.slider(
            "Eksiklik orani bu yuzdeden yuksek olan kolonlari sil (%)",
            0, 100, 80, 5,
            key="drop_threshold",
            help="Bu esigi asan kolonlar tamamen kaldirilir."
        )
        st.divider()
        for col in missing_cols:
            pct = round(engine.df[col].isnull().sum() / len(engine.df) * 100, 1)
            is_numeric = col in numeric_cols
            c1, c2 = st.columns([2, 3])
            with c1:
                st.write(f"**{col}** ({pct}% eksik)")
            with c2:
                if is_numeric:
                    strategy = st.selectbox(
                        f"{col} stratejisi",
                        ["atla", "ortalama", "medyan", "sifir", "satirlari_sil"],
                        key=f"missing_{col}",
                        label_visibility="collapsed",
                        format_func=lambda x: {
                            "atla": "Atla",
                            "ortalama": "Ortalama ile doldur",
                            "medyan": "Medyan ile doldur",
                            "sifir": "Sifir ile doldur",
                            "satirlari_sil": "Satirlari sil",
                        }[x],
                    )
                else:
                    strategy = st.selectbox(
                        f"{col} stratejisi",
                        ["atla", "mod", "yer_tutucu", "satirlari_sil"],
                        key=f"missing_{col}",
                        label_visibility="collapsed",
                        format_func=lambda x: {
                            "atla": "Atla",
                            "mod": "En sik deger ile doldur",
                            "yer_tutucu": "Yer tutucu ile doldur",
                            "satirlari_sil": "Satirlari sil",
                        }[x],
                    )
                missing_settings[col] = strategy

# -- Tekrar Eden Satirlar
with st.expander("Tekrar Eden Satirlarin Kaldirilmasi"):
    dup_count = int(engine.df.duplicated().sum())
    remove_dups = False
    if dup_count > 0:
        remove_dups = st.checkbox(f"{dup_count} tekrar eden satiri kaldir", value=True)
    else:
        st.write("Tekrar eden satir bulunamadi.")

# -- Tip Donusumleri
with st.expander("Veri Tipi Donusumleri"):
    type_issues = issues.get("type_issues", {})
    type_settings = {}
    if not type_issues:
        st.write("Tip uyumsuzlugu tespit edilmedi.")
    else:
        for col, kind in type_issues.items():
            label = "Sayisala donustur" if kind == "numeric_as_text" else "Tarihe donustur"
            type_settings[col] = st.checkbox(f"{label} - **{col}**", value=True, key=f"type_{col}")

    st.divider()
    st.subheader("Boolean Normalizasyonu")
    bool_candidates = []
    for col in text_cols:
        unique_lower = set(engine.df[col].dropna().astype(str).str.strip().str.lower().unique())
        bool_vals = {"yes", "no", "true", "false", "1", "0", "evet", "hayir", "hayır"}
        if unique_lower and unique_lower.issubset(bool_vals):
            bool_candidates.append(col)
    bool_settings = {}
    if bool_candidates:
        for col in bool_candidates:
            bool_settings[col] = st.checkbox(f"Boolean'a donustur - **{col}**", value=True, key=f"bool_{col}")
    else:
        st.write("Boolean benzeri kolon tespit edilmedi.")

# -- Metin Temizleme
with st.expander("Metin Standardizasyonu"):
    if not text_cols:
        st.write("Metin kolonu bulunamadi.")
    else:
        text_settings = {}
        selected_text_cols = st.multiselect("Temizlenecek metin kolonlarini secin", text_cols, default=text_cols, key="text_cols_select")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            do_trim = st.checkbox("Bosluk kirp", value=True, key="do_trim")
        with c2:
            do_extra_spaces = st.checkbox("Fazla bosluklari sil", value=True, key="do_extra_spaces")
        with c3:
            case_option = st.selectbox(
                "Harf donusumu",
                ["yok", "kucuk_harf", "buyuk_harf", "baslik"],
                key="case_option",
                format_func=lambda x: {
                    "yok": "Yok",
                    "kucuk_harf": "Kucuk harf",
                    "buyuk_harf": "Buyuk harf",
                    "baslik": "Baslik formati",
                }[x],
            )
        with c4:
            do_punctuation = st.checkbox("Noktalama isareti sil", value=False, key="do_punctuation")

# -- Yer Tutucu / Gecersiz Deger Temizligi
with st.expander("Yer Tutucu / Gecersiz Deger Temizligi"):
    placeholder_issues = issues.get("placeholder_values", {})
    placeholder_settings = {}
    if not placeholder_issues:
        st.write("Yer tutucu deger tespit edilmedi.")
    else:
        st.write("Yaygin yer tutucu degerleri (N/A, null, -, unknown vb.) bos/NaN ile degistir:")
        for col, count in placeholder_issues.items():
            placeholder_settings[col] = st.checkbox(
                f"**{col}** kolonunu temizle ({count} yer tutucu)",
                value=True,
                key=f"placeholder_{col}",
            )

# -- Aykiri Degerler
with st.expander("Aykiri Deger Yonetimi"):
    outlier_issues = issues.get("outliers", {})
    outlier_settings = {}
    if not outlier_issues:
        st.write("Aykiri deger tespit edilmedi.")
    else:
        for col, info in outlier_issues.items():
            c1, c2 = st.columns([2, 2])
            with c1:
                do_outlier = st.checkbox(
                    f"**{col}** aykiri degerlerini isle ({info['count']} adet)",
                    value=False,
                    key=f"outlier_do_{col}",
                )
            with c2:
                method = st.selectbox(
                    f"{col} yontemi",
                    ["iqr", "winsorize"],
                    key=f"outlier_method_{col}",
                    label_visibility="collapsed",
                    format_func=lambda x: {"iqr": "IQR Sinirlama", "winsorize": "Winsorlama"}[x],
                )
            if do_outlier:
                outlier_settings[col] = method

# ── Temizligi Uygula ────────────────────────────────────────────────
st.divider()

# Strateji mapping: Turkce -> engine
_numeric_strategy_map = {"atla": "skip", "ortalama": "mean", "medyan": "median", "sifir": "zero", "satirlari_sil": "drop_rows"}
_cat_strategy_map = {"atla": "skip", "mod": "mode", "yer_tutucu": "placeholder", "satirlari_sil": "drop_rows"}
_case_map = {"yok": "none", "kucuk_harf": "lower", "buyuk_harf": "upper", "baslik": "title"}

if st.button("Temizligi Uygula", type="primary", use_container_width=True):
    # Orijinal veriye sifirla
    engine.df = engine.original_df.copy()
    engine.log = []

    # 1. Yuksek eksiklik oranli kolonlari sil
    if missing_cols:
        engine.drop_high_missing_columns(threshold=drop_threshold / 100)

    # 2. Yer tutucu temizligi (eksik deger isleminden once, NaN olsunlar)
    for col, do_it in placeholder_settings.items():
        if do_it and col in engine.df.columns:
            engine.replace_placeholders(col)

    # 3. Eksik degerler
    for col, strategy_tr in missing_settings.items():
        is_numeric = col in numeric_cols
        if is_numeric:
            strategy = _numeric_strategy_map[strategy_tr]
        else:
            strategy = _cat_strategy_map[strategy_tr]
        if strategy == "skip" or col not in engine.df.columns:
            continue
        if is_numeric:
            engine.handle_missing_numeric(col, strategy)
        else:
            engine.handle_missing_categorical(col, strategy)

    # 4. Tekrar eden satirlar
    if remove_dups:
        engine.remove_duplicates()

    # 5. Tip donusumleri
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

    # 6. Metin temizleme
    if text_cols:
        case_eng = _case_map[case_option]
        for col in selected_text_cols:
            if col not in engine.df.columns:
                continue
            if engine.df[col].dtype != "object":
                continue
            if do_trim:
                engine.trim_whitespace(col)
            if do_extra_spaces:
                engine.remove_extra_spaces(col)
            if case_eng != "none":
                engine.change_case(col, case_eng)
            if do_punctuation:
                engine.remove_punctuation(col)

    # 7. Aykiri degerler
    for col, method in outlier_settings.items():
        if col in engine.df.columns:
            engine.cap_outliers(col, method)

    st.session_state.cleaned = True
    st.rerun()

# ── Sonuclar ─────────────────────────────────────────────────────────
if st.session_state.cleaned and engine.log:
    st.header("Temizlik Sonuclari")

    metrics = engine.get_metrics()

    m_cols = st.columns(4)
    with m_cols[0]:
        st.metric("Onceki Satir Sayisi", metrics["rows_before"])
    with m_cols[1]:
        st.metric("Sonraki Satir Sayisi", metrics["rows_after"], delta=-metrics["rows_removed"] if metrics["rows_removed"] else None)
    with m_cols[2]:
        st.metric("Onceki Eksik Deger", metrics["missing_before"])
    with m_cols[3]:
        st.metric("Sonraki Eksik Deger", metrics["missing_after"], delta=-(metrics["missing_before"] - metrics["missing_after"]) if metrics["missing_before"] != metrics["missing_after"] else None)

    st.subheader("Donusum Kaydi")
    summary_df = engine.get_summary_df()
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.subheader("Temizlenmis Veri Onizleme")
    st.dataframe(engine.df.head(100), use_container_width=True, height=300)

    # ── Indirmeler ───────────────────────────────────────────────────
    st.header("Indir")

    col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)

    with col_dl1:
        csv_buffer = io.BytesIO()
        engine.df.to_csv(csv_buffer, index=False)
        st.download_button(
            "Temiz Veri (CSV)",
            csv_buffer.getvalue(),
            "temizlenmis_veri.csv",
            "text/csv",
            use_container_width=True,
        )

    with col_dl2:
        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine="xlsxwriter") as writer:
            engine.df.to_excel(writer, index=False, sheet_name="Temizlenmis Veri")
        st.download_button(
            "Temiz Veri (Excel)",
            xlsx_buffer.getvalue(),
            "temizlenmis_veri.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col_dl3:
        summary_csv = io.BytesIO()
        summary_df.to_csv(summary_csv, index=False)
        st.download_button(
            "Rapor (CSV)",
            summary_csv.getvalue(),
            "temizlik_raporu.csv",
            "text/csv",
            use_container_width=True,
        )

    with col_dl4:
        summary_xlsx = io.BytesIO()
        with pd.ExcelWriter(summary_xlsx, engine="xlsxwriter") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Temizlik Raporu")
        st.download_button(
            "Rapor (Excel)",
            summary_xlsx.getvalue(),
            "temizlik_raporu.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

elif st.session_state.cleaned and not engine.log:
    st.info("Hicbir temizleme islemi uygulanmadi. Yukaridaki secenekleri ayarlayip tekrar deneyin.")
