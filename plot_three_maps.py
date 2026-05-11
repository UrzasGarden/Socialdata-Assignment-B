import json
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Try to locate data CSV automatically (common locations)
possible = [
    Path.cwd() / "INDKP107_komplet.csv",
    Path.cwd() / "INDKP107_komplet.csv" / "INDKP107_komplet.csv",
    Path.home() / "Downloads" / "INDKP107_komplet.csv",
]

data_path = None
for p in possible:
    if p.exists():
        data_path = p
        break

if data_path is None:
    raise FileNotFoundError("Could not find INDKP107_komplet.csv. Please set data_path in the script.")

print(f"Using data: {data_path}")
Data = pd.read_csv(data_path, sep=';')
Data = Data.dropna(how='all')

# Minimal preprocessing needed for these maps
Data = Data[["TID", "OMRÅDE", "KOEN", "UDDNIV", "INDKOMSTTYPE", "INDHOLD", "ENHED"]]
Data.columns = ["Year", "Area", "Gender", "Education_Level", "Income_Type", "Value", "Unit"]
Data["Year"] = pd.to_numeric(Data["Year"], errors="coerce")
Data["Value"] = pd.to_numeric(Data["Value"], errors="coerce")
text_cols = ["Area", "Gender", "Education_Level", "Income_Type", "Unit"]
for col in text_cols:
    Data[col] = Data[col].astype(str).str.strip()

# Build plot_df and lookup
plot_df = Data.copy()
plot_df["Area_norm"] = plot_df["Area"].astype(str).str.strip().str.lower()
lookup_csv_path = Path.cwd() / "GeoData" / "Places.csv"
if not lookup_csv_path.exists():
    raise FileNotFoundError("GeoData/Places.csv not found")
lookup = pd.read_csv(lookup_csv_path)
lookup["lau_1"] = lookup["lau_1"].astype(str).str.strip()
lookup_dk = lookup[["lau_1", "label_dk"]].rename(columns={"label_dk": "Area"})
lookup_en = lookup[["lau_1", "label_en"]].rename(columns={"label_en": "Area"})
lookup_long = pd.concat([lookup_dk, lookup_en], ignore_index=True)
lookup_long["Area_norm"] = lookup_long["Area"].astype(str).str.strip().str.lower()
lookup_long = lookup_long[["lau_1", "Area_norm"]].drop_duplicates()

# Aliases
area_aliases = {"aarhus": "århus", "brønderslev": "brønderslev-dronninglund"}
alias_df = pd.DataFrame({"Area_norm": list(area_aliases.keys()), "Area_norm_target": list(area_aliases.values())})
alias_rows = (alias_df.merge(
    lookup_long.rename(columns={"Area_norm": "Area_norm_target"}),
    on="Area_norm_target",
    how="left",
)[["lau_1", "Area_norm"]].dropna(subset=["lau_1"]).drop_duplicates())
lookup_long = pd.concat([lookup_long, alias_rows], ignore_index=True).drop_duplicates()

matched_rows = plot_df.merge(lookup_long, on="Area_norm", how="left")
matched_rows = matched_rows.dropna(subset=["lau_1"]).copy()
agg = (matched_rows.groupby("lau_1", as_index=False).agg(Data_Points=("Area", "size"), Area=("Area", "first")))

# Load geojsons
mun_geojson_path = Path.cwd() / "GeoData" / "municipalities.geojson"
lands_geojson_path = Path.cwd() / "GeoData" / "landsdel.geojson"
region_geojson_path = Path.cwd() / "GeoData" / "regions.json"
for p in [mun_geojson_path, lands_geojson_path, region_geojson_path]:
    if not p.exists():
        raise FileNotFoundError(f"Missing geojson: {p}")

with open(mun_geojson_path, 'r', encoding='utf-8') as f:
    mun_geojson = json.load(f)
for feat in mun_geojson['features']:
    feat['properties']['lau_1'] = str(feat.get('properties', {}).get('lau_1', '')).strip()

with open(lands_geojson_path, 'r', encoding='utf-8') as f:
    subregion_geojson = json.load(f)
for feat in subregion_geojson['features']:
    feat['properties']['navn'] = str(feat.get('properties', {}).get('navn', '')).strip().lower()

with open(region_geojson_path, 'r', encoding='utf-8') as f:
    region_geojson = json.load(f)
for feat in region_geojson['features']:
    feat['properties']['name'] = str(feat.get('properties', {}).get('name', '')).strip().lower()

