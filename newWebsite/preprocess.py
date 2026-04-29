"""
INDKP107 preprocessing pipeline.

Reads the ~7.7M-row INDKP107_komplet.csv from Statistics Denmark, filters it
down to the slices we need for the "Stem" of the data story, adjusts all
income values to 2024 DKK using Danish CPI multipliers, and renders three
PNG charts styled for the dark glassmorphism front-end.

Output: charts/chart1_time.png, chart2_education.png, chart3_region.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "INDKP107_komplet.csv"
OUT_DIR = BASE_DIR / "charts"
OUT_DIR.mkdir(exist_ok=True)

# Match the CSS accent palette so chart colors blend with the UI.
ACCENT_BLUE = "#3b82f6"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_PINK = "#ec4899"
TEXT_COLOR = "#e2e8f0"
GRID_COLOR = "#ffffff"

# Filter values used throughout. Strings exactly as they appear in the CSV.
UNIT_AVG_ALL = "Gennemsnit for alle personer (kr.)"
INCOME_TYPE = "1 Disponibel indkomst (2+30-31-32-35)"
GENDER_TOTAL = "Mænd og kvinder i alt"
COUNTRY = "Hele landet"

# ---------------------------------------------------------------------------
# CPI multipliers — convert nominal DKK in year Y to real DKK in 2024.
# Approximated from Statistics Denmark Forbrugerprisindeks (PRIS113), with
# 2024 as the base year (multiplier = CPI_2024 / CPI_year).
# ---------------------------------------------------------------------------
CPI_2024_MULTIPLIER = {
    2004: 1.459,
    2005: 1.434,
    2006: 1.407,
    2007: 1.384,
    2008: 1.337,
    2009: 1.320,
    2010: 1.288,
    2011: 1.254,
    2012: 1.224,
    2013: 1.214,
    2014: 1.206,
    2015: 1.200,
    2016: 1.196,
    2017: 1.183,
    2018: 1.174,
    2019: 1.164,
    2020: 1.159,
    2021: 1.137,
    2022: 1.052,
    2023: 1.012,
    2024: 1.000,
}

# ---------------------------------------------------------------------------
# Dark-theme matplotlib defaults
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.facecolor": (0, 0, 0, 0),
    "axes.facecolor":   (0, 0, 0, 0),
    "savefig.facecolor": (0, 0, 0, 0),
    "savefig.transparent": True,
    "axes.edgecolor":   "#ffffff22",
    "axes.labelcolor":  TEXT_COLOR,
    "axes.titlecolor":  TEXT_COLOR,
    "xtick.color":      TEXT_COLOR,
    "ytick.color":      TEXT_COLOR,
    "text.color":       TEXT_COLOR,
    "grid.color":       GRID_COLOR,
    "grid.alpha":       0.08,
    "grid.linestyle":   "--",
    "axes.grid":        True,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.spines.left":  False,
    "axes.spines.bottom": False,
    "font.family":      "DejaVu Sans",
    "font.size":        11,
})


def kr_formatter(x, _pos):
    """Format kroner values: 612400 -> '612k kr.', 1_250_000 -> '1.25M kr.'"""
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.2f}M kr."
    if abs(x) >= 1_000:
        return f"{x / 1_000:.0f}k kr."
    return f"{int(x)} kr."


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_data() -> pd.DataFrame:
    """Stream the CSV with explicit dtypes; only keep the disposable-income,
    average-per-person slice so the working frame is small. Adds the
    Adjusted_Income column (2024 DKK) using the CPI multipliers above."""
    print(f"Loading {CSV_PATH.name} ...")
    df = pd.read_csv(
        CSV_PATH,
        sep=";",
        encoding="utf-8-sig",
        dtype={
            "OMRÅDE": "category",
            "ENHED": "category",
            "KOEN": "category",
            "UDDNIV": "category",
            "INDKOMSTTYPE": "category",
            "TID": "int16",
        },
    )

    for col in ["OMRÅDE", "ENHED", "KOEN", "UDDNIV", "INDKOMSTTYPE"]:
        df[col] = df[col].astype(str).str.strip().astype("category")

    df["INDHOLD"] = pd.to_numeric(df["INDHOLD"], errors="coerce")

    mask = (df["ENHED"] == UNIT_AVG_ALL) & (df["INDKOMSTTYPE"] == INCOME_TYPE)
    df = df.loc[mask].dropna(subset=["INDHOLD"]).copy()

    # Inflation-adjust to 2024 DKK. Years outside the table fall back to 1.0
    # so we never silently drop rows; surface a warning instead.
    missing_years = sorted(set(df["TID"].unique()) - set(CPI_2024_MULTIPLIER))
    if missing_years:
        print(f"  WARNING: no CPI multiplier for years {missing_years}; using 1.0")

    df["CPI_MULT"] = df["TID"].map(CPI_2024_MULTIPLIER).fillna(1.0).astype(float)
    df["Adjusted_Income"] = df["INDHOLD"] * df["CPI_MULT"]

    print(f"Filtered rows: {len(df):,} (years {df['TID'].min()}–{df['TID'].max()})")
    return df


# ---------------------------------------------------------------------------
# Chart 1: National income gap over time (line chart, real 2024 DKK)
# ---------------------------------------------------------------------------
def chart_time(df: pd.DataFrame) -> None:
    # National view: restrict to Hele landet and GENDER_TOTAL
    sub = df[(df["OMRÅDE"] == COUNTRY) & (df["KOEN"] == GENDER_TOTAL)]

    pivot = (
        sub.groupby(["TID", "UDDNIV"], observed=True)["Adjusted_Income"]
        .mean()
        .unstack("UDDNIV")
        .sort_index()
    )
    
    if "Uoplyst" in pivot.columns:
        pivot = pivot.drop(columns=["Uoplyst"])

    label_lookup = {
        "10 GRUNDSKOLE": "Primary school",
        "20+25 GYMNASIALE UDDANNELSER": "Gymnasium",
        "35 ERHVERVSUDDANNELSER": "Vocational Education",
        "40 KORTE VIDEREGÅENDE UDDANNELSER": "Short Higher Education",
        "50+60 MELLEMLANGE VIDEREGÅENDE UDDANNELSER INKL. BACHELOR": "Medium Higher Education",
        "65 LANGE VIDEREGÅENDE UDDANNELSER": "Long Higher Education",
    }
    
    # Sort columns by their latest value so the legend order matches the lines visually
    latest_year = pivot.index.max()
    sorted_cols = pivot.loc[latest_year].sort_values(ascending=False).index
    pivot = pivot[sorted_cols]

    fig, ax = plt.subplots(figsize=(11, 4.8), dpi=140)

    cmap = plt.cm.colors.LinearSegmentedColormap.from_list(
        "accents", [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_PINK]
    )
    
    for i, col in enumerate(pivot.columns):
        color = cmap(i / max(1, len(pivot.columns) - 1))
        label = label_lookup.get(col, col)
        ax.plot(
            pivot.index, pivot[col],
            marker="o", markersize=4, linewidth=2.5,
            color=color,
            label=label,
        )

    ax.set_title("Income by Education Over Time — Adjusted for Inflation (2024 DKK)",
                 pad=14, fontsize=12, color=TEXT_COLOR)
    ax.set_xlabel("Year")
    ax.set_ylabel("Average disposable income (2024 DKK)")
    ax.yaxis.set_major_formatter(FuncFormatter(kr_formatter))
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    ax.margins(x=0.02)

    fig.tight_layout()
    out = OUT_DIR / "chart1_time.png"
    fig.savefig(out, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(BASE_DIR)}")


# ---------------------------------------------------------------------------
# Chart 2: Income by education (horizontal bar, latest year, real DKK)
# ---------------------------------------------------------------------------
def chart_education(df: pd.DataFrame) -> None:
    latest = int(df["TID"].max())
    sub = df[
        (df["TID"] == latest)
        & (df["OMRÅDE"] == COUNTRY)
        & (df["KOEN"] == GENDER_TOTAL)
    ]

    by_edu = (
        sub.groupby("UDDNIV", observed=True)["Adjusted_Income"]
        .mean()
        .sort_values(ascending=True)
    )
    by_edu = by_edu[by_edu.index != "Uoplyst"]

    label_lookup = {
        "10 GRUNDSKOLE": "Primary school",
        "20+25 GYMNASIALE UDDANNELSER": "Gymnasium",
        "35 ERHVERVSUDDANNELSER": "Vocational Education",
        "40 KORTE VIDEREGÅENDE UDDANNELSER": "Short Higher Education",
        "50+60 MELLEMLANGE VIDEREGÅENDE UDDANNELSER INKL. BACHELOR": "Medium Higher Education",
        "65 LANGE VIDEREGÅENDE UDDANNELSER": "Long Higher Education",
    }
    labels = [label_lookup.get(idx, idx) for idx in by_edu.index]

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=140)

    cmap = plt.cm.colors.LinearSegmentedColormap.from_list(
        "accents", [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_PINK]
    )
    colors = [cmap(i / max(1, len(by_edu) - 1)) for i in range(len(by_edu))]

    bars = ax.barh(labels, by_edu.values, color=colors, edgecolor="none")

    for bar, val in zip(bars, by_edu.values):
        ax.text(
            bar.get_width() * 1.01, bar.get_y() + bar.get_height() / 2,
            kr_formatter(val, None),
            va="center", ha="left", fontsize=9, color=TEXT_COLOR,
        )

    ax.set_title(f"Income by Education — {latest}, Adjusted for Inflation (2024 DKK)",
                 pad=14, fontsize=12, color=TEXT_COLOR)
    ax.xaxis.set_major_formatter(FuncFormatter(kr_formatter))
    ax.set_xlabel("Average disposable income (2024 DKK)")
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.margins(x=0.15)

    fig.tight_layout()
    out = OUT_DIR / "chart2_education.png"
    fig.savefig(out, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(BASE_DIR)}")


# ---------------------------------------------------------------------------
# Chart 3: Regional distribution — top municipalities (latest year, real DKK)
# ---------------------------------------------------------------------------
def chart_region(df: pd.DataFrame) -> None:
    latest = int(df["TID"].max())
    sub = df[
        (df["TID"] == latest) 
        & (df["KOEN"] == GENDER_TOTAL)
        & (df["UDDNIV"] == "65 LANGE VIDEREGÅENDE UDDANNELSER")
    ]

    # Drop national + landsdel/region rollups so the chart shows municipalities.
    areas = sub["OMRÅDE"].astype(str)
    is_rollup = (
        (areas == COUNTRY)
        | areas.str.startswith("Landsdel")
        | areas.str.startswith("Region")
    )
    sub = sub[~is_rollup]

    by_area = (
        sub.groupby("OMRÅDE", observed=True)["Adjusted_Income"]
        .mean()
        .sort_values(ascending=False)
    )

    top_n = by_area.head(20)
    x = np.arange(len(top_n))
    y = top_n.values

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=140)

    ax.plot(x, y, color=ACCENT_PURPLE, linewidth=2.5)
    ax.fill_between(x, y, y.min() * 0.95, color=ACCENT_PURPLE, alpha=0.18)
    ax.scatter(x, y, color=ACCENT_PINK, s=35, zorder=3,
               edgecolor=ACCENT_PURPLE, linewidth=1)

    ax.set_title(f"Regional Distribution (Long Tertiary) — {latest}, Adjusted (2024 DKK)",
                 pad=14, fontsize=12, color=TEXT_COLOR)
    ax.set_xticks(x)
    ax.set_xticklabels(top_n.index, rotation=45, ha="right", fontsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(kr_formatter))
    ax.set_ylabel("Average disposable income (2024 DKK)")
    ax.margins(x=0.02)

    fig.tight_layout()
    out = OUT_DIR / "chart3_region.png"
    fig.savefig(out, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(BASE_DIR)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    df = load_data()
    print("Rendering charts ...")
    chart_time(df)
    chart_education(df)
    chart_region(df)
    print("Done.")


if __name__ == "__main__":
    main()
