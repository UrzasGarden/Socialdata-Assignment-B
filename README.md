# Socialdata Assignment B

Interactive data story and dashboard exploring Denmark's gender pay gap and education paradox, using two decades of Statistics Denmark data.

## Project Overview

This project tells the story of *Denmark's Equality Paradox*: Denmark ranks among the world's most gender-equal societies, yet a persistent pay gap remains. The project combines a scrollable data story with an interactive dashboard for exploring the underlying data by geography, education level, income type, and year.

## Live Site

Open [https://urzasgarden.github.io/Socialdata-Assignment-B/index.html](https://urzasgarden.github.io/Socialdata-Assignment-B/index.html) in your browser.

## Project Structure

```
.
├── index.html                        # Data Story (main entry page)
├── Hand-in.ipynb                     # Assignment hand-in notebook
├── Pictures_for_handin/              # Figures exported from the notebook
├── GeoData/                          # Root-level geographic datasets (GeoJSON/CSV)
└── website/
    ├── explore.html                  # Interactive dashboard
    ├── styles.css                    # Shared stylesheet
    ├── script.js                     # Dashboard logic (Leaflet maps, filters, charts)
    ├── dashboard_aggregation.json    # Pre-processed data served to the dashboard
    ├── GeoData/                      # GeoJSON files used by the dashboard
    │   ├── municipalities_clean.geojson
    │   ├── municipalities.geojson
    │   ├── landsdel.geojson
    │   └── regions.json
    ├── charts/                       # Static chart images and a standalone chart page
    │   ├── chart1_time.png
    │   ├── chart2_education.png
    │   ├── chart3_region.png
    │   └── index.html
    ├── municipalities_map.html       # Standalone municipality map
    ├── regions_map.html              # Standalone region map
    ├── subregions_map.html           # Standalone subregion map
    ├── Data_processing.py            # Data cleaning and transformation script
    ├── preprocess.py                 # Preprocessing pipeline
    ├── aggregate_dashboard.py        # Aggregates data into dashboard_aggregation.json
    └── plot_three_maps.py            # Generates the static chart images
```

## Quick Start

### Option 1: Open via GitHub Pages
Visit the live site linked above — no setup required.

### Option 2: Run a local static server
From the project root, run:

```bash
python -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

### Option 3: Regenerate the dashboard data
If you need to re-run the data pipeline it requires the source CSV from Statistics Denmark, [link to data](https://www.statistikbanken.dk/INDKP107), and a change of path in [Hand-in.ipynb](Hand-in.ipynb).


```bash
cd website
python preprocess.py
python aggregate_dashboard.py
```

## Key Files

| File | Purpose |
|------|---------|
| [index.html](index.html) | Scrollable data story with embedded charts |
| [website/explore.html](website/explore.html) | Interactive dashboard — filter by year, education, income type; click municipalities on a Leaflet map |
| [Hand-in.ipynb](Hand-in.ipynb) | Jupyter notebook with full analysis and hand-in material |
| [website/dashboard_aggregation.json](website/dashboard_aggregation.json) | Pre-aggregated JSON powering the dashboard (no backend needed) |

## Notes

- The dashboard uses [Leaflet.js](https://leafletjs.com/) for the interactive choropleth map.
- No build step or package install is required to run the website — everything is plain HTML/CSS/JS with CDN dependencies.
- Notebook files can be opened in Jupyter or VS Code with the Jupyter extension.
