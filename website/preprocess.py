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
from matplotlib.ticker import FuncFormatter, PercentFormatter

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "INDKP107_komplet.csv"
OUT_DIR = BASE_DIR / "charts"
OUT_DIR.mkdir(exist_ok=True)

# Match the CSS accent palette so chart colors blend with the UI.
ACCENT_BLUE   = "#3b82f6"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_PINK   = "#ec4899"
ACCENT_RED    = "#ef4444"
TEXT_COLOR = "#e2e8f0"
GRID_COLOR = "#ffffff"

# Filter values used throughout. Strings exactly as they appear in the CSV.
UNIT_AVG_ALL = "Gennemsnit for alle personer (kr.)"
INCOME_TYPE = "4 Løn"
GENDER_TOTAL = "Mænd og kvinder i alt"
COUNTRY = "Hele landet"

# ---------------------------------------------------------------------------
# CPI multipliers
# ---------------------------------------------------------------------------
CPI_2024_MULTIPLIER = {
    2004: 1.459, 2005: 1.434, 2006: 1.407, 2007: 1.384, 2008: 1.337,
    2009: 1.320, 2010: 1.288, 2011: 1.254, 2012: 1.224, 2013: 1.214,
    2014: 1.206, 2015: 1.200, 2016: 1.196, 2017: 1.183, 2018: 1.174,
    2019: 1.164, 2020: 1.159, 2021: 1.137, 2022: 1.052, 2023: 1.012,
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
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.2f}M kr."
    if abs(x) >= 1_000:
        return f"{x / 1_000:.0f}k kr."
    return f"{int(x)} kr."

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_data() -> pd.DataFrame:
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

    df["CPI_MULT"] = df["TID"].map(CPI_2024_MULTIPLIER).fillna(1.0).astype(float)
    df["Adjusted_Income"] = df["INDHOLD"] * df["CPI_MULT"]
    return df

# ---------------------------------------------------------------------------
# Chart 1: Gender Pay Gap (%) Over Time by Education
# ---------------------------------------------------------------------------
def chart_time(df: pd.DataFrame) -> None:
    sub = df[(df["OMRÅDE"] == COUNTRY) & (df["KOEN"].isin(["Mænd", "Kvinder"]))]
    
    pivot = sub.pivot_table(index=["TID", "UDDNIV"], columns="KOEN", values="Adjusted_Income").reset_index()
    # Calculate % gap: (Men - Women) / Men * 100
    pivot["Gap"] = (pivot["Mænd"] - pivot["Kvinder"]) / pivot["Mænd"] * 100
    
    gap_pivot = pivot.pivot(index="TID", columns="UDDNIV", values="Gap").sort_index()
    if "Uoplyst" in gap_pivot.columns:
        gap_pivot = gap_pivot.drop(columns=["Uoplyst"])

    label_lookup = {
        "10 GRUNDSKOLE": "Primary school",
        "20+25 GYMNASIALE UDDANNELSER": "Gymnasium",
        "35 ERHVERVSUDDANNELSER": "Vocational Education",
        "40 KORTE VIDEREGÅENDE UDDANNELSER": "Short Higher Education",
        "50+60 MELLEMLANGE VIDEREGÅENDE UDDANNELSER INKL. BACHELOR": "Medium Higher Education",
        "65 LANGE VIDEREGÅENDE UDDANNELSER": "Long Higher Education",
    }
    
    latest_year = gap_pivot.index.max()
    sorted_cols = gap_pivot.loc[latest_year].sort_values(ascending=False).index
    gap_pivot = gap_pivot[sorted_cols]

    fig, ax = plt.subplots(figsize=(11, 4.8), dpi=140)
    cmap = plt.cm.colors.LinearSegmentedColormap.from_list(
        "accents", [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_PINK, ACCENT_RED]
    )
    
    for i, col in enumerate(gap_pivot.columns):
        color = cmap(i / max(1, len(gap_pivot.columns) - 1))
        label = label_lookup.get(col, col)
        ax.plot(
            gap_pivot.index, gap_pivot[col],
            marker="o", markersize=4, linewidth=2.5,
            color=color, label=label,
        )

    ax.set_title("Gender Income Gap Over Time", pad=14, fontsize=12, color=TEXT_COLOR)
    ax.set_xlabel("Year")
    ax.set_ylabel("Income Gap (% less than men)")
    ax.yaxis.set_major_formatter(PercentFormatter())
    years = sorted(gap_pivot.index.astype(int).unique())
    ax.set_xticks(years[::2])
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: str(int(x))))
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    ax.margins(x=0.02)

    fig.tight_layout()
    out = OUT_DIR / "chart1_time.png"
    fig.savefig(out, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(BASE_DIR)}")