# Subregions
subregion_df = plot_df[plot_df["Area_norm"].astype(str).str.lower().str.startswith("landsdel ")].copy()
if not subregion_df.empty:
    subregion_df["Landsdel_name"] = (
        subregion_df["Area_norm"].astype(str).str.strip().str.lower()
        .str.replace(r"^landsdel\\s+", "", regex=True)
    )
    subregion_agg = subregion_df.groupby("Landsdel_name", as_index=False).agg(Data_Points=("Area", "size"), Area=("Area", "first"))
    geo_subregion_names = {feat['properties']['navn'] for feat in subregion_geojson['features']}
    subregion_agg = subregion_agg[subregion_agg['Landsdel_name'].isin(geo_subregion_names)]
else:
    subregion_agg = pd.DataFrame(columns=["Landsdel_name", "Data_Points", "Area"])

# Regions
region_df = plot_df[plot_df["Area"].astype(str).str.lower().str.startswith("region ")].copy()
if not region_df.empty:
    region_df["Region_name"] = (
        region_df["Area"].astype(str).str.strip().str.lower()
        .str.replace(r"^region\\s+", "", regex=True)
    )
    region_agg = region_df.groupby("Region_name", as_index=False).agg(Data_Points=("Area", "size"), Area=("Area", "first"))
    geo_region_names = {feat['properties']['name'] for feat in region_geojson['features']}
    region_agg = region_agg[region_agg['Region_name'].isin(geo_region_names)]
else:
    region_agg = pd.DataFrame(columns=["Region_name", "Data_Points", "Area"])

# Shared color range
all_vals = list(agg['Data_Points']) if not agg.empty else []
if not subregion_agg.empty:
    all_vals += list(subregion_agg['Data_Points'])
if not region_agg.empty:
    all_vals += list(region_agg['Data_Points'])
if len(all_vals) == 0:
    data_min, data_max = 0, 1
else:
    data_min, data_max = min(all_vals), max(all_vals)

# Regions figure
if not region_agg.empty:
    fig_regions = go.Figure(go.Choropleth(
        locations=region_agg['Region_name'],
        z=region_agg['Data_Points'],
        geojson=region_geojson,
        featureidkey='properties.name',
        colorscale='Viridis', zmin=data_min, zmax=data_max,
        marker_line_width=0.5,
        customdata=region_agg['Area'],
        hovertemplate='<b>%{customdata}</b><br>Data points: %{z}<extra></extra>',
    ))
    fig_regions.update_geos(fitbounds='locations', visible=False, projection_type='mercator')
    fig_regions.update_layout(title_text='Data points — Regions', height=500, margin=dict(t=50))
    fig_regions.write_html('regions_map.html')
    print('Saved regions_map.html')

# Subregions figure
if not subregion_agg.empty:
    fig_sub = go.Figure(go.Choropleth(
        locations=subregion_agg['Landsdel_name'],
        z=subregion_agg['Data_Points'],
        geojson=subregion_geojson,
        featureidkey='properties.navn',
        colorscale='Viridis', zmin=data_min, zmax=data_max,
        marker_line_width=0.5,
        customdata=subregion_agg['Area'],
        hovertemplate='<b>%{customdata}</b><br>Data points: %{z}<extra></extra>',
    ))
    fig_sub.update_geos(fitbounds='locations', visible=False, projection_type='mercator')
    fig_sub.update_layout(title_text='Data points — Subregions (Landsdel)', height=500, margin=dict(t=50))
    fig_sub.write_html('subregions_map.html')
    print('Saved subregions_map.html')

# Municipalities figure
if not agg.empty:
    fig_munis = go.Figure(go.Choropleth(
        locations=agg['lau_1'],
        z=agg['Data_Points'],
        geojson=mun_geojson,
        featureidkey='properties.lau_1',
        colorscale='Viridis', zmin=data_min, zmax=data_max,
        marker_line_width=0.2,
        customdata=agg['Area'],
        hovertemplate='<b>%{customdata}</b><br>Data points: %{z}<extra></extra>',
    ))
    fig_munis.update_geos(fitbounds='locations', visible=False, projection_type='mercator')
    fig_munis.update_layout(title_text='Data points — Municipalities (Kommune)', height=700, margin=dict(t=50))
    fig_munis.write_html('municipalities_map.html')
    print('Saved municipalities_map.html')

print(f"Regions matched: {len(region_agg) if not region_agg.empty else 0}/5")
print(f"Subregions matched: {len(subregion_agg) if not subregion_agg.empty else 0}/11")
print(f"Municipalities matched: {len(agg) if not agg.empty else 0}/98")
