# Import
import pandas as pd 
import numpy as np 
import matplotlib.pyplot as plt
import json
from pathlib import Path
import pandas as pd
import plotly.express as px

# Load data
data_path = "newWebsite/INDKP107_komplet.csv"
Data = pd.read_csv(data_path, sep=";")
Data = Data.dropna()


# Restructure and rename columns (to English)
Data = Data[["TID", "OMRÅDE", "KOEN", "UDDNIV", "INDKOMSTTYPE", "INDHOLD", "ENHED"]]
Data.columns = ["Year", "Area", "Gender", "Education_Level", "Income_Type", "Value", "Unit"]

# Convert year and income to numeric values
Data["Year"] = pd.to_numeric(Data["Year"], errors="coerce")
Data["Value"] = pd.to_numeric(Data["Value"], errors="coerce")

# A lot of the text values have unnecessary whitespace like "                10 GRUNDSKOLE " instead of "10 GRUNDSKOLE".
# Therefore: trim leading/trailing whitespace in text columns
text_cols = ["Area", "Gender", "Education_Level", "Income_Type", "Unit"]
for col in text_cols:
    Data[col] = Data[col].str.strip()

# Rename values from Danish to English
Data["Gender"] = Data["Gender"].replace({
    "Mænd": "Male", 
    "Kvinder": "Female", 
    "Mænd og kvinder i alt": "Both Genders Total"})
Data["Education_Level"] = Data["Education_Level"].replace({
    "Uoplyst": "Unknown",
    "10 GRUNDSKOLE": "Primary School",
    "20+25 GYMNASIALE UDDANNELSER": "Gymnasium",
    "35 ERHVERVSUDDANNELSER": "Vocational Education",
    "40 KORTE VIDEREGÅENDE UDDANNELSER": "Short Higher Education",
    "50+60 MELLEMLANGE VIDEREGÅENDE UDDANNELSER INKL. BACHELOR": "Medium Higher Education",
    "65 LANGE VIDEREGÅENDE UDDANNELSER": "Long Higher Education"})
Data["Unit"] = Data["Unit"].replace({
    "Gennemsnit for alle personer (kr.)": "Average for all persons (DKK)",
    "Gennemsnit for personer med indkomsttypen (kr.)": "Average for persons with income type (DKK)",
    "Indkomstbeløb (1.000 kr.)": "Income amount (1,000 DKK)",
    "Personer med indkomsttypen (antal)": "Persons with income type (number)"})
Data["Income_Type"] = Data["Income_Type"].replace({
    "1 Disponibel indkomst (2+30-31-32-35)": "1 Disposable income (2+30+31+32+35)",
    "2 Indkomst i alt, før skatter mv. (3+7+22+26+29)": "2 Total income before taxes, etc. (3+7+22+26+29)",
    "3 Erhvervsindkomst (4+5+6)": "3 Business income (4+5+6)",
    "4 Løn": "4 Wages/salary",
    "5 Virksomhedsoverskud": "5 Business profits",
    "6 AMB.pligtige honorarer": "6 Professional fees subject to labour market contribution",
    "7 Offentlige overførsler (8+14+19)": "7 Public transfers (8+14+19)",
    "8 Dagpenge og kontanthjælp i alt (9+10+11+12+13)": "8 Unemployment and cash benefits total (9+10+11+12+13)",
    "9 Arbejdsløshedsdagpenge mv.": "9 Unemployment benefits, etc.",
    "10 Øvrige dagpenge fra A-kasser": "10 Other unemployment benefits from unemployment insurance funds",
    "11 Kontanthjælp": "11 Social assistance (cash benefits)",
    "12 Aktiverings-, ledigheds- og revalideringsydelse mv.": "12 Activation, unemployment and rehabilitation benefits, etc.",
    "13 Syge og barselsdagpenge, ekskl. refusion til arbejdsgiver": "13 Sickness and parental leave benefits, excl. employer reimbursement",
    "14 Øvrige overførsler(15+16+17+18)": "14 Other transfers (15+16+17+18)",
    "15 Statens uddannelsesstøtte": "15 State education grant (SU)",
    "16 Boligstøtte": "16 Housing benefit",
    "17 Børnefamilieydelser": "17 Child and family benefits",
    "18 Grøn check": "18 Green tax compensation",
    "19 Offentlige pensioner(20+21)": "19 Public pensions (20+21)",
    "20 Efterløn, fleksydelse": "20 Early retirement pay and flex benefit",
    "21 Folke- og førtidspension": "21 State and disability pension",
    "22 Private pensioner(23+24+25)": "22 Private pensions (23+24+25)",
    "23 Tjenestemandspension": "23 Civil servant pension",
    "24 ATP pension": "24 ATP pension",
    "25 Arbejdsmarkeds- og privatpensioner (Rate og Livrente)": "25 Labor market and private pensions (instalment and life annuity)",
    "26 Formueindkomst, brutto (27+28)": "26 Capital income, gross (27+28)",
    "27 Renteindtægt": "27 Interest income",
    "28 Øvrig formueindkomst (Aktieindkomst mv.)": "28 Other capital income (share income, etc.)",
    "29 Anden personlig indkomst": "29 Other personal income",
    "30 Lejeværdi af egen bolig": "30 Imputed rent of owner-occupied housing",
    "31 Renteudgifter": "31 Interest expenses",
    "32 Skat mv. (33+34)": "32 Taxes, etc. (33+34)",
    "33 Indkomstskat": "33 Income tax",
    "34 Arbejdsmarkedsbidrag og særlig pensionsopsparing": "34 Labor market contribution and special pension savings",
    "35 Betalt underholdsbidrag": "35 Paid alimony",
    "Ejendomsskat (grundskyld), boligejere": "36 Property tax (land tax), homeowners",
    "Ejendomsskat (grundskyld), lejere": "37 Property tax (land tax), tenants",
    "Skattepligtig indkomst": "38 Taxable income",
    "Ækvivaleret disponibel indkomst": "39 Equivalized disposable income",
})

print("Data processing complete.")
print(Data.info())
print(Data.head())

