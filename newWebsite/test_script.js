const fs = require('fs');
const agg = JSON.parse(fs.readFileSync('dashboard_aggregation.json', 'utf8'));
const state = {
  meta: agg.Metadata,
  fullData: agg.Data,
  incomeType: null
};

try {
  state.meta.Income_Types.forEach(inc => {
    // simulated append
  });
  const defaultIncome = state.meta.Income_Types.includes("Wages/salary") ? "Wages/salary" : state.meta.Income_Types[0];
  state.incomeType = defaultIncome;

  state.nationalData = state.fullData[state.incomeType].National_Data;
  state.regionData   = state.fullData[state.incomeType].Region_Data;
  state.muniData     = state.fullData[state.incomeType].Municipality_Data;
  
  console.log("Success! nationalData keys:", Object.keys(state.nationalData));
} catch (e) {
  console.error("Error:", e);
}
