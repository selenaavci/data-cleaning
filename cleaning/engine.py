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
    status: str = "Applied"


class CleaningEngine:
    """Core engine that performs all data cleaning operations."""

    def __init__(self, df: pd.DataFrame):
        self.original_df = df.copy()
        self.df = df.copy()
        self.log: list[CleaningAction] = []
        self.original_row_count = len(df)

    # ── Detection / Analysis ─────────────────────────────────────────

    def detect_issues(self) -> dict[str, Any]:
        """Scan the dataframe and return a summary of detected issues."""
        issues: dict[str, Any] = {}

        # Missing values
        missing = self.df.isnull().sum()
        missing = missing[missing > 0]
        if not missing.empty:
            issues["missing_values"] = {
                col: {"count": int(cnt), "pct": round(cnt / len(self.df) * 100, 1)}
                for col, cnt in missing.items()
            }

        # Duplicates
        dup_count = int(self.df.duplicated().sum())
        if dup_count > 0:
            issues["duplicates"] = dup_count

        # Type issues – numeric-looking text columns
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

        # Text issues – leading/trailing whitespace, extra spaces
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

        # Invalid / placeholder values
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

        # Outliers in numeric columns (IQR)
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

    # ── Cleaning Operations ──────────────────────────────────────────

    def handle_missing_numeric(self, col: str, strategy: str) -> None:
        """Fill or drop missing values in a numeric column."""
        if col not in self.df.columns:
            return
        missing_count = int(self.df[col].isnull().sum())
        if missing_count == 0:
            return

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

        self.log.append(CleaningAction(col, "Missing Value", f"Filled with {strategy}" if strategy != "drop_rows" else "Dropped rows", missing_count))

    def handle_missing_categorical(self, col: str, strategy: str, placeholder: str = "Unknown") -> None:
        """Fill missing values in a categorical column."""
        if col not in self.df.columns:
            return
        missing_count = int(self.df[col].isnull().sum())
        if missing_count == 0:
            return

        if strategy == "mode":
            mode_val = self.df[col].mode()
            if not mode_val.empty:
                self.df[col] = self.df[col].fillna(mode_val.iloc[0])
        elif strategy == "placeholder":
            self.df[col] = self.df[col].fillna(placeholder)
        elif strategy == "drop_rows":
            self.df = self.df.dropna(subset=[col]).reset_index(drop=True)

        action_desc = f"Filled with {strategy}" if strategy != "drop_rows" else "Dropped rows"
        if strategy == "placeholder":
            action_desc = f"Filled with '{placeholder}'"
        self.log.append(CleaningAction(col, "Missing Value", action_desc, missing_count))

    def remove_duplicates(self) -> int:
        """Remove duplicate rows. Returns number removed."""
        dup_count = int(self.df.duplicated().sum())
        if dup_count > 0:
            self.df = self.df.drop_duplicates().reset_index(drop=True)
            self.log.append(CleaningAction("All", "Duplicate Rows", "Removed duplicates", dup_count))
        return dup_count

    def convert_to_numeric(self, col: str) -> None:
        """Convert a text column to numeric."""
        if col not in self.df.columns:
            return
        before = self.df[col].copy()
        self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
        changed = int((before.astype(str) != self.df[col].astype(str)).sum())
        self.log.append(CleaningAction(col, "Type Conversion", "Converted to numeric", changed))

    def convert_to_datetime(self, col: str) -> None:
        """Convert a text column to datetime."""
        if col not in self.df.columns:
            return
        before_null = int(self.df[col].isnull().sum())
        self.df[col] = pd.to_datetime(self.df[col], errors="coerce", dayfirst=True)
        after_null = int(self.df[col].isnull().sum())
        converted = len(self.df) - after_null
        self.log.append(CleaningAction(col, "Type Conversion", "Converted to datetime", converted))

    def normalize_boolean(self, col: str) -> None:
        """Normalize boolean-like values (Yes/No, True/False, 1/0) to True/False."""
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
        self.log.append(CleaningAction(col, "Type Conversion", "Normalized to boolean", changed))

    def trim_whitespace(self, col: str) -> None:
        """Trim leading/trailing whitespace."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        self.df[col] = self.df[col].astype(str).str.strip()
        # Restore NaN
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Text Cleaning", "Trimmed whitespace", changed))

    def remove_extra_spaces(self, col: str) -> None:
        """Collapse multiple spaces into one."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        self.df[col] = self.df[col].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Text Cleaning", "Removed extra spaces", changed))

    def change_case(self, col: str, case: str) -> None:
        """Change text case: 'lower', 'upper', 'title'."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        if case == "lower":
            self.df[col] = self.df[col].astype(str).str.lower()
        elif case == "upper":
            self.df[col] = self.df[col].astype(str).str.upper()
        elif case == "title":
            self.df[col] = self.df[col].astype(str).str.title()
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Text Cleaning", f"Changed to {case}case", changed))

    def remove_punctuation(self, col: str) -> None:
        """Remove punctuation characters from text."""
        if col not in self.df.columns:
            return
        series = self.df[col].copy()
        self.df[col] = self.df[col].astype(str).str.replace(r"[^\w\s]", "", regex=True)
        self.df.loc[series.isna(), col] = np.nan
        changed = int((series.fillna("") != self.df[col].fillna("")).sum())
        if changed > 0:
            self.log.append(CleaningAction(col, "Text Cleaning", "Removed punctuation", changed))

    def replace_placeholders(self, col: str) -> None:
        """Replace common placeholder values with NaN."""
        if col not in self.df.columns:
            return
        placeholders = {"n/a", "na", "N/A", "NA", "-", "--", "null", "NULL",
                        "none", "None", "unknown", "Unknown", ".", "?", "undefined",
                        "nan", "NaN"}
        mask = self.df[col].astype(str).str.strip().isin(placeholders)
        count = int(mask.sum())
        if count > 0:
            self.df.loc[mask, col] = np.nan
            self.log.append(CleaningAction(col, "Invalid Values", "Replaced placeholders with NaN", count))

    def cap_outliers(self, col: str, method: str = "iqr") -> None:
        """Cap outliers using IQR method or winsorization."""
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
            method_label = "IQR capping" if method == "iqr" else "Winsorization"
            self.log.append(CleaningAction(col, "Outlier", method_label, count))

    def drop_high_missing_columns(self, threshold: float = 0.8) -> None:
        """Drop columns where missing ratio exceeds threshold."""
        for col in list(self.df.columns):
            ratio = self.df[col].isnull().sum() / len(self.df)
            if ratio >= threshold:
                self.df = self.df.drop(columns=[col])
                self.log.append(CleaningAction(col, "High Missing Rate", f"Dropped column (>{threshold*100:.0f}% missing)", len(self.df)))

    # ── Summary & Export ─────────────────────────────────────────────

    def get_summary_df(self) -> pd.DataFrame:
        """Return the cleaning log as a DataFrame."""
        if not self.log:
            return pd.DataFrame(columns=["Column", "Issue Type", "Action", "Affected Rows", "Status"])
        return pd.DataFrame([
            {
                "Column": a.column,
                "Issue Type": a.issue_type,
                "Action": a.action,
                "Affected Rows": a.affected_rows,
                "Status": a.status,
            }
            for a in self.log
        ])

    def get_metrics(self) -> dict[str, Any]:
        """Return before/after metrics."""
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
