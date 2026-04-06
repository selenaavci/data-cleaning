import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CleaningAction:
    column: str
    issue_type: str
    action: str
    affected_rows: int
    status: str = "Uygulandi"


class CleaningEngine:
    """Tum veri temizleme islemlerini gerceklestiren cekirdek motor."""

    def __init__(self, df: pd.DataFrame):
        self.original_df = df.copy()
        self.df = df.copy()
        self.log: list[CleaningAction] = []
        self.original_row_count = len(df)

    # ── Tespit / Analiz ──────────────────────────────────────────────

    def detect_issues(self) -> dict[str, Any]:
        """Veri setini tarayip tespit edilen sorunlarin ozetini dondurur."""
        issues: dict[str, Any] = {}

        # Eksik degerler
        missing = self.df.isnull().sum()
        missing = missing[missing > 0]
        if not missing.empty:
            issues["missing_values"] = {
                col: {"count": int(cnt), "pct": round(cnt / len(self.df) * 100, 1)}
                for col, cnt in missing.items()
            }

        # Tekrar eden satirlar
        dup_count = int(self.df.duplicated().sum())
        if dup_count > 0:
            issues["duplicates"] = dup_count

        # Tip sorunlari - metin olarak saklanan sayisal/tarih kolonlari
        type_issues = {}
        for col in self.df.select_dtypes(include=["object"]).columns:
            numeric_count = pd.to_numeric(self.df[col], errors="coerce").notna().sum()
            non_null = self.df[col].notna().sum()
            if non_null > 0 and numeric_count / non_null > 0.5:
                type_issues[col] = "numeric_as_text"
            else:
                with pd.option_context("mode.chained_assignment", None):
                    date_count = pd.to_datetime(self.df[col], errors="coerce", dayfirst=True, format="mixed").notna().sum()
                if non_null > 0 and date_count / non_null > 0.5:
                    type_issues[col] = "date_as_text"
        if type_issues:
            issues["type_issues"] = type_issues

        # Metin sorunlari - bosluklar
        text_issues = {}
        for col in self.df.select_dtypes(include=["object"]).columns:
            series = self.df[col].dropna()
            if series.empty:
                continue
            ws_count = int((series != series.str.strip()).sum())
            extra_space = int(series.str.contains(r"  +", regex=True, na=False).sum())
            if ws_count > 0 or extra_space > 0:
                text_issues[col] = {"whitespace": ws_count, "extra_spaces": extra_space}
        if text_issues:
            issues["text_issues"] = text_issues

        # Gecersiz / yer tutucu degerler
        placeholders = {"n/a", "na", "N/A", "NA", "-", "--", "null", "NULL",
                        "none", "None", "unknown", "Unknown", ".", "?", "undefined"}
        placeholder_issues = {}
        for col in self.df.select_dtypes(include=["object"]).columns:
            series = self.df[col].dropna()
            hits = int(series.isin(placeholders).sum())
            if hits > 0:
                placeholder_issues[col] = hits
        if placeholder_issues:
            issues["placeholder_values"] = placeholder_issues

        # Sayisal kolonlarda aykiri degerler (IQR)
        outlier_issues = {}
        for col in self.df.select_dtypes(include=["number"]).columns:
            series = self.df[col].dropna()
            if len(series) < 10:
                continue
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier_count = int(((series < lower) | (series > upper)).sum())
            if outlier_count > 0:
                outlier_issues[col] = {
                    "count": outlier_count,
                    "lower_bound": round(float(lower), 2),
                    "upper_bound": round(float(upper), 2),
                }
        if outlier_issues:
            issues["outliers"] = outlier_issues

        return issues

    # ── Temizleme Islemleri ──────────────────────────────────────────

    def handle_missing_numeric(self, col: str, strategy: str) -> None:
        """Sayisal kolondaki eksik degerleri doldur veya satirlari sil."""
        if col not in self.df.columns:
            return
        missing_count = int(self.df[col].isnull().sum())
        if missing_count == 0:
            return

        action_map = {
            "mean": "Ortalama ile dolduruldu",
            "median": "Medyan ile dolduruldu",
            "zero": "Sifir ile dolduruldu",
            "drop_rows": "Satirlar silindi",
        }

        if strategy == "mean":
            val = self.df[col].mean()
            self.df[col] = self.df[col].fillna(val)
        elif strategy == "median":
            val = self.df[col].median()
            self.df[col] = self.df[col].fillna(val)
        elif strategy == "zero":
            self.df[col] = self.df[col].fillna(0)
        elif strategy == "drop_rows":
            self.df = self.df.dropna(subset=[col]).reset_index(drop=True)

        self.log.append(CleaningAction(col, "Eksik Deger", action_map.get(strategy, strategy), missing_count))

    def handle_missing_categorical(self, col: str, strategy: str, placeholder: str = "Bilinmiyor") -> None:
        """Kategorik kolondaki eksik degerleri doldur."""
        if col not in self.df.columns:
            return
        missing_count = int(self.df[col].isnull().sum())
        if missing_count == 0:
            return

        if strategy == "mode":
            mode_val = self.df[col].mode()
            if not mode_val.empty:
                self.df[col] = self.df[col].fillna(mode_val.iloc[0])
            action_desc = "En sik deger ile dolduruldu"
        elif strategy == "placeholder":
            self.df[col] = self.df[col].fillna(placeholder)
            action_desc = f"'{placeholder}' ile dolduruldu"
        elif strategy == "drop_rows":
            self.df = self.df.dropna(subset=[col]).reset_index(drop=True)
            action_desc = "Satirlar silindi"
        else:
            action_desc = strategy

        self.log.append(CleaningAction(col, "Eksik Deger", action_desc, missing_count))

    def remove_duplicates(self) -> int:
        """Tekrar eden satirlari kaldir."""
        dup_count = int(self.df.duplicated().sum())
        if dup_count > 0:
            self.df = self.df.drop_duplicates().reset_index(drop=True)
            self.log.append(CleaningAction("Tumu", "Tekrar Eden Satir", "Tekrar eden satirlar kaldirildi", dup_count))
        return dup_count

    def convert_to_numeric(self, col: str) -> None:
        """Metin kolonunu sayisala donustur."""
        if col not in self.df.columns:
            return
        before = self.df[col].copy()
        self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
        changed = int((before.astype(str) != self.df[col].astype(str)).sum())
        self.log.append(CleaningAction(col, "Tip Donusumu", "Sayisala donusturuldu", changed))

    def convert_to_datetime(self, col: str) -> None:
        """Metin kolonunu tarihe donustur."""
        if col not in self.df.columns:
            return
        before_null = int(self.df[col].isnull().sum())
        self.df[col] = pd.to_datetime(self.df[col], errors="coerce", dayfirst=True)
        after_null = int(self.df[col].isnull().sum())
        converted = len(self.df) - after_null
        self.log.append(CleaningAction(col, "Tip Donusumu", "Tarihe donusturuldu", converted))

    def normalize_boolean(self, col: str) -> None:
        """Boolean benzeri degerleri (Evet/Hayir, True/False, 1/0) True/False'a normalize et."""
        if col not in self.df.columns:
            return
        mapping = {
            "yes": True, "no": False,
            "true": True, "false": False,
            "1": True, "0": False,
            "evet": True, "hayır": False,
            "hayir": False,
        }
        original = self.df[col].copy()
        self.df[col] = self.df[col].astype(str).str.strip().str.lower().map(mapping)
        changed = int((original.astype(str) != self.df[col].astype(str)).sum())
        self.log.append(CleaningAction(col, "Tip Donusumu", "Boolean'a normalize edildi", changed))

    def trim_whitespace(self, col: str) -> None:
        """Bastaki ve sondaki bosluklari kirp."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        self.df[col] = self.df[col].astype(str).str.strip()
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Metin Temizleme", "Bosluklar kirpildi", changed))

    def remove_extra_spaces(self, col: str) -> None:
        """Birden fazla bosluklari teke indir."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        self.df[col] = self.df[col].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Metin Temizleme", "Fazla bosluklar silindi", changed))

    def change_case(self, col: str, case: str) -> None:
        """Metin harflerini degistir: 'lower', 'upper', 'title'."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        case_labels = {"lower": "Kucuk harfe cevirildi", "upper": "Buyuk harfe cevirildi", "title": "Baslik formatina cevirildi"}
        if case == "lower":
            self.df[col] = self.df[col].astype(str).str.lower()
        elif case == "upper":
            self.df[col] = self.df[col].astype(str).str.upper()
        elif case == "title":
            self.df[col] = self.df[col].astype(str).str.title()
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Metin Temizleme", case_labels.get(case, case), changed))

    def remove_punctuation(self, col: str) -> None:
        """Noktalama isaretlerini kaldir."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        self.df[col] = self.df[col].astype(str).str.replace(r"[^\w\s]", "", regex=True)
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Metin Temizleme", "Noktalama isaretleri silindi", changed))

    def replace_placeholders(self, col: str) -> None:
        """Yaygin yer tutucu degerleri NaN ile degistir."""
        if col not in self.df.columns:
            return
        placeholders = {"n/a", "na", "N/A", "NA", "-", "--", "null", "NULL",
                        "none", "None", "unknown", "Unknown", ".", "?", "undefined",
                        "nan", "NaN"}
        mask = self.df[col].astype(str).str.strip().isin(placeholders)
        count = int(mask.sum())
        if count > 0:
            self.df.loc[mask, col] = np.nan
            self.log.append(CleaningAction(col, "Gecersiz Deger", "Yer tutucular NaN ile degistirildi", count))

    def cap_outliers(self, col: str, method: str = "iqr") -> None:
        """IQR veya winsorlama yontemiyle aykiri degerleri sinirla."""
        if col not in self.df.columns:
            return
        series = self.df[col].dropna()
        if len(series) < 10:
            return

        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return

        if method == "iqr":
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        else:  # winsorize
            lower, upper = series.quantile(0.05), series.quantile(0.95)

        outlier_mask = (self.df[col] < lower) | (self.df[col] > upper)
        count = int(outlier_mask.sum())
        if count > 0:
            self.df[col] = self.df[col].clip(lower=lower, upper=upper)
            method_label = "IQR sinirlama" if method == "iqr" else "Winsorlama"
            self.log.append(CleaningAction(col, "Aykiri Deger", method_label, count))

    def drop_high_missing_columns(self, threshold: float = 0.8) -> None:
        """Eksiklik orani esigi asan kolonlari sil."""
        for col in list(self.df.columns):
            ratio = self.df[col].isnull().sum() / len(self.df)
            if ratio >= threshold:
                self.df = self.df.drop(columns=[col])
                self.log.append(CleaningAction(col, "Yuksek Eksiklik Orani", f"Kolon silindi (>{threshold*100:.0f}% eksik)", len(self.df)))

    # ── Ozet ve Disari Aktarma ───────────────────────────────────────

    def get_summary_df(self) -> pd.DataFrame:
        """Temizleme logunu DataFrame olarak dondur."""
        if not self.log:
            return pd.DataFrame(columns=["Kolon", "Sorun Tipi", "Uygulanan Islem", "Etkilenen Satir", "Durum"])
        return pd.DataFrame([
            {
                "Kolon": a.column,
                "Sorun Tipi": a.issue_type,
                "Uygulanan Islem": a.action,
                "Etkilenen Satir": a.affected_rows,
                "Durum": a.status,
            }
            for a in self.log
        ])

    def get_metrics(self) -> dict[str, Any]:
        """Oncesi/sonrasi metriklerini dondur."""
        return {
            "rows_before": self.original_row_count,
            "rows_after": len(self.df),
            "rows_removed": self.original_row_count - len(self.df),
            "cols_before": len(self.original_df.columns),
            "cols_after": len(self.df.columns),
            "missing_before": int(self.original_df.isnull().sum().sum()),
            "missing_after": int(self.df.isnull().sum().sum()),
            "actions_applied": len(self.log),
        }
