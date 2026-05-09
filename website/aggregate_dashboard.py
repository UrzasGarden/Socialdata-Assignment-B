"""
Build dashboard_aggregation.json — the static, browser-loadable data layer for
the interactive dashboard ("Bowl" of the Martini Glass).

Source:  INDKP107_komplet.csv (~7.7M rows, sep=';', utf-8 with BOM)
Output:  dashboard_aggregation.json

Pipeline:
  1. Load only the columns we need with explicit dtypes.
  2. Filter to ENHED = "Gennemsnit for alle personer (kr.)" and to the
     wages/salary line ("4 Wages/salary"). 
  3. Adjust nominal DKK -> 2024 DKK using hardcoded Danish CPI multipliers.
  4. Pivot Men / Women rows side-by-side and compute Gap = Men - Women.
  5. Group by (year, area, education) and write a nested JSON document
     split into Region_Data and Municipality_Data, plus a Metadata block.

The output structure is shaped for direct lookup in JS:
    data.Data.Region_Data["2024"]["Hovedstaden"]["Long tertiary"].Gap
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "INDKP107_komplet.csv"
if not CSV_PATH.exists():
    alt_csv_path = Path.home() / "Downloads" / "INDKP107_komplet.csv" / "INDKP107_komplet.csv"
    if alt_csv_path.exists():
        CSV_PATH = alt_csv_path
OUT_PATH = BASE_DIR / "dashboard_aggregation.json"

# Filter strings — must match the CSV exactly.
UNIT_AVG_ALL = "Gennemsnit for alle personer (kr.)"
UNIT_COUNT   = "Personer med indkomsttypen (antal)"
COUNTRY = "Hele landet"

# Income types to surface in the dashboard. Keys are the JS-friendly labels
# (used as JSON keys + dropdown options); values are the exact INDKOMSTTYPE
# strings as they appear in INDKP107. Order matters — first item is default.
INCOME_TYPES = {
    "Disposable":         "1 Disponibel indkomst (2+30-31-32-35)",
    "Total before tax":   "2 Indkomst i alt, før skatter mv. (3+7+22+26+29)",
    "Wages":              "4 Løn",
    "Public transfers":   "7 Offentlige overførsler (8+14+19)",
    "Public pensions":    "19 Offentlige pensioner(20+21)",
    "Private pensions":   "22 Private pensioner(23+24+25)",
    "Taxable income":     "Skattepligtig indkomst",
}

# CPI multipliers convert nominal year-Y kroner into 2024 kroner.
# Approximated from Statistics Denmark's PRIS113 (Forbrugerprisindeks);
# multiplier = CPI_2024 / CPI_year, so 2024 itself is exactly 1.000.
CPI_2024_MULTIPLIER = {
    2004: 1.459, 2005: 1.434, 2006: 1.407, 2007: 1.384,
    2008: 1.337, 2009: 1.320, 2010: 1.288, 2011: 1.254,
    2012: 1.224, 2013: 1.214, 2014: 1.206, 2015: 1.200,
    2016: 1.196, 2017: 1.183, 2018: 1.174, 2019: 1.164,
    2020: 1.159, 2021: 1.137, 2022: 1.052, 2023: 1.012,
    2024: 1.000,
}

# Map raw Danish UDDNIV codes (with their messy trailing whitespace) to clean,
# JS-friendly English labels. Anything not in the map is dropped.
EDUCATION_LABELS = {
    "10 GRUNDSKOLE": "Primary school",
    "20+25 GYMNASIALE UDDANNELSER": "Gymnasium",
    "35 ERHVERVSUDDANNELSER": "Vocational Education",
    "40 KORTE VIDEREGÅENDE UDDANNELSER": "Short Higher Education",
    "50+60 MELLEMLANGE VIDEREGÅENDE UDDANNELSER INKL. BACHELOR": "Medium Higher Education",
    "65 LANGE VIDEREGÅENDE UDDANNELSER": "Long Higher Education",
}


# ---------------------------------------------------------------------------
# Step 1 — Load & filter
# ---------------------------------------------------------------------------
def load_filtered() -> pd.DataFrame:
    print(f"[1/5] Loading {CSV_PATH.name} ...")
    chunks = pd.read_csv(
        CSV_PATH,
        sep=";",
        encoding="utf-8-sig",
        usecols=["OMRÅDE", "ENHED", "KOEN", "UDDNIV", "INDKOMSTTYPE", "TID", "INDHOLD"],
        dtype={
            "OMRÅDE": "string",
            "ENHED": "string",
            "KOEN": "string",
            "UDDNIV": "string",
            "INDKOMSTTYPE": "string",
            "TID": "int16",
        },
        chunksize=250_000,
    )

    kept = []
    raw_rows = 0
    for chunk in chunks:
        raw_rows += len(chunk)

        # Strip whitespace from text values — UDDNIV in particular has
        # trailing spaces on some labels.
        for col in ["OMRÅDE", "ENHED", "KOEN", "UDDNIV", "INDKOMSTTYPE"]:
            chunk[col] = chunk[col].str.strip()

        chunk["INDHOLD"] = pd.to_numeric(chunk["INDHOLD"], errors="coerce")
        mask = (
            (chunk["ENHED"].isin([UNIT_AVG_ALL, UNIT_COUNT]))
            & (chunk["INDKOMSTTYPE"].isin(INCOME_TYPES.values()))
            & (chunk["KOEN"].isin(["Mænd", "Kvinder"]))   # gap needs M & F only
        )
        filtered = chunk.loc[mask].dropna(subset=["INDHOLD"]).copy()
        if not filtered.empty:
            kept.append(filtered)

    df = pd.concat(kept, ignore_index=True)
    print(f"      raw rows: {raw_rows:,}")
    print(f"      after filter (Avg / M+F only): {len(df):,}")
    return df


# ---------------------------------------------------------------------------
# Step 2 — Inflation adjustment
# ---------------------------------------------------------------------------
def adjust_inflation(df: pd.DataFrame) -> pd.DataFrame:
    print("[2/5] Adjusting to 2024 DKK ...")
    missing = sorted(set(df["TID"].unique()) - set(CPI_2024_MULTIPLIER))
    if missing:
        print(f"      WARNING: no CPI multiplier for years {missing}; using 1.0")

    # Only apply CPI to average-kroner rows. Count rows are headcounts and
    # must pass through unchanged.
    df["CPI_MULT"] = df["TID"].map(CPI_2024_MULTIPLIER).fillna(1.0).astype(float)
    is_avg = df["ENHED"] == UNIT_AVG_ALL
    df["Adjusted_Value"] = df["INDHOLD"].astype(float)
    df.loc[is_avg, "Adjusted_Value"] = df.loc[is_avg, "INDHOLD"] * df.loc[is_avg, "CPI_MULT"]
    df["Adjusted_Value"] = df["Adjusted_Value"].round().astype("int64")
    return df


# ---------------------------------------------------------------------------
# Step 3 — Pivot Men/Women side-by-side, compute Gap
# ---------------------------------------------------------------------------
def pivot_gender(df: pd.DataFrame) -> pd.DataFrame:
    print("[3/5] Pivoting M/F and computing income gap + headcount ...")

    # Map raw UDDNIV -> clean English label, drop "Uoplyst" and unknowns.
    df["Education"] = df["UDDNIV"].map(EDUCATION_LABELS)

    inv_income = {v: k for k, v in INCOME_TYPES.items()}
    df["IncomeTypeLabel"] = df["INDKOMSTTYPE"].map(inv_income)

    df = df.dropna(subset=["Education", "IncomeTypeLabel"])

    # Tag each row with a "metric" combining unit + gender so we can pivot
    # avg-income and headcount columns side-by-side in one shot.
    metric_map = {
        (UNIT_AVG_ALL, "Mænd"):    "Avg_M",
        (UNIT_AVG_ALL, "Kvinder"): "Avg_F",
        (UNIT_COUNT,   "Mænd"):    "Cnt_M",
        (UNIT_COUNT,   "Kvinder"): "Cnt_F",
    }
    df["Metric"] = list(zip(df["ENHED"], df["KOEN"]))
    df["Metric"] = df["Metric"].map(metric_map)
    df = df.dropna(subset=["Metric"])

    grouped = (
        df.groupby(["TID", "OMRÅDE", "Education", "IncomeTypeLabel", "Metric"], observed=True)["Adjusted_Value"]
        .mean()
        .round()
        .astype("int64")
        .unstack("Metric")
        .reset_index()
    )

    # Need both genders' average income for a meaningful gap. Headcount is
    # optional — fill missing with 0.
    grouped = grouped.dropna(subset=["Avg_M", "Avg_F"])
    grouped = grouped.rename(columns={"Avg_M": "Men", "Avg_F": "Women"})
    grouped["Men"] = grouped["Men"].astype("int64")
    grouped["Women"] = grouped["Women"].astype("int64")
    grouped["Gap"] = grouped["Men"] - grouped["Women"]

    cnt_m = grouped["Cnt_M"].fillna(0) if "Cnt_M" in grouped.columns else 0
    cnt_f = grouped["Cnt_F"].fillna(0) if "Cnt_F" in grouped.columns else 0
    grouped["Men_Count"]   = (cnt_m if hasattr(cnt_m, "astype") else pd.Series([cnt_m] * len(grouped))).astype("int64")
    grouped["Women_Count"] = (cnt_f if hasattr(cnt_f, "astype") else pd.Series([cnt_f] * len(grouped))).astype("int64")
    grouped["Count"] = grouped["Men_Count"] + grouped["Women_Count"]

    print(f"      pivoted rows: {len(grouped):,}")
    return grouped


# ---------------------------------------------------------------------------
# Step 4 — Build the nested dictionary
# ---------------------------------------------------------------------------
def classify_area(area: str) -> str:
    """Returns 'region', 'landsdel', 'country', or 'municipality'."""
    if area == COUNTRY:
        return "country"
    if area.startswith("Region "):
        return "region"
    if area.startswith("Landsdel "):
        return "landsdel"
    return "municipality"


def build_nested(grouped: pd.DataFrame) -> tuple[dict, list, list, list]:
    print("[4/5] Building nested national / subregions / region / municipality dictionaries ...")

    # Strip rollup prefixes so JS keys match GeoJSON labels.
    grouped["AreaKind"] = grouped["OMRÅDE"].map(classify_area)
    grouped["AreaName"] = grouped["OMRÅDE"].str.replace(r"^(Region|Landsdel)\s+", "", regex=True)

    data_by_income = {
        k: {
            "National_Data": {},
            "Landsdel_Data": {},
            "Region_Data": {},
            "Municipality_Data": {},
        }
        for k in INCOME_TYPES.keys()
    }

    # "Hele landet" rows go into National_Data keyed by year -> education.
    # No area sub-key needed since there is only one national figure.
    country_subset = grouped[grouped["AreaKind"] == "country"]
    for (year, _area, edu, inc), row in country_subset.set_index(
        ["TID", "AreaName", "Education", "IncomeTypeLabel"]
    ).iterrows():
        data_by_income[inc]["National_Data"].setdefault(str(year), {})[edu] = {
            "Men": int(row["Men"]),
            "Women": int(row["Women"]),
            "Gap": int(row["Gap"]),
            "Count": int(row["Count"]),
        }

    for kind, target_key in (
        ("landsdel", "Landsdel_Data"),
        ("region", "Region_Data"),
        ("municipality", "Municipality_Data"),
    ):
        subset = grouped[grouped["AreaKind"] == kind]
        for (year, area, edu, inc), row in subset.set_index(
            ["TID", "AreaName", "Education", "IncomeTypeLabel"]
        ).iterrows():
            year_key = str(year)
            data_by_income[inc][target_key].setdefault(year_key, {}).setdefault(area, {})[edu] = {
                "Men": int(row["Men"]),
                "Women": int(row["Women"]),
                "Gap": int(row["Gap"]),
                "Count": int(row["Count"]),
                "Men_Count": int(row["Men_Count"]),
                "Women_Count": int(row["Women_Count"]),
            }

    landsdele = sorted(grouped.loc[grouped["AreaKind"] == "landsdel", "AreaName"].unique())
    regions = sorted(grouped.loc[grouped["AreaKind"] == "region", "AreaName"].unique())
    munis = sorted(grouped.loc[grouped["AreaKind"] == "municipality", "AreaName"].unique())
    print(f"      subregions: {len(landsdele)}  |  regions: {len(regions)}  |  municipalities: {len(munis)}")
    return data_by_income, landsdele, regions, munis


# ---------------------------------------------------------------------------
# Step 5 — Write JSON
# ---------------------------------------------------------------------------
def write_json(grouped: pd.DataFrame,
               data_by_income: dict,
               landsdele: list,
               regions: list,
               munis: list) -> None:
    print(f"[5/5] Writing {OUT_PATH.name} ...")
    payload = {
        "Metadata": {
            "Updated_at": date.today().isoformat(),
            "Source": "Statistics Denmark — INDKP107",
            "Income_Types": list(INCOME_TYPES.keys()),
            "Unit": "Average per person, 2024 DKK (CPI-adjusted)",
            "Base_Currency_Year": 2024,
            "Subregions_Included": landsdele,
            "Regions_Included": regions,
            "Municipalities_Included": munis,
            "Education_Levels": list(EDUCATION_LABELS.values()),
            "Years_Available": sorted(int(y) for y in grouped["TID"].unique()),
        },
        "Data": data_by_income,
    }

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"      wrote {OUT_PATH.name} ({size_kb:,.1f} KB)")


# ---------------------------------------------------------------------------
def main() -> None:
    df = load_filtered()
    df = adjust_inflation(df)
    grouped = pivot_gender(df)
    national_data, landsdele, regions, munis = build_nested(grouped)
    write_json(grouped, national_data, landsdele, regions, munis)
    print("Done.")


if __name__ == "__main__":
    main()
