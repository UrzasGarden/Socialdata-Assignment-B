import pandas as pd
from pathlib import Path

BASE_DIR = Path("/Users/jonathannielsen/Desktop/vibed/Socialdata-Assignment-B/newWebsite")
CSV_PATH = BASE_DIR / "INDKP107_komplet.csv"
UNIT_AVG_ALL = "Gennemsnit for alle personer (kr.)"
INCOME_TYPE = "1 Disponibel indkomst (2+30-31-32-35)"
COUNTRY = "Hele landet"

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
df = df.loc[mask].dropna(subset=["INDHOLD"])

sub = df[(df["OMRÅDE"] == COUNTRY) & (df["KOEN"].isin(["Mænd", "Kvinder"]))]
pivot = sub.pivot_table(index=["TID", "UDDNIV"], columns="KOEN", values="INDHOLD").reset_index()
pivot["Gap"] = (pivot["Mænd"] - pivot["Kvinder"]) / pivot["Mænd"] * 100
print(pivot[pivot["TID"] == 2023].to_string())

