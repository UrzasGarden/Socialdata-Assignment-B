# Socialdata Assignment B

Interactive data story and dashboard project for exploring income and geography-related data in Denmark.

## Project Overview

This repository contains:
- A landing page data story
- An interactive dashboard page with map interactions
- Jupyter notebooks for data exploration and hand-in material
- Geographic data files in GeoJSON/JSON/CSV formats

## Project Structure

- [index.html](index.html): Main entry page (Data Story)
- [Main_page/style.css](Main_page/style.css): Shared styling used by pages
- [Main_page/dk.svg](Main_page/dk.svg): Denmark SVG asset
- [Main_page/Map_DK.svg](Main_page/Map_DK.svg): Interactive map SVG asset
- [Explore_page/explore.html](Explore_page/explore.html): Dashboard page
- [Explore_page/dataExplore.ipynb](Explore_page/dataExplore.ipynb): Exploration notebook
- [Hand-in-notebook.ipynb](Hand-in-notebook.ipynb): Assignment hand-in notebook
- [Chaos.ipynb](Chaos.ipynb): Additional notebook
- [GeoData](GeoData): Geographic datasets and helper script

## Quick Start

### Option 1: Open directly in browser
1. Open [index.html](index.html) in your browser.

### Option 2: Run a local static server (recommended)
From the project root, run one of these commands:

PowerShell (Python):
python -m http.server 8000

Then open:
http://localhost:8000

## Notes

- The dashboard page is linked from [index.html](index.html) and is located at [Explore_page/explore.html](Explore_page/explore.html).
- Paths are currently organized with page assets in [Main_page](Main_page) and dashboard files in [Explore_page](Explore_page).
- Notebook files can be run in Jupyter or VS Code Notebook support.