# ---------------------------------------------------------------------------
# Chart 2: Income by Education (Men vs Women)
# ---------------------------------------------------------------------------
def chart_education(df: pd.DataFrame) -> None:
    latest = int(df["TID"].max())
    sub = df[
        (df["TID"] == latest)
        & (df["OMRÅDE"] == COUNTRY)
        & (df["KOEN"].isin(["Mænd", "Kvinder"]))
    ]

    pivot = sub.pivot_table(index="UDDNIV", columns="KOEN", values="Adjusted_Income")
    if "Uoplyst" in pivot.index:
        pivot = pivot.drop(index="Uoplyst")
    pivot = pivot.sort_values(by="Mænd", ascending=True)

    label_lookup = {
        "10 GRUNDSKOLE": "Primary school",
        "20+25 GYMNASIALE UDDANNELSER": "Gymnasium",
        "35 ERHVERVSUDDANNELSER": "Vocational Education",
        "40 KORTE VIDEREGÅENDE UDDANNELSER": "Short Higher",
        "50+60 MELLEMLANGE VIDEREGÅENDE UDDANNELSER INKL. BACHELOR": "Medium Higher",
        "65 LANGE VIDEREGÅENDE UDDANNELSER": "Long Higher",
    }
    labels = [label_lookup.get(idx, idx) for idx in pivot.index]

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=140)
    
    y = np.arange(len(labels))
    height = 0.35

    ax.barh(y - height/2, pivot["Kvinder"], height, label="Women", color=ACCENT_RED, edgecolor="none")
    ax.barh(y + height/2, pivot["Mænd"], height, label="Men", color=ACCENT_BLUE, edgecolor="none")

    ax.set_title(f"Income by Education (Men vs Women) — {latest}", pad=14, fontsize=12, color=TEXT_COLOR)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.xaxis.set_major_formatter(FuncFormatter(kr_formatter))
    ax.set_xlabel("Average wages (2024 DKK)")
    ax.legend(frameon=False, loc="lower right")
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.margins(x=0.05)

    fig.tight_layout()
    out = OUT_DIR / "chart2_education.png"
    fig.savefig(out, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(BASE_DIR)}")

# ---------------------------------------------------------------------------
# Chart 3: Regional Distribution (Dumbbell Plot for Gender Gap)
# ---------------------------------------------------------------------------
def chart_region(df: pd.DataFrame) -> None:
    latest = int(df["TID"].max())
    sub = df[
        (df["TID"] == latest) 
        & (df["KOEN"].isin(["Mænd", "Kvinder"]))
        & (df["UDDNIV"] == "65 LANGE VIDEREGÅENDE UDDANNELSER")
    ]

    areas = sub["OMRÅDE"].astype(str)
    is_rollup = (
        (areas == COUNTRY)
        | areas.str.startswith("Landsdel")
        | areas.str.startswith("Region")
    )
    sub = sub[~is_rollup]

    pivot = sub.pivot_table(index="OMRÅDE", columns="KOEN", values="Adjusted_Income")
    top_n = pivot.sort_values(by="Mænd", ascending=False).head(15)
    
    # Sort backwards so highest is at the top of the horizontal chart
    top_n = top_n.sort_values(by="Mænd", ascending=True)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=140)
    y = np.arange(len(top_n))

    # Draw line connecting the dots
    ax.hlines(y, top_n["Kvinder"], top_n["Mænd"], color="#ffffff44", linewidth=2, zorder=1)
    
    # Draw dots
    ax.scatter(top_n["Kvinder"], y, color=ACCENT_RED, s=80, label="Women", zorder=2)
    ax.scatter(top_n["Mænd"], y, color=ACCENT_BLUE, s=80, label="Men", zorder=2)

    ax.set_title(f"Regional Gender Gap (Long Higher Ed.) — {latest}", pad=14, fontsize=12, color=TEXT_COLOR)
    ax.set_yticks(y)
    ax.set_yticklabels(top_n.index, fontsize=9)
    ax.xaxis.set_major_formatter(FuncFormatter(kr_formatter))
    ax.set_xlabel("Average wages (2024 DKK)")
    
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    ax.margins(x=0.05)

    fig.tight_layout()
    out = OUT_DIR / "chart3_region.png"
    fig.savefig(out, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out.relative_to(BASE_DIR)}")

def main() -> None:
    df = load_data()
    print("Rendering charts ...")
    chart_time(df)
    chart_education(df)
    chart_region(df)
    print("Done.")

if __name__ == "__main__":
    main()
