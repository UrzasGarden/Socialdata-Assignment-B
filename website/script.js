/* ==========================================================================
 * Interactive Dashboard - "Bowl" of the Martini Glass
 * --------------------------------------------------------------------------
 * Loads the pre-aggregated dashboard JSON + three GeoJSON files, renders an
 * interactive Leaflet choropleth, and drives a Chart.js panel that responds
 * to map clicks and filter changes.
 *
 * Data flow:
 *   1. fetchAll()              - parallel fetch of JSON + geojson assets
 *   2. populateControls()      - fill education + year dropdowns from metadata
 *   3. initMap()               - one-time Leaflet map setup
 *   4. renderLayer()           - swap GeoJSON layer (country/regions/munis)
 *                                and recolor based on current education+year
 *   5. renderChart()           - rebuild Chart.js (or table) from current
 *                                selection + filter state
 *
 * State is kept in a single mutable object; every interaction calls into
 * either renderLayer() or renderChart() (or both) to re-derive the view.
 * ========================================================================== */

(() => {

  // -----------------------------------------------------------------------
  // Constants
  // -----------------------------------------------------------------------
  const ACCENT_BLUE   = "#3b82f6";
  const ACCENT_PURPLE = "#8b5cf6";
  const ACCENT_PINK   = "#ec4899";
  const ACCENT_RED    = "#ef4444";
  const TEXT_PRIMARY  = "#e2e8f0";
  const TEXT_SECONDARY = "#94a3b8";

  const ASSETS = {
    aggregation: "dashboard_aggregation.json?v=4",
    landsdel:    "GeoData/landsdel.geojson",
    regions:     "GeoData/regions.json",
    munis:       "GeoData/municipalities_clean.geojson",
  };

  // Whichever field on a GeoJSON feature.properties holds the join key for
  // each layer. landsdel/subregions has no data in our JSON so it's treated
  // as context in the current explorer build.
  const NAME_FIELD = {
    country: "navn",       // landsdel.geojson: "Østjylland", "Bornholm", ...
    regions: "name",       // regions.json:    "Hovedstaden", "Sjælland", ...
    munis:   "label_dk",   // municipalities:   "Aarhus", "København", ...
  };

  // Some municipality names diverge between Statistics Denmark (our JSON keys)
  // and the GeoJSON's label_dk field. Add aliases here as we find them.
  // Format: geoJsonName -> aggregationJsonKey
  const MUNI_ALIASES = {
    "Århus": "Aarhus",
    "Vesthimmerland": "Vesthimmerlands",
    "Brønderslev-Dronninglund": "Brønderslev",
  };

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  const state = {
    meta: null,
    fullData: null,          // Complete nested structure: { [IncomeType]: { National_Data, Landsdel_Data, Region_Data, Municipality_Data } }
    nationalData: null,
    landsdelData: null,
    regionData: null,        // Pointer to current income type's Region_Data
    muniData:   null,
    geo: { country: null, regions: null, munis: null },

    incomeType: null,        // selected income type
    education: null,         // selected education label (string)
    year: null,              // selected year (string, e.g. "2024")
    layer: "regions",        // "country" | "regions" | "munis"
    chartType: "bar",        // "bar" | "line" | "table"
    metric: "gap_pct",       // "gap_abs" | "men" | "women" | "gap_pct"
    selected: new Set(),     // selected area names (in their JSON-key form)

    map: null,
    geoLayer: null,          // currently rendered Leaflet GeoJSON layer
    chart: null,             // Chart.js instance (null when in table mode)
    dotChart: null,          // Chart.js instance for education dot plot
    dotSplit: "combined",    // "combined" | "gender"
  };

  // -----------------------------------------------------------------------
  // 1. Load assets in parallel
  // -----------------------------------------------------------------------
  async function fetchAll() {
    const [agg, country, regions, munis] = await Promise.all([
      fetch(ASSETS.aggregation).then(r => r.json()),
      fetch(ASSETS.landsdel).then(r => r.json()),
      fetch(ASSETS.regions).then(r => r.json()),
      fetch(ASSETS.munis).then(r => r.json()),
    ]);

    state.meta         = agg.Metadata;
    state.fullData     = agg.Data;
    // We will initialize nationalData, landsdelData, regionData, and muniData in populateControls()
    state.geo.country = country;
    state.geo.regions = regions;
    state.geo.munis   = munis;
  }

  // -----------------------------------------------------------------------
  // 2. Populate dropdowns from metadata
  // -----------------------------------------------------------------------
  function populateControls() {
    const incomeSel = document.getElementById("income-select");
    const eduSel  = document.getElementById("education-select");
    const yearSel = document.getElementById("year-select");

    // Populate Income Types
    state.meta.Income_Types.forEach(inc => {
      const opt = document.createElement("option");
      opt.value = inc;
      opt.textContent = inc;
      incomeSel.appendChild(opt);
    });
    const defaultIncome = state.meta.Income_Types.includes("Wages")
      ? "Wages"
      : (state.meta.Income_Types.includes("Wages/salary") ? "Wages/salary" : state.meta.Income_Types[0]);
    incomeSel.value = defaultIncome;
    state.incomeType = defaultIncome;

    // Set initial pointers
    state.nationalData = state.fullData[state.incomeType].National_Data;
    state.landsdelData = state.fullData[state.incomeType].Landsdel_Data || {};
    state.regionData   = state.fullData[state.incomeType].Region_Data;
    state.muniData     = state.fullData[state.incomeType].Municipality_Data;

    state.meta.Education_Levels.forEach(lv => {
      const opt = document.createElement("option");
      opt.value = lv;
      opt.textContent = lv;
      eduSel.appendChild(opt);
    });
    // Default to the highest tier - that's where the gap is most dramatic.
    const defaultEdu = state.meta.Education_Levels.includes("Long Higher Education")
      ? "Long Higher Education"
      : (state.meta.Education_Levels.includes("Long tertiary") ? "Long tertiary" : state.meta.Education_Levels[0]);
    eduSel.value = defaultEdu;
    state.education = defaultEdu;

    // Years descending so the latest is on top.
    [...state.meta.Years_Available].sort((a, b) => b - a).forEach(y => {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      yearSel.appendChild(opt);
    });
    yearSel.value = String(Math.max(...state.meta.Years_Available));
    state.year = yearSel.value;
  }

  // -----------------------------------------------------------------------
  // 3. Map
  // -----------------------------------------------------------------------
  function initMap() {
    // No tile layer - we want the page's animated blob background to bleed
    // through. The map is purely a vector choropleth on transparent canvas.
    state.map = L.map("map", {
      zoomControl: true,
      attributionControl: false,
      scrollWheelZoom: false,   // avoid hijacking page scroll
      preferCanvas: true,
    }).setView([56.0, 11.5], 6);
  }

  /** Resolve a GeoJSON feature to the (areaName, dataPoint) pair used by the
   *  rest of the code. Returns null if the layer has no associated data. */
  function lookupFeature(feature, layerKey) {
    const rawName = feature.properties[NAME_FIELD[layerKey]];
    if (!rawName) return null;

    if (layerKey === "regions") {
      const dp = state.regionData[state.year]?.[rawName]?.[state.education] ?? null;
      return { name: rawName, dp };
    }
    if (layerKey === "munis") {
      const key = MUNI_ALIASES[rawName] ?? rawName;
      const dp = state.muniData[state.year]?.[key]?.[state.education] ?? null;
      return { name: key, dp };
    }
    const dp = state.landsdelData?.[state.year]?.[rawName]?.[state.education] ?? null;
    return { name: rawName, dp };
  }

  function mapMetricValue(dp) {
    if (!dp) return null;
    if (state.metric === "gap_pct") {
      {
        const hi = Math.max(dp.Men, dp.Women);
        const lo = Math.min(dp.Men, dp.Women);
        return hi ? (1 - lo / hi) * 100 : null;
      }
    }
    return dp.Gap;
  }

  /** Linear hex interpolation along green -> yellow -> orange -> red. */
  function colorForGap(gap, min, max) {
    if (gap == null || !isFinite(gap)) return "rgba(255,255,255,0.05)";
    if (max <= min) return ACCENT_PURPLE;
    const t = Math.max(0, Math.min(1, (gap - min) / (max - min)));
    const stops = [
      { t: 0.0,  c: hexToRgb("#a8e063") }, // light green
      { t: 0.4,  c: hexToRgb("#fde047") }, // yellow
      { t: 0.7,  c: hexToRgb("#f97316") }, // orange
      { t: 1.0,  c: hexToRgb("#ef4444") }, // red
    ];
    let a = stops[0], b = stops[stops.length - 1];
    for (let i = 0; i < stops.length - 1; i++) {
      if (t >= stops[i].t && t <= stops[i + 1].t) { a = stops[i]; b = stops[i + 1]; break; }
    }
    const k = (t - a.t) / (b.t - a.t || 1);
    const r = Math.round(a.c[0] + (b.c[0] - a.c[0]) * k);
    const g = Math.round(a.c[1] + (b.c[1] - a.c[1]) * k);
    const bl = Math.round(a.c[2] + (b.c[2] - a.c[2]) * k);
    return `rgb(${r},${g},${bl})`;
  }

  function hexToRgb(hex) {
    const v = hex.replace("#", "");
    return [parseInt(v.slice(0,2), 16), parseInt(v.slice(2,4), 16), parseInt(v.slice(4,6), 16)];
  }

  /** Compute min/max gap to anchor the colour scale and legend.
   *  Domain is computed across ALL layers (country/regions/munis) for the
   *  current income / education / year / metric so colors stay consistent
   *  when the user toggles between geographic levels. */
  function gapDomain(_layerKey) {
    const gaps = [];
    for (const key of ["country", "regions", "munis"]) {
      const fc = state.geo[key];
      if (!fc) continue;
      fc.features.forEach(f => {
        const r = lookupFeature(f, key);
        const v = mapMetricValue(r?.dp);
        if (v != null && isFinite(v)) gaps.push(v);
      });
    }
    if (!gaps.length) return [0, 0];
    return [Math.min(...gaps), Math.max(...gaps)];
  }

  /** Re-render the active GeoJSON layer with the current education/year.
   *  Called on layer toggle, education change, year change, and selection. */
  function renderLayer() {
    if (state.geoLayer) {
      state.map.removeLayer(state.geoLayer);
      state.geoLayer = null;
    }

    const layerKey = state.layer;
    const fc = state.geo[layerKey];
    const [gMin, gMax] = gapDomain(layerKey);

    // Update legend ticks.
    document.getElementById("legend-min").textContent = gMax > gMin ? formatMetric(gMin) : "-";
    document.getElementById("legend-max").textContent = gMax > gMin ? formatMetric(gMax) : "-";
    document.getElementById("map-legend").style.opacity = gMax > gMin ? "1" : "0.3";

    const legendLabel = document.querySelector("#map-legend .legend-label");
    if (legendLabel) {
      const incomeLabel = state.incomeType || "Wages/salary";
      const yearLabel = state.year || "2024";
      legendLabel.textContent = state.metric === "gap_pct"
        ? `${incomeLabel} gap (% of the higher earner's income, ${yearLabel})`
        : `${incomeLabel} gap (M − W, ${yearLabel} DKK)`;
    }

    // municipalities_clean.geojson already has exactly 99 dissolved features
    // (98 current municipalities + Christiansø). No filter needed - features
    // without data for the current filter show greyed out via the style fn.
    const filter = () => true;

    state.geoLayer = L.geoJSON(fc, {
      filter,
      style: feature => {
        const { dp, name } = lookupFeature(feature, layerKey) ?? {};
        const metricValue = mapMetricValue(dp);
        const isSelected = name && state.selected.has(name);
        const hasData = metricValue != null;
        return {
          fillColor: hasData ? colorForGap(metricValue, gMin, gMax) : "rgba(255,255,255,0.04)",
          fillOpacity: hasData ? 0.78 : 0.12,
          color: isSelected ? "#ffffff" : hasData ? "rgba(255,255,255,0.25)" : "rgba(255,255,255,0.1)",
          weight: isSelected ? 2.5 : 0.8,
          dashArray: hasData ? "0" : "4 3",
        };
      },
      onEachFeature: (feature, lyr) => {
        const { name, dp } = lookupFeature(feature, layerKey) ?? {};
        const metricValue = mapMetricValue(dp);
        if (!name) return;

        // Hover tooltip (with special formatting for "country" layer)
        const tooltipName = layerKey === "country" ? `Denmark (${escapeHtml(name)})` : name;
        lyr.bindTooltip(buildTooltip(tooltipName, dp), { sticky: true, className: "map-popup" });

        lyr.on("mouseover", e => {
          if (metricValue != null) {
            e.target.setStyle({ weight: 2.2, color: "#ffffff" });
            e.target.bringToFront();
          }
        });
        lyr.on("mouseout", () => state.geoLayer.resetStyle(lyr));

        // Only areas with data for the current filter are selectable.
        if (metricValue != null) {
          lyr.on("click", () => {
            if (state.selected.has(name)) state.selected.delete(name);
            else                          state.selected.add(name);
            renderLayer();      // recolor borders for selection state
            renderChart();      // chart filters to selection
            renderSelectionChips();
          });
        }
      },
    }).addTo(state.map);

    // Fit bounds the first time; afterwards keep current view so toggles
    // don't fight the user.
    if (!state.fitDone) {
      state.map.fitBounds(state.geoLayer.getBounds(), { padding: [10, 10] });
      state.fitDone = true;
    }
  }

  function buildTooltip(name, dp) {
    if (!dp) return `
      <div class="map-popup">
        <div class="name">${escapeHtml(name)}</div>
        <div class="row no-data-note">No data for ${escapeHtml(state.education)} · ${escapeHtml(state.year)}</div>
      </div>`;
    return `
      <div class="map-popup">
        <div class="name">${escapeHtml(name)}</div>
        <div class="row"><span>Men</span><span class="v">${formatKr(dp.Men)}</span></div>
        <div class="row"><span>Women</span><span class="v">${formatKr(dp.Women)}</span></div>
        <div class="row"><span>Gap</span><span class="v">${formatKr(dp.Gap)}</span></div>
      </div>`;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function formatKr(v) {
    if (v == null || !isFinite(v)) return "-";
    if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(2) + "M kr.";
    if (Math.abs(v) >= 1_000)     return (v / 1_000).toFixed(0) + "k kr.";
    return Math.round(v) + " kr.";
  }

  function formatPct(v) {
    if (v == null || !isFinite(v)) return "-";
    return v.toFixed(1) + "%";
  }

  function formatMetric(v) {
    return state.metric === "gap_pct" ? formatPct(v) : formatKr(v);
  }

  // -----------------------------------------------------------------------
  // 4. Chart
  // -----------------------------------------------------------------------

  /** Pull the current dataset for the chart based on selection + layer. */
  function getChartData() {
    const layerKey = state.layer;
    const dataDict = layerKey === "country"
      ? state.landsdelData
      : layerKey === "regions"
        ? state.regionData
        : state.muniData;
    const yearMap  = dataDict[state.year] ?? {};

    // If anything is selected, restrict to that. Otherwise use every area
    // with a data point at the current education level.
    let names;
    if (state.selected.size) {
      names = [...state.selected].filter(n => yearMap[n]?.[state.education]);
    } else {
      names = Object.keys(yearMap).filter(n => yearMap[n][state.education]);
    }

    // Sort by gap descending and cap at 12 for legibility (only when
    // selection is empty - selections always show all selected items).
    if (!state.selected.size && layerKey === "munis") {
      names.sort((a, b) => yearMap[b][state.education].Gap - yearMap[a][state.education].Gap);
      names = names.slice(0, 12);
    } else {
      names.sort((a, b) => yearMap[b][state.education].Gap - yearMap[a][state.education].Gap);
    }

    const points = names.map(n => ({ name: n, ...yearMap[n][state.education] }));
    return { layerKey, points };
  }

  function renderChart() {
    const titleEl    = document.getElementById("chart-title");
    const subtitleEl = document.getElementById("chart-subtitle");
    const canvas     = document.getElementById("main-chart");
    const tableHost  = document.getElementById("table-host");

    // Clean up previous render
    if (state.chart) { state.chart.destroy(); state.chart = null; }
    tableHost.classList.add("hidden");
    canvas.classList.remove("hidden");

    const { layerKey, points } = getChartData();
    const layerLabel = {
      country: "Subregions",
      regions: "Regions",
      munis: "Municipalities",
    }[layerKey] || "Areas";

    const incLabel = state.incomeType || 'Wages/salary';
    let titlePrefix = "Income Gap";
    let subtitleText = `How much more men earn than women in ${state.year} · [Men − Women] DKK (CPI-adjusted to 2024)`;

    if (state.metric === "compare") {
      titlePrefix = "Men vs Women Income";
      subtitleText = `Average ${incLabel.toLowerCase()} side-by-side, ${state.year} DKK (CPI-adjusted to 2024)`;
    } else if (state.metric === "gap_pct") {
      titlePrefix = "Income Gap (%)";
      subtitleText = `Pay gap as % of the higher earner's income in ${state.year} · [(1 − lower / higher) × 100]`;
    }

    titleEl.textContent =
      `${titlePrefix}: ${state.education} - ${layerLabel}` +
      (state.selected.size ? ` (${state.selected.size} selected)` : "");
    subtitleEl.textContent = subtitleText;

    if (!points.length) {
      titleEl.textContent += " - no data";
      return;
    }

    if (state.chartType === "bar")   renderBar(canvas, points);
    else if (state.chartType === "line")  renderLine(canvas, layerKey, points);
    else if (state.chartType === "table") renderTable(tableHost, canvas, points);

    renderDotPlot();
  }

  function chartBaseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: TEXT_PRIMARY, usePointStyle: true } },
        tooltip: {
          backgroundColor: "rgba(15, 17, 25, 0.95)",
          titleColor: "#fff",
          bodyColor: TEXT_PRIMARY,
          borderColor: "rgba(255,255,255,0.08)",
          borderWidth: 1,
          callbacks: {
            label: ctx => {
              const val = ctx.parsed.y ?? ctx.parsed;
              const formatted = state.metric === "gap_pct" ? val.toFixed(1) + "%" : formatKr(val);
              return `${ctx.dataset.label}: ${formatted}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: TEXT_SECONDARY, maxRotation: 45, minRotation: 0 },
          grid:  { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          ticks: {
            color: TEXT_SECONDARY,
            callback: v => state.metric === "gap_pct" ? v.toFixed(1) + "%" : formatKr(v),
          },
          grid:  { color: "rgba(255,255,255,0.05)" },
        },
      },
    };
  }

  function renderBar(canvas, points) {
    let datasets = [];
    if (state.metric === "compare") {
      datasets = [
        {
          label: "Men",
          data: points.map(p => p.Men),
          backgroundColor: ACCENT_BLUE,
          borderRadius: 6,
        },
        {
          label: "Women",
          data: points.map(p => p.Women),
          backgroundColor: ACCENT_PINK,
          borderRadius: 6,
        }
      ];
    } else if (state.metric === "gap_pct") {
      datasets = [{
        label: "Gap (%)",
        data: points.map(p => {
          const hi = Math.max(p.Men, p.Women);
          const lo = Math.min(p.Men, p.Women);
          return hi ? (1 - lo / hi) * 100 : null;
        }),
        backgroundColor: ACCENT_PURPLE,
        borderRadius: 6,
      }];
    } else {
      datasets = [{
        label: "Gap (kr.)",
        data: points.map(p => p.Gap),
        backgroundColor: ACCENT_PURPLE,
        borderRadius: 6,
      }];
    }

    state.chart = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: points.map(p => p.name),
        datasets: datasets,
      },
      options: chartBaseOptions(),
    });
  }

  /** Line chart = trend across ALL years for each chosen area. */
  function renderLine(canvas, layerKey, points) {
    const dataDict = layerKey === "country"
      ? state.landsdelData
      : layerKey === "regions"
        ? state.regionData
        : state.muniData;
    const years = state.meta.Years_Available;
    const palette = [ACCENT_BLUE, ACCENT_PINK, ACCENT_PURPLE, "#34d399", "#fbbf24", "#f87171"];

    // For line mode we cap to top 6 by latest-year gap if no selection.
    const areas = (state.selected.size
      ? [...state.selected]
      : points.slice(0, 6).map(p => p.name)
    );

    let datasets = [];
    if (state.metric === "compare") {
      areas.forEach((name, i) => {
        datasets.push({
          label: `${name} (Men)`,
          data: years.map(y => {
            const dp = dataDict[String(y)]?.[name]?.[state.education];
            return dp ? dp.Men : null;
          }),
          borderColor: palette[i % palette.length],
          backgroundColor: palette[i % palette.length] + "22",
          tension: 0.3,
          pointRadius: 3,
          spanGaps: true,
          borderDash: []
        });
        datasets.push({
          label: `${name} (Women)`,
          data: years.map(y => {
            const dp = dataDict[String(y)]?.[name]?.[state.education];
            return dp ? dp.Women : null;
          }),
          borderColor: palette[i % palette.length],
          backgroundColor: palette[i % palette.length] + "22",
          tension: 0.3,
          pointRadius: 3,
          spanGaps: true,
          borderDash: [5, 5]
        });
      });
    } else {
      datasets = areas.map((name, i) => {
        return {
          label: name,
          data: years.map(y => {
            const dp = dataDict[String(y)]?.[name]?.[state.education];
            if (!dp) return null;
            if (state.metric === "gap_pct") {
              const hi = Math.max(dp.Men, dp.Women);
              const lo = Math.min(dp.Men, dp.Women);
              return hi ? (1 - lo / hi) * 100 : null;
            }
            return dp.Gap;
          }),
          borderColor: palette[i % palette.length],
          backgroundColor: palette[i % palette.length] + "22",
          tension: 0.3,
          pointRadius: 3,
          spanGaps: true,
        };
      });
    }

    state.chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels: years, datasets },
      options: chartBaseOptions(),
    });

    let titlePrefix = "Gap Trend";
    let subtitleText = `${state.incomeType || 'Wages/salary'} gap (Men − Women), 2024 DKK · ${areas.length} areas`;
    
    if (state.metric === "compare") {
      titlePrefix = "Men vs Women Trend";
      subtitleText = `Average ${state.incomeType ? state.incomeType.toLowerCase() : 'Wages/salary'}, 2024 DKK · ${areas.length} areas`;
    } else if (state.metric === "gap_pct") {
      titlePrefix = "Gap Trend (%)";
      subtitleText = `${state.incomeType || 'Wages/salary'} gap as % of the higher earner's income · (1 − lower / higher) × 100 · ${areas.length} areas`;
    }

    document.getElementById("chart-title").textContent =
      `${titlePrefix}: ${state.education}`;
    document.getElementById("chart-subtitle").textContent = subtitleText;
  }

  /** Normalized education-share dot plot.
   *  For each selected area, shows what % of people (within the current
   *  income type) have each education level. Values are normalized per
   *  area so different-sized regions/municipalities are directly comparable. */
  function renderDotPlot() {
    const canvas  = document.getElementById("dot-plot-canvas");
    const titleEl = document.getElementById("dot-plot-title");
    const subEl   = document.getElementById("dot-plot-subtitle");

    if (state.dotChart) { state.dotChart.destroy(); state.dotChart = null; }

    const eduLevels = state.meta.Education_Levels;
    const layerKey  = state.layer;
    const dataDict  = layerKey === "country"
      ? state.landsdelData
      : layerKey === "regions"
        ? state.regionData
        : state.muniData;
    const yearMap = dataDict[state.year] ?? {};

    // Prefer selected areas; otherwise fall back to top 6 by gap at the
    // currently-selected education level so the chart is never empty.
    let areas;
    if (state.selected.size) {
      areas = [...state.selected].filter(n => yearMap[n]);
    } else {
      const allNames = Object.keys(yearMap).filter(n => yearMap[n]?.[state.education]);
      allNames.sort((a, b) => yearMap[b][state.education].Gap - yearMap[a][state.education].Gap);
      areas = allNames.slice(0, 6);
    }

    if (!areas.length) return;

    const palette = [
      "#3b82f6", "#ec4899", "#34d399", "#fbbf24", "#f87171",
      "#a78bfa", "#fb923c", "#22d3ee", "#4ade80", "#f472b6",
    ];

    // For each area: pull the count(s) per education level, divide by the
    // area's total → percentage share. Keeps the X-axis comparable across
    // areas of different sizes.
    const splitMode = state.dotSplit === "gender";
    const datasets = [];
    areas.forEach((name, i) => {
      const color = palette[i % palette.length];
      if (!splitMode) {
        const counts = eduLevels.map(edu => yearMap[name]?.[edu]?.Count ?? 0);
        const total  = counts.reduce((a, b) => a + b, 0);
        const data   = counts
          .map((c, j) => (total > 0 ? { x: (c / total) * 100, y: j, count: c } : null))
          .filter(Boolean);
        datasets.push({
          label: name,
          data,
          backgroundColor: color,
          borderColor: color,
          pointStyle: "circle",
          pointRadius: 7,
          pointHoverRadius: 10,
          showLine: false,
          $area: name,
          $gender: null,
        });
      } else {
        // Per-gender shares: each gender normalised to its own total so
        // the M and F distributions are independently comparable.
        // Y is offset above/below the row centerline so the two genders
        // stack visibly and the connector lines stay aligned with the dots.
        const mCounts = eduLevels.map(edu => yearMap[name]?.[edu]?.Men_Count   ?? 0);
        const fCounts = eduLevels.map(edu => yearMap[name]?.[edu]?.Women_Count ?? 0);
        const mTotal  = mCounts.reduce((a, b) => a + b, 0);
        const fTotal  = fCounts.reduce((a, b) => a + b, 0);
        const Y_OFFSET = 0.14;

        datasets.push({
          label: `${name} · Men`,
          data: mCounts
            .map((c, j) => (mTotal > 0 ? { x: (c / mTotal) * 100, y: j - Y_OFFSET, count: c } : null))
            .filter(Boolean),
          backgroundColor: color,
          borderColor: color,
          pointStyle: "circle",
          pointRadius: 7,
          pointHoverRadius: 10,
          showLine: false,
          $area: name,
          $gender: "M",
        });
        datasets.push({
          label: `${name} · Women`,
          data: fCounts
            .map((c, j) => (fTotal > 0 ? { x: (c / fTotal) * 100, y: j + Y_OFFSET, count: c } : null))
            .filter(Boolean),
          backgroundColor: color,
          borderColor: color,
          pointStyle: "triangle",
          pointRadius: 8,
          pointHoverRadius: 11,
          showLine: false,
          $area: name,
          $gender: "F",
        });
      }
    });

    const layerLabel = { country: "Subregions", regions: "Regions", munis: "Municipalities" }[layerKey];
    const incomeLabel = state.incomeType || "Wages";
    titleEl.textContent = `Education Distribution - ${layerLabel}, ${state.year}`;
    subEl.textContent   = state.selected.size
      ? `Share of people by education in ${state.selected.size} selected area${state.selected.size > 1 ? "s" : ""} (normalized per area)`
      : `Share of people by education · top 6 ${layerLabel.toLowerCase()} (normalized per area)`;

    // Draws subtle row bands so each education level reads as its own
    // horizontal lane (label sits inside the band, not on a gridline).
    const rowBandsPlugin = {
      id: "rowBands",
      beforeDatasetsDraw(chart) {
        const { ctx, scales, chartArea } = chart;
        const yScale = scales.y;
        if (!yScale || !chartArea) return;
        ctx.save();

        // Faint zebra fill on every other row.
        for (let j = 0; j < eduLevels.length; j++) {
          if (j % 2 !== 0) continue;
          const yTop = yScale.getPixelForValue(j + 0.5);
          const yBot = yScale.getPixelForValue(j - 0.5);
          ctx.fillStyle = "rgba(255,255,255,0.025)";
          ctx.fillRect(chartArea.left, yTop, chartArea.right - chartArea.left, yBot - yTop);
        }

        // Crisp separators between rows.
        ctx.strokeStyle = "rgba(255,255,255,0.06)";
        ctx.lineWidth = 1;
        for (let j = 0; j < eduLevels.length - 1; j++) {
          const py = yScale.getPixelForValue(j + 0.5);
          ctx.beginPath();
          ctx.moveTo(chartArea.left, py);
          ctx.lineTo(chartArea.right, py);
          ctx.stroke();
        }
        ctx.restore();
      },
    };

    // Draws a thin connector from min-X to max-X dot on each education row.
    // Sits underneath the dots so they stay readable. afterEvent hit-tests
    // the connector for hover and shows a small spread tooltip.
    const HIT_TOLERANCE = 8;
    const rangeLinesPlugin = {
      id: "rangeLines",
      beforeDatasetsDraw(chart) {
        const { ctx, scales } = chart;
        const xScale = scales.x, yScale = scales.y;
        if (!xScale || !yScale) return;

        chart.$rangeLines = [];
        ctx.save();
        ctx.lineWidth = 2;

        // Bucket points by row + gender (gender null in combined mode).
        const buckets = new Map(); // key: `${j}|${gender}` -> { j, gender, xs: [] }
        chart.data.datasets.forEach((ds, i) => {
          const meta = chart.getDatasetMeta(i);
          if (meta.hidden) return;
          ds.data.forEach(pt => {
            if (!pt) return;
            const j = Math.round(pt.y);
            const key = `${j}|${ds.$gender ?? ""}`;
            if (!buckets.has(key)) buckets.set(key, { j, gender: ds.$gender ?? null, xs: [] });
            buckets.get(key).xs.push(pt.x);
          });
        });

        const yOffsetFor = g => g === "M" ? -0.14 : g === "F" ? 0.14 : 0;

        for (const { j, gender, xs } of buckets.values()) {
          if (xs.length < 2) continue;
          const xMin = Math.min(...xs);
          const xMax = Math.max(...xs);
          const py    = yScale.getPixelForValue(j + yOffsetFor(gender));
          const pxMin = xScale.getPixelForValue(xMin);
          const pxMax = xScale.getPixelForValue(xMax);

          ctx.strokeStyle = gender ? "rgba(255,255,255,0.22)" : "rgba(255,255,255,0.28)";
          ctx.beginPath();
          ctx.moveTo(pxMin, py);
          ctx.lineTo(pxMax, py);
          ctx.stroke();

          chart.$rangeLines.push({ j, gender, xMin, xMax, py, pxMin, pxMax });
        }
        ctx.restore();
      },
      afterEvent(chart, args) {
        const e = args.event;
        if (e.type !== "mousemove" && e.type !== "mouseout") return;

        const tip = ensureRangeTooltip();
        if (e.type === "mouseout" || !chart.$rangeLines) {
          tip.style.opacity = "0";
          return;
        }

        // If the cursor is on an actual dot, defer to Chart.js's own tooltip.
        const onDot = chart.getElementsAtEventForMode(e, "nearest", { intersect: true }, true);
        if (onDot.length) { tip.style.opacity = "0"; return; }

        let hit = null;
        for (const ln of chart.$rangeLines) {
          if (Math.abs(e.y - ln.py) <= HIT_TOLERANCE &&
              e.x >= ln.pxMin - HIT_TOLERANCE && e.x <= ln.pxMax + HIT_TOLERANCE) {
            hit = ln;
            break;
          }
        }

        if (!hit) { tip.style.opacity = "0"; return; }

        const diff = hit.xMax - hit.xMin;
        const genderLabel = hit.gender === "M" ? " · Men"
                          : hit.gender === "F" ? " · Women"
                          : "";
        tip.innerHTML =
          `<div class="r-row"><span>${eduLevels[hit.j]}${genderLabel}</span></div>` +
          `<div class="r-row"><span>Highest</span><span class="v">${hit.xMax.toFixed(1)}%</span></div>` +
          `<div class="r-row"><span>Lowest</span><span class="v">${hit.xMin.toFixed(1)}%</span></div>` +
          `<div class="r-row r-diff"><span>Difference</span><span class="v">${diff.toFixed(1)} pp</span></div>`;
        tip.style.left = `${(hit.pxMin + hit.pxMax) / 2}px`;
        tip.style.top  = `${hit.py - 12}px`;
        tip.style.opacity = "1";
      },
    };

    function ensureRangeTooltip() {
      let tip = document.getElementById("range-line-tooltip");
      if (!tip) {
        tip = document.createElement("div");
        tip.id = "range-line-tooltip";
        tip.className = "range-tooltip";
        document.querySelector(".dot-plot-wrapper")?.appendChild(tip);
      }
      return tip;
    }

    state.dotChart = new Chart(canvas.getContext("2d"), {
      type: "scatter",
      data: { datasets },
      plugins: [rowBandsPlugin, rangeLinesPlugin],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: TEXT_PRIMARY, usePointStyle: true } },
          tooltip: {
            backgroundColor: "rgba(15, 17, 25, 0.95)",
            titleColor: "#fff",
            bodyColor: TEXT_PRIMARY,
            borderColor: "rgba(255,255,255,0.08)",
            borderWidth: 1,
            usePointStyle: true,
            callbacks: {
              title: ctx => ctx[0].dataset.label,
              label: ctx => {
                const edu = eduLevels[Math.round(ctx.parsed.y)] ?? "";
                const cnt = ctx.raw?.count;
                const cntStr = cnt != null ? ` (${cnt.toLocaleString()})` : "";
                return `${edu}: ${ctx.parsed.x.toFixed(1)}%${cntStr}`;
              },
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: `Share of people (%)`, color: TEXT_SECONDARY, font: { size: 11 } },
            ticks: { color: TEXT_SECONDARY, callback: v => v.toFixed(0) + "%" },
            grid:  { color: "rgba(255,255,255,0.05)" },
            min: 0,
          },
          y: {
            type: "linear",
            min: -0.5,
            max: eduLevels.length - 0.5,
            ticks: {
              color: TEXT_SECONDARY,
              stepSize: 1,
              callback: val => eduLevels[Math.round(val)] ?? "",
            },
            afterBuildTicks: axis => {
              axis.ticks = eduLevels.map((_, j) => ({ value: j }));
            },
            // Default gridlines pass through the labels and dots; we draw
            // our own lines between rows via the rowBands plugin instead.
            grid: { drawOnChartArea: false, color: "rgba(255,255,255,0.05)" },
          },
        },
      },
    });
  }

  function renderTable(tableHost, canvas, points) {
    canvas.classList.add("hidden");
    tableHost.classList.remove("hidden");
    tableHost.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Area</th>
            <th class="num">Men</th>
            <th class="num">Women</th>
            <th class="num">Gap</th>
          </tr>
        </thead>
        <tbody>
          ${points.map(p => `
            <tr>
              <td>${escapeHtml(p.name)}</td>
              <td class="num">${formatKr(p.Men)}</td>
              <td class="num">${formatKr(p.Women)}</td>
              <td class="num">${formatKr(p.Gap)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>`;
  }

  function renderSelectionChips() {
    const list = document.getElementById("selection-list");
    if (!state.selected.size) {
      list.innerHTML = `<span class="empty">None - showing all visible areas</span>`;
      return;
    }
    list.innerHTML = [...state.selected].map(name => `
      <span class="chip">
        ${escapeHtml(name)}
        <button type="button" data-name="${escapeHtml(name)}" aria-label="Remove">×</button>
      </span>
    `).join("");
    list.querySelectorAll("button").forEach(btn => {
      btn.addEventListener("click", () => {
        state.selected.delete(btn.dataset.name);
        renderLayer();
        renderChart();
        renderSelectionChips();
      });
    });
  }

  // -----------------------------------------------------------------------
  // 5. Wire up controls
  // -----------------------------------------------------------------------
  function setupControls() {
    document.getElementById("income-select").addEventListener("change", e => {
      state.incomeType = e.target.value;
      state.nationalData = state.fullData[state.incomeType].National_Data;
      state.landsdelData = state.fullData[state.incomeType].Landsdel_Data || {};
      state.regionData   = state.fullData[state.incomeType].Region_Data;
      state.muniData     = state.fullData[state.incomeType].Municipality_Data;
      renderLayer();
      renderChart();
    });

    document.getElementById("education-select").addEventListener("change", e => {
      state.education = e.target.value;
      renderLayer();
      renderChart();
    });

    document.getElementById("year-select").addEventListener("change", e => {
      state.year = e.target.value;
      // Drop selections that no longer have data in the new year.
      const dict = state.layer === "country"
        ? state.landsdelData
        : state.layer === "munis"
          ? state.muniData
          : state.regionData;
      const valid = dict[state.year] ?? {};
      [...state.selected].forEach(n => {
        if (!valid[n]) state.selected.delete(n);
      });
      renderLayer();
      renderChart();
      renderSelectionChips();
    });

    document.querySelectorAll(".metric-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".metric-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.metric = btn.dataset.metric;
        renderLayer();
        renderChart();
      });
    });

    document.querySelectorAll(".viz-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".viz-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.chartType = btn.dataset.viz;
        renderChart();
      });
    });

    document.querySelectorAll(".layer-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".layer-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.layer = btn.dataset.layer;
        // Different layer = different name space for selection; clear it.
        state.selected.clear();
        state.fitDone = false;
        renderLayer();
        renderChart();
        renderSelectionChips();
      });
    });

    document.getElementById("clear-selection").addEventListener("click", () => {
      state.selected.clear();
      renderLayer();
      renderChart();
      renderSelectionChips();
    });

    document.querySelectorAll(".split-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".split-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.dotSplit = btn.dataset.split;
        renderDotPlot();
      });
    });

    document.getElementById("update-btn").addEventListener("click", () => {
      // Force a clean re-render. Useful as a "reset rendering" button.
      renderLayer();
      renderChart();
    });
  }

  // -----------------------------------------------------------------------
  // Boot
  // -----------------------------------------------------------------------
  async function main() {
    try {
      await fetchAll();
      populateControls();
      initMap();
      setupControls();
      renderLayer();
      renderChart();
    } catch (err) {
      console.error("Dashboard failed to initialize:", err);
      document.getElementById("map").innerHTML =
        `<div style="padding:2rem;color:#f87171">Failed to load data - see console.<br>` +
        `If you're opening index.html with file://, you need to serve it via a local web server ` +
        `(fetch() can't read local files).</div>`;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }

})();
