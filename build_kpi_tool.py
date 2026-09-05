import os
import json

with open('scratch_csv.txt', 'r', encoding='utf-8') as f:
    csv_raw = f.read().strip()

# Strip any leading backticks or quotes
while csv_raw.startswith('`') or csv_raw.startswith('"'):
    csv_raw = csv_raw[1:]
while csv_raw.endswith('`') or csv_raw.endswith('"'):
    csv_raw = csv_raw[:-1]
csv_raw = csv_raw.strip()

# Escape for inclusion in JS template literal
csv_escaped = csv_raw.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Universal KPI Builder & Record Explorer</title>
  <style>
    :root {{
      --bg: #0B1118;
      --panel: #121B26;
      --panel2: #182330;
      --panel-hover: #1F2D3D;
      --border: #24313F;
      --border-light: rgba(255, 255, 255, 0.08);
      --text: #EDF1F5;
      --muted: #8393A3;
      --amber: #F2A93B;
      --amber-soft: rgba(242, 169, 59, 0.15);
      --teal: #35C7B3;
      --teal-soft: rgba(53, 199, 179, 0.15);
      --coral: #E8674A;
      --blue: #6E9FE8;
      --purple: #B98BDE;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      min-height: 100vh;
      padding: 24px;
      line-height: 1.5;
    }}

    /* Scrollbars */
    ::-webkit-scrollbar {{ width: 7px; height: 7px; }}
    ::-webkit-scrollbar-track {{ background: var(--bg); }}
    ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: var(--muted); }}

    .container {{ max-width: 1380px; margin: 0 auto; }}

    /* Header & Hero Stats */
    .hero {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 20px;
    }}

    .hero-title h1 {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #fff;
    }}

    .hero-title p {{
      color: var(--muted);
      font-size: 13.5px;
      margin-top: 4px;
    }}

    .hero-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 8px;
    }}

    .btn-file {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--panel2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    .btn-file:hover {{
      border-color: var(--teal);
      color: #fff;
    }}

    .hero-stats {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .hero-stat {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px 18px;
      min-width: 105px;
      text-align: center;
    }}
    .hero-stat .num {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 22px;
      font-weight: 700;
      color: var(--amber);
      line-height: 1.1;
    }}
    .hero-stat .lbl {{
      font-size: 11px;
      color: var(--muted);
      margin-top: 4px;
      text-transform: lowercase;
    }}

    /* Tabs */
    .tabs {{
      display: flex;
      gap: 8px;
      margin-bottom: 20px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }}
    .tab-btn {{
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
      padding: 8px 18px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    .tab-btn:hover {{
      color: var(--text);
      border-color: var(--muted);
    }}
    .tab-btn.active {{
      background: var(--panel2);
      color: #fff;
      border-color: var(--teal);
      box-shadow: 0 0 12px rgba(53, 199, 179, 0.25);
    }}

    /* KPI Dashboard Layout */
    .dashboard-layout {{
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 20px;
      align-items: start;
    }}
    @media (max-width: 900px) {{
      .dashboard-layout {{ grid-template-columns: 1fr; }}
    }}

    .builder-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      position: sticky;
      top: 20px;
    }}

    .builder-card h2 {{
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 14px;
      color: #fff;
    }}

    /* Presets */
    .preset-list {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 18px;
    }}
    .preset-btn {{
      background: transparent;
      border: 1px dashed var(--border);
      color: var(--muted);
      font-size: 12px;
      padding: 7px 10px;
      border-radius: 5px;
      cursor: pointer;
      text-align: left;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }}
    .preset-btn:hover {{
      border-color: var(--teal);
      color: var(--teal);
      background: var(--teal-soft);
    }}

    /* Steps */
    .step {{
      margin-bottom: 18px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--border);
    }}
    .step:last-of-type {{ border-bottom: none; }}

    .step-head {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 10px;
      color: #fff;
    }}
    .step-badge {{
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: var(--amber);
      color: #1A1206;
      font-family: ui-monospace, monospace;
      font-size: 11px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}

    .radio-group {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .radio-opt {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12.5px;
      cursor: pointer;
      color: var(--muted);
      padding: 4px 6px;
      border-radius: 4px;
      transition: background 0.15s;
    }}
    .radio-opt:hover {{ background: var(--panel2); }}
    .radio-opt.active {{ color: var(--text); font-weight: 500; }}
    .radio-opt input {{ accent-color: var(--amber); cursor: pointer; }}

    select, input[type="text"] {{
      width: 100%;
      background: var(--panel2);
      border: 1px solid var(--border);
      color: var(--text);
      font-size: 12.5px;
      padding: 8px 10px;
      border-radius: 5px;
      margin-top: 6px;
      outline: none;
      transition: border-color 0.15s;
    }}
    select:focus, input[type="text"]:focus {{
      border-color: var(--teal);
    }}

    .filter-inputs {{
      display: flex;
      gap: 6px;
    }}
    .filter-inputs select {{ margin-top: 0; }}

    .agg-pills {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 5px;
      margin-top: 6px;
    }}
    .agg-pill {{
      background: var(--panel2);
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 11px;
      padding: 5px;
      border-radius: 4px;
      text-align: center;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s ease;
    }}
    .agg-pill:hover {{ color: #fff; border-color: var(--muted); }}
    .agg-pill.active {{
      background: var(--amber);
      color: #1A1206;
      border-color: var(--amber);
    }}

    .chip-row {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    .viz-chip {{
      font-size: 11.5px;
      padding: 5px 11px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: var(--panel2);
      color: var(--muted);
      cursor: pointer;
      font-family: ui-monospace, monospace;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .viz-chip:hover {{ color: var(--text); border-color: var(--muted); }}
    .viz-chip.active {{
      border-color: var(--amber);
      color: var(--amber);
      background: var(--amber-soft);
      font-weight: 600;
    }}
    .viz-chip.suggested::after {{
      content: "★";
      font-size: 9px;
      color: var(--teal);
    }}

    .preview-box {{
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 14px;
      margin-top: 8px;
    }}
    .preview-box .lbl {{
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
    }}
    .preview-box .title {{
      font-size: 13.5px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 6px;
    }}
    .preview-box .val {{
      font-family: ui-monospace, monospace;
      font-size: 24px;
      font-weight: 700;
      color: var(--teal);
    }}

    .btn-add {{
      width: 100%;
      margin-top: 14px;
      background: var(--amber);
      color: #1A1206;
      border: none;
      border-radius: 6px;
      padding: 11px;
      font-size: 13.5px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: transform 0.12s ease, filter 0.15s ease;
    }}
    .btn-add:hover {{
      filter: brightness(1.08);
      transform: translateY(-1px);
    }}

    /* Dashboard Grid */
    .dashboard-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }}
    .dashboard-header h2 {{ font-size: 16px; font-weight: 700; }}
    .btn-clear {{
      background: transparent;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 11.5px;
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
    }}
    .btn-clear:hover {{ color: var(--coral); border-color: var(--coral); }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }}

    .tile {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      position: relative;
      animation: tileFadeIn 0.2s ease;
      min-height: 170px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    @keyframes tileFadeIn {{
      from {{ opacity: 0; transform: scale(0.98); }}
      to {{ opacity: 1; transform: scale(1); }}
    }}

    .tile-chart, .tile-table {{
      grid-column: span 2;
    }}
    @media (max-width: 650px) {{
      .tile-chart, .tile-table {{ grid-column: span 1; }}
    }}

    .tile-del {{
      position: absolute;
      top: 10px;
      right: 10px;
      background: transparent;
      border: none;
      color: var(--muted);
      font-size: 16px;
      cursor: pointer;
      line-height: 1;
      padding: 4px;
    }}
    .tile-del:hover {{ color: var(--coral); }}

    .tile-title {{
      font-size: 12.5px;
      font-weight: 600;
      color: var(--muted);
      margin-bottom: 8px;
      padding-right: 20px;
    }}
    .tile-num {{
      font-family: ui-monospace, monospace;
      font-size: 32px;
      font-weight: 700;
      color: var(--amber);
      line-height: 1.1;
      margin-top: 6px;
    }}
    .tile-sub {{
      font-size: 11px;
      color: var(--muted);
      margin-top: 8px;
    }}

    /* SVG Charts inside tiles */
    .chart-container {{
      width: 100%;
      height: 170px;
      margin-top: 10px;
    }}
    .bar-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 7px;
      font-size: 11px;
    }}
    .bar-lbl {{ width: 110px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .bar-val {{ width: 60px; text-align: right; color: var(--teal); font-family: ui-monospace, monospace; font-weight: 600; }}
    .bar-track {{ flex: 1; height: 7px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--amber), #ffc107); border-radius: 4px; }}

    /* Explorer Layout */
    .explorer {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
    }}

    .explorer-controls {{
      display: flex;
      flex-direction: column;
      gap: 12px;
      margin-bottom: 16px;
    }}

    .search-wrap {{
      position: relative;
    }}
    .search-wrap input {{
      padding-left: 34px;
      margin-top: 0;
      font-size: 13.5px;
      background: var(--panel2);
      border-radius: 6px;
    }}
    .search-icon {{
      position: absolute;
      left: 11px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-size: 14px;
      pointer-events: none;
    }}
    .clear-search-btn {{
      position: absolute;
      right: 10px;
      top: 50%;
      transform: translateY(-50%);
      background: none;
      border: none;
      color: var(--muted);
      font-size: 14px;
      cursor: pointer;
    }}

    .filter-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    @media (max-width: 700px) {{
      .filter-grid {{ grid-template-columns: 1fr; }}
    }}

    .filter-pair {{
      display: flex;
      gap: 6px;
    }}
    .filter-pair select {{ margin-top: 0; }}

    .explorer-body {{
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 16px;
      align-items: start;
    }}
    @media (max-width: 900px) {{
      .explorer-body {{ grid-template-columns: 1fr; }}
    }}

    .results-column {{
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--panel2);
      overflow: hidden;
    }}

    .results-head {{
      padding: 10px 14px;
      font-size: 11.5px;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .results-list {{
      max-height: 540px;
      overflow-y: auto;
    }}

    .result-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 11px 14px;
      border-bottom: 1px solid var(--border-light);
      cursor: pointer;
      transition: background 0.15s ease, border-color 0.15s ease;
      font-size: 12.5px;
      color: var(--text);
      user-select: none;
    }}
    .result-row:hover {{
      background: var(--panel-hover);
    }}
    .result-row.active {{
      background: rgba(53, 199, 179, 0.12);
      border-left: 3px solid var(--teal);
      color: #fff;
    }}
    .result-main {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      padding-right: 8px;
    }}
    .result-arrow {{
      color: var(--muted);
      font-size: 12px;
    }}
    .result-row.active .result-arrow {{
      color: var(--teal);
    }}

    .pagination-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      border-top: 1px solid var(--border);
      background: var(--panel);
      font-size: 11px;
      color: var(--muted);
    }}
    .pg-btn {{
      background: var(--panel2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 3px 8px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 11px;
    }}
    .pg-btn:disabled {{
      opacity: 0.4;
      cursor: not-allowed;
    }}

    /* Record Detail Panel */
    .detail-panel {{
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 16px;
      min-height: 380px;
    }}
    .detail-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 12px;
      margin-bottom: 14px;
      border-bottom: 1px solid var(--border);
    }}
    .detail-header h3 {{
      font-size: 15px;
      font-weight: 700;
      color: #fff;
    }}
    .btn-modal-open {{
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--teal);
      font-size: 11.5px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
    }}
    .btn-modal-open:hover {{
      border-color: var(--teal);
      background: var(--teal-soft);
    }}

    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 10px;
      max-height: 480px;
      overflow-y: auto;
      padding-right: 4px;
    }}

    .detail-cell {{
      background: var(--panel);
      border: 1px solid var(--border-light);
      border-radius: 5px;
      padding: 9px 12px;
    }}
    .detail-cell .k {{
      font-size: 10.5px;
      color: var(--muted);
      text-transform: capitalize;
      margin-bottom: 3px;
    }}
    .detail-cell .v {{
      font-size: 12.5px;
      font-weight: 600;
      color: #fff;
      word-break: break-word;
    }}
    .detail-cell .v.num {{
      font-family: ui-monospace, monospace;
      color: var(--teal);
    }}
    .detail-cell .v.empty {{
      color: var(--muted);
      font-weight: 400;
    }}

    /* Fullscreen Detail Modal */
    .modal-backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 1000;
    }}
    .modal-content {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      max-width: 960px;
      width: 100%;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 10px 40px rgba(0,0,0,0.6);
    }}
    .modal-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
    }}
    .modal-head h3 {{ font-size: 16px; font-weight: 700; color: #fff; }}
    .modal-close {{
      background: none;
      border: none;
      color: var(--muted);
      font-size: 20px;
      cursor: pointer;
    }}
    .modal-body {{
      padding: 20px;
      overflow-y: auto;
    }}

    .empty-state {{
      border: 1px dashed var(--border);
      border-radius: 6px;
      padding: 30px;
      text-align: center;
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header with Stats -->
    <header class="hero">
      <div class="hero-title">
        <h1>Universal KPI builder</h1>
        <p>Pick any column, choose how to measure it, and add it to your dashboard — or search every record directly across any dataset.</p>
        <div class="hero-actions">
          <label class="btn-file">
            <span>📁 Load Custom CSV</span>
            <input type="file" id="csvFileInput" accept=".csv" style="display:none" onchange="handleFileUpload(event)" />
          </label>
          <button class="btn-file" onclick="resetToSample()">↺ Reset Sample Data</button>
        </div>
      </div>
      <div class="hero-stats" id="heroStats">
        <!-- Rendered dynamically -->
      </div>
    </header>

    <!-- Tabs -->
    <nav class="tabs">
      <button class="tab-btn active" id="tabBtnDashboard" onclick="switchTab('dashboard')">KPI dashboard</button>
      <button class="tab-btn" id="tabBtnExplore" onclick="switchTab('explore')">Explore records</button>
    </nav>

    <!-- TAB 1: KPI DASHBOARD -->
    <section id="tabDashboard" class="dashboard-layout">
      <!-- Left Form: Builder -->
      <div class="builder-card">
        <h2>Build a KPI</h2>

        <!-- Quick Presets -->
        <div class="preset-list" id="presetList">
          <!-- Rendered dynamically -->
        </div>

        <!-- Step 1: What to measure -->
        <div class="step">
          <div class="step-head">
            <span class="step-badge">1</span>
            <span>What do you want to measure?</span>
          </div>
          <div class="radio-group">
            <label class="radio-opt active" id="lblMeasureNum">
              <input type="radio" name="measureType" value="number" checked onchange="onMeasureTypeChange('number')" />
              <span>A number (sum, average, min, max)</span>
            </label>
            <label class="radio-opt" id="lblMeasureRate">
              <input type="radio" name="measureType" value="rate" onchange="onMeasureTypeChange('rate')" />
              <span>A rate or percentage (%)</span>
            </label>
            <label class="radio-opt" id="lblMeasureCount">
              <input type="radio" name="measureType" value="count" onchange="onMeasureTypeChange('count')" />
              <span>Just count records</span>
            </label>
          </div>

          <div id="measureNumControls" style="margin-top: 10px;">
            <select id="selMeasureCol" onchange="onMeasureColChange(this.value)"></select>
            <div class="agg-pills">
              <div class="agg-pill active" id="agg_avg" onclick="setAggFn('avg')">AVG</div>
              <div class="agg-pill" id="agg_sum" onclick="setAggFn('sum')">TOTAL</div>
              <div class="agg-pill" id="agg_min" onclick="setAggFn('min')">MIN</div>
              <div class="agg-pill" id="agg_max" onclick="setAggFn('max')">MAX</div>
            </div>
          </div>

          <div id="measureRateControls" style="margin-top: 10px; display: none;">
            <select id="selRateCol" onchange="onRateColChange(this.value)"></select>
          </div>
        </div>

        <!-- Step 2: Breakdown by -->
        <div class="step">
          <div class="step-head">
            <span class="step-badge">2</span>
            <span>Break down by</span>
          </div>
          <select id="selBreakdown" onchange="onBreakdownChange(this.value)">
            <option value="none">No breakdown — one total</option>
          </select>
        </div>

        <!-- Step 3: Filter (optional) -->
        <div class="step">
          <div class="step-head">
            <span class="step-badge">3</span>
            <span>Filter (optional)</span>
          </div>
          <div class="filter-inputs">
            <select id="selFilterKey" onchange="onFilterKeyChange(this.value)">
              <option value="none">No filter</option>
            </select>
            <select id="selFilterVal" onchange="onFilterValChange(this.value)" style="display:none;">
              <option value="__all__">All</option>
            </select>
          </div>
        </div>

        <!-- Step 4: Show as -->
        <div class="step">
          <div class="step-head">
            <span class="step-badge">4</span>
            <span>Show as</span>
          </div>
          <div class="chip-row" id="vizChips">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <!-- Live Preview Box -->
        <div class="preview-box">
          <div class="lbl">Live Preview</div>
          <div class="title" id="previewTitle">Average Delay</div>
          <div class="val" id="previewVal">--</div>
        </div>

        <button class="btn-add" onclick="addCurrentKpiToDashboard()">+ Add to dashboard</button>
      </div>

      <!-- Right Panel: Dashboard Tiles -->
      <div>
        <div class="dashboard-header">
          <h2>Your dashboard</h2>
          <button class="btn-clear" onclick="clearAllTiles()">Clear all</button>
        </div>
        <div class="grid" id="dashboardGrid">
          <!-- Rendered dynamically -->
        </div>
      </div>
    </section>

    <!-- TAB 2: RECORD EXPLORER -->
    <section id="tabExplore" class="explorer" style="display: none;">
      <div class="explorer-controls">
        <div class="search-wrap">
          <span class="search-icon">🔍</span>
          <input
            type="text"
            id="globalSearchInput"
            placeholder="Search any field across all columns..."
            oninput="onSearchInput(this.value)"
          />
          <button class="clear-search-btn" id="clearSearchBtn" style="display:none;" onclick="clearSearch()">✕</button>
        </div>

        <div class="filter-grid">
          <div class="filter-pair">
            <select id="expFilterKey1" onchange="onExpFilterKeyChange(1, this.value)">
              <option value="none">Filter by...</option>
            </select>
            <select id="expFilterVal1" onchange="onExpFilterValChange(1, this.value)">
              <option value="__all__">All</option>
            </select>
          </div>
          <div class="filter-pair">
            <select id="expFilterKey2" onchange="onExpFilterKeyChange(2, this.value)">
              <option value="none">And filter by...</option>
            </select>
            <select id="expFilterVal2" onchange="onExpFilterValChange(2, this.value)">
              <option value="__all__">All</option>
            </select>
          </div>
        </div>
      </div>

      <div class="explorer-body">
        <!-- Records List -->
        <div class="results-column">
          <div class="results-head">
            <span id="resultsCount">0 records</span>
            <span>Click row to view</span>
          </div>
          <div class="results-list" id="resultsList">
            <!-- Rows rendered dynamically -->
          </div>
          <div class="pagination-bar">
            <button class="pg-btn" id="btnPrevPage" onclick="changePage(-1)">← Prev</button>
            <span id="pageIndicator">Page 1 of 1</span>
            <button class="pg-btn" id="btnNextPage" onclick="changePage(1)">Next →</button>
          </div>
        </div>

        <!-- Detail Inspector -->
        <div class="detail-panel" id="detailPanel">
          <div class="detail-header">
            <h3 id="detailHeaderTitle">Record Details</h3>
            <button class="btn-modal-open" onclick="openDetailModal()">Fullscreen Modal ↗</button>
          </div>
          <div class="detail-grid" id="detailGrid">
            <!-- Grid of 33+ columns rendered dynamically -->
          </div>
        </div>
      </div>
    </section>
  </div>

  <!-- Detail Fullscreen Modal -->
  <div class="modal-backdrop" id="detailModal" style="display: none;" onclick="closeDetailModal()">
    <div class="modal-content" onclick="event.stopPropagation()">
      <div class="modal-head">
        <h3 id="modalRecordTitle">Full Row Inspector</h3>
        <button class="modal-close" onclick="closeDetailModal()">✕</button>
      </div>
      <div class="modal-body">
        <div class="detail-grid" id="modalDetailGrid" style="max-height: 65vh;"></div>
      </div>
    </div>
  </div>

  <!-- Pure Vanilla JavaScript Engine (Zero CDNs, 100% Reliable) -->
  <script>
    const EMBEDDED_CSV = `{csv_escaped}`;

    const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const ACCENTS = ['#F2A93B', '#35C7B3', '#E8674A', '#6E9FE8', '#B98BDE', '#7FD17A', '#E0C46C', '#5FA8D3'];
    const UNIT_HINTS = {{
      DelayMinutes: {{ unit: 'min' }},
      DurationMinutes: {{ unit: 'min' }},
      DistanceKM: {{ unit: 'km' }},
      Capacity: {{ unit: 'seats' }},
      Passengers: {{ unit: 'pax' }},
      LoadFactor: {{ unit: '%', scale: 100 }},
      TicketPriceUSD: {{ unit: '$', prefix: true }},
    }};

    // State
    let rawDataset = [];
    let datasetFields = [];
    let schema = {{ boolean: [], numeric: [], categorical: [], identifier: [] }};
    let activeTab = 'dashboard';

    // Builder Form State
    let currentSpec = {{
      measureType: 'number',
      measureCol: '',
      aggFn: 'avg',
      rateCol: '',
      breakdown: 'none',
      filterKey: 'none',
      filterVal: '__all__',
      vizOverride: null
    }};

    // Dashboard Saved Tiles
    let savedTiles = [];

    // Explorer State
    let searchQuery = '';
    let expFilter1 = {{ key: 'none', val: '__all__' }};
    let expFilter2 = {{ key: 'none', val: '__all__' }};
    let currentPage = 1;
    const pageSize = 40;
    let selectedRecord = null;

    // --- CSV PARSER ---
    function parseCSV(text) {{
      const lines = text.split(/\\r?\\n/).filter(l => l.trim().length > 0);
      if (lines.length < 2) return {{ rows: [], fields: [] }};

      const parseLine = (line) => {{
        const res = [];
        let cur = '';
        let inQuotes = false;
        for (let i = 0; i < line.length; i++) {{
          const ch = line[i];
          if (ch === '"') inQuotes = !inQuotes;
          else if (ch === ',' && !inQuotes) {{
            res.push(cur.trim());
            cur = '';
          }} else {{
            cur += ch;
          }}
        }}
        res.push(cur.trim());
        return res;
      }};

      const fields = parseLine(lines[0]).map(h => h.replace(/^["'`]|["'`]$/g, '').trim());
      const rows = [];

      for (let i = 1; i < lines.length; i++) {{
        const vals = parseLine(lines[i]);
        if (vals.length !== fields.length) continue;
        const row = {{}};
        fields.forEach((f, idx) => {{
          let val = vals[idx].replace(/^["']|["']$/g, '').trim();
          if (val === '') {{
            row[f] = null;
          }} else if (!isNaN(Number(val))) {{
            row[f] = Number(val);
          }} else if (val.toLowerCase() === 'true') {{
            row[f] = 1;
          }} else if (val.toLowerCase() === 'false') {{
            row[f] = 0;
          }} else {{
            row[f] = val;
          }}
        }});
        rows.push(row);
      }}

      return {{ rows, fields }};
    }}

    // --- SCHEMA INFERENCE ---
    function detectSchema(rows, fields) {{
      const total = rows.length;
      const boolean = [], numeric = [], categorical = [], identifier = [];

      fields.forEach(key => {{
        const values = rows.map(r => r[key]).filter(v => v !== null && v !== undefined && v !== '');
        if (values.length === 0) {{ identifier.push(key); return; }}

        const uniqueSet = new Set(values.map(String));
        const uniqueCount = uniqueSet.size;
        const allNumeric = values.every(v => typeof v === 'number' && !isNaN(v));
        const isBinary = allNumeric && uniqueCount <= 2 && [...uniqueSet].every(v => v === '0' || v === '1');

        if (isBinary) {{
          boolean.push(key);
        }} else if (allNumeric && uniqueCount > 15) {{
          numeric.push(key);
        }} else if (uniqueCount / total > 0.85 && uniqueCount > 30) {{
          identifier.push(key);
        }} else {{
          categorical.push(key);
        }}
      }});

      return {{ boolean, numeric, categorical, identifier }};
    }}

    function prettify(key) {{
      return key
        .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
        .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
        .trim();
    }}

    function labelFor(key, stripIs = false) {{
      const k = stripIs && key.startsWith('Is') ? key.slice(2) : key;
      return prettify(k);
    }}

    // --- METRIC AGGREGATION ---
    function aggregate(rows, measureType, measureKey, aggFn) {{
      if (rows.length === 0) return null;
      if (measureType === 'count') return rows.length;
      if (measureType === 'rate') {{
        const trueCount = rows.filter(r => Number(r[measureKey]) === 1).length;
        return (trueCount / rows.length) * 100;
      }}
      const nums = rows.map(r => Number(r[measureKey])).filter(v => !isNaN(v));
      if (nums.length === 0) return null;
      if (aggFn === 'sum') return nums.reduce((a, b) => a + b, 0);
      if (aggFn === 'min') return Math.min(...nums);
      if (aggFn === 'max') return Math.max(...nums);
      return nums.reduce((a, b) => a + b, 0) / nums.length;
    }}

    function formatValue(value, measureType, measureKey) {{
      if (value === null || value === undefined || isNaN(value)) return '--';
      if (measureType === 'rate') return `${{value.toFixed(1)}}%`;
      if (measureType === 'count') return Math.round(value).toLocaleString();
      const hint = UNIT_HINTS[measureKey] || {{}};
      const scaled = value * (hint.scale || 1);
      const rounded = Math.abs(scaled) >= 100 ? Math.round(scaled) : Math.round(scaled * 10) / 10;
      const numStr = rounded.toLocaleString();
      if (hint.prefix) return `${{hint.unit}}${{numStr}}`;
      return `${{numStr}}${{hint.unit ? ' ' + hint.unit : ''}}`;
    }}

    function formatCellValue(key, val) {{
      if (val === null || val === undefined || val === '') return '--';
      if (schema.boolean.includes(key)) return Number(val) === 1 ? 'Yes' : 'No';
      const hint = UNIT_HINTS[key];
      if (hint && typeof val === 'number') {{
        const scaled = val * (hint.scale || 1);
        const rounded = Math.abs(scaled) >= 100 ? Math.round(scaled) : Math.round(scaled * 10) / 10;
        const numStr = rounded.toLocaleString();
        return hint.prefix ? `${{hint.unit}}${{numStr}}` : `${{numStr}}${{hint.unit ? ' ' + hint.unit : ''}}`;
      }}
      return String(val);
    }}

    // --- COMPUTE KPI RESULT ---
    function computeResult(spec) {{
      let rows = rawDataset;
      if (spec.filterKey !== 'none' && spec.filterVal !== '__all__') {{
        rows = rows.filter(r => String(r[spec.filterKey]) === String(spec.filterVal));
      }}

      const targetCol = spec.measureType === 'rate' ? spec.rateCol : spec.measureCol;

      if (spec.breakdown === 'none') {{
        const val = aggregate(rows, spec.measureType, targetCol, spec.aggFn);
        return {{ kind: 'single', value: val, sampleSize: rows.length, suggestedViz: 'kpi' }};
      }}

      const groups = {{}};
      rows.forEach(r => {{
        let g = r[spec.breakdown];
        if (g === undefined || g === null || g === '') return;
        if (spec.breakdown === 'Month' && typeof g === 'number') g = MONTH_NAMES[g - 1] || g;
        if (!groups[g]) groups[g] = [];
        groups[g].push(r);
      }});

      let entries = Object.keys(groups).map(g => ({{
        name: String(g),
        value: aggregate(groups[g], spec.measureType, targetCol, spec.aggFn),
        count: groups[g].length
      }})).filter(e => e.value !== null);

      const isTemporal = spec.breakdown === 'Month' || spec.breakdown === 'DayOfWeek' || spec.breakdown === 'Year';
      if (isTemporal) {{
        entries.sort((a, b) => {{
          if (spec.breakdown === 'Month') return MONTH_NAMES.indexOf(a.name) - MONTH_NAMES.indexOf(b.name);
          if (spec.breakdown === 'DayOfWeek') return DAY_ORDER.indexOf(a.name) - DAY_ORDER.indexOf(b.name);
          return a.name.localeCompare(b.name);
        }});
      }} else {{
        entries.sort((a, b) => b.value - a.value);
      }}

      let suggestedViz = 'bar';
      if (isTemporal) suggestedViz = 'line';
      else if (entries.length <= 5) suggestedViz = 'pie';

      return {{
        kind: 'grouped',
        entries: entries.slice(0, 15),
        totalGroups: entries.length,
        sampleSize: rows.length,
        suggestedViz
      }};
    }}

    function buildTitle(spec) {{
      const bk = spec.breakdown !== 'none' ? ` by ${{labelFor(spec.breakdown)}}` : '';
      let base = '';
      if (spec.measureType === 'count') {{
        base = 'Record count';
      }} else if (spec.measureType === 'rate') {{
        base = `% ${{labelFor(spec.rateCol, true)}}`;
      }} else {{
        const aggName = {{ avg: 'Average', sum: 'Total', min: 'Min', max: 'Max' }}[spec.aggFn] || 'Average';
        base = `${{aggName}} ${{labelFor(spec.measureCol)}}`;
      }}
      return `${{base}}${{bk}}`;
    }}

    // --- INITIALIZATION ---
    function initData(csvText) {{
      const parsed = parseCSV(csvText);
      rawDataset = parsed.rows;
      datasetFields = parsed.fields;
      schema = detectSchema(rawDataset, datasetFields);

      // Default Spec
      currentSpec.measureCol = schema.numeric.find(c => c.toLowerCase().includes('delay')) || schema.numeric[0] || '';
      currentSpec.rateCol = schema.boolean[0] || '';
      currentSpec.breakdown = 'none';

      // Explorer default filter
      expFilter1.key = schema.categorical[0] || 'none';
      expFilter1.val = '__all__';

      renderHeroStats();
      renderPresets();
      populateDropdowns();
      renderVizChips();
      updateLivePreview();

      // Explorer init
      selectedRecord = rawDataset[0] || null;
      renderExplorer();
    }}

    function renderHeroStats() {{
      const total = rawDataset.length;
      const dims = schema.categorical.slice(0, 2);
      const uniqueA = dims[0] ? new Set(rawDataset.map(r => r[dims[0]])).size : 0;
      const uniqueB = dims[1] ? new Set(rawDataset.map(r => r[dims[1]])).size : 0;
      const onTimeCol = datasetFields.includes('Status') ? 'Status' : null;
      const onTimeCount = onTimeCol ? rawDataset.filter(r => r[onTimeCol] === 'On Time').length : null;
      const onTimePct = onTimeCount !== null && total > 0 ? ((onTimeCount / total) * 100).toFixed(1) : null;

      let html = `
        <div class="hero-stat">
          <div class="num">${{total.toLocaleString()}}</div>
          <div class="lbl">records</div>
        </div>
      `;
      if (dims[0]) {{
        html += `
          <div class="hero-stat">
            <div class="num">${{uniqueA}}</div>
            <div class="lbl">${{labelFor(dims[0])}}s</div>
          </div>
        `;
      }}
      if (dims[1]) {{
        html += `
          <div class="hero-stat">
            <div class="num">${{uniqueB}}</div>
            <div class="lbl">${{labelFor(dims[1])}}s</div>
          </div>
        `;
      }}
      if (onTimePct) {{
        html += `
          <div class="hero-stat">
            <div class="num">${{onTimePct}}%</div>
            <div class="lbl">on time</div>
          </div>
        `;
      }}

      document.getElementById('heroStats').innerHTML = html;
    }}

    function renderPresets() {{
      const list = [];
      if (datasetFields.includes('IsDelayed')) {{
        list.push({{ title: '% Delayed flights', spec: {{ measureType: 'rate', rateCol: 'IsDelayed', breakdown: 'none' }} }});
      }}
      if (datasetFields.includes('DelayMinutes') && datasetFields.includes('Airline')) {{
        list.push({{ title: 'Avg Delay by Airline', spec: {{ measureType: 'number', measureCol: 'DelayMinutes', aggFn: 'avg', breakdown: 'Airline' }} }});
      }}
      if (datasetFields.includes('Month')) {{
        list.push({{ title: 'Flight Count by Month', spec: {{ measureType: 'count', breakdown: 'Month' }} }});
      }}
      if (datasetFields.includes('CabinClass')) {{
        list.push({{ title: 'Cabin Class Distribution', spec: {{ measureType: 'count', breakdown: 'CabinClass' }} }});
      }}

      const html = list.map((p, i) => `
        <button class="preset-btn" onclick="applyPreset(${{i}})">
          ✨ ${{p.title}}
        </button>
      `).join('');

      document.getElementById('presetList').innerHTML = html;
      window.__presets = list;
    }}

    function applyPreset(idx) {{
      const p = window.__presets[idx];
      if (!p) return;
      currentSpec = {{ ...currentSpec, ...p.spec, filterKey: 'none', filterVal: '__all__', vizOverride: null }};
      syncFormUI();
      updateLivePreview();
    }}

    function populateDropdowns() {{
      // Measure Col (Numeric)
      const numOpts = schema.numeric.map(c => `<option value="${{c}}">${{labelFor(c)}}</option>`).join('');
      document.getElementById('selMeasureCol').innerHTML = numOpts;
      document.getElementById('selMeasureCol').value = currentSpec.measureCol;

      // Rate Col (Boolean)
      const rateOpts = schema.boolean.map(c => `<option value="${{c}}">% ${{labelFor(c, true)}}</option>`).join('');
      document.getElementById('selRateCol').innerHTML = rateOpts;
      document.getElementById('selRateCol').value = currentSpec.rateCol;

      // Breakdown Dims
      const allDims = schema.categorical.concat(schema.boolean);
      const bkOpts = '<option value="none">No breakdown — one total</option>' +
        allDims.map(c => `<option value="${{c}}">${{labelFor(c)}}</option>`).join('');
      document.getElementById('selBreakdown').innerHTML = bkOpts;
      document.getElementById('selBreakdown').value = currentSpec.breakdown;

      // Filter Keys
      const filterOpts = '<option value="none">No filter</option>' +
        allDims.map(c => `<option value="${{c}}">${{labelFor(c)}}</option>`).join('');
      document.getElementById('selFilterKey').innerHTML = filterOpts;
      document.getElementById('selFilterKey').value = currentSpec.filterKey;

      // Explorer Filters
      const expOpts1 = '<option value="none">Filter by...</option>' +
        allDims.map(c => `<option value="${{c}}">${{labelFor(c)}}</option>`).join('');
      document.getElementById('expFilterKey1').innerHTML = expOpts1;
      document.getElementById('expFilterKey1').value = expFilter1.key;

      const expOpts2 = '<option value="none">And filter by...</option>' +
        allDims.map(c => `<option value="${{c}}">${{labelFor(c)}}</option>`).join('');
      document.getElementById('expFilterKey2').innerHTML = expOpts2;
      document.getElementById('expFilterKey2').value = expFilter2.key;

      updateExpFilterVals(1);
      updateExpFilterVals(2);
    }}

    function syncFormUI() {{
      // Measure Type
      document.querySelectorAll('input[name="measureType"]').forEach(r => {{
        r.checked = r.value === currentSpec.measureType;
      }});
      document.getElementById('lblMeasureNum').classList.toggle('active', currentSpec.measureType === 'number');
      document.getElementById('lblMeasureRate').classList.toggle('active', currentSpec.measureType === 'rate');
      document.getElementById('lblMeasureCount').classList.toggle('active', currentSpec.measureType === 'count');

      document.getElementById('measureNumControls').style.display = currentSpec.measureType === 'number' ? 'block' : 'none';
      document.getElementById('measureRateControls').style.display = currentSpec.measureType === 'rate' ? 'block' : 'none';

      document.querySelectorAll('.agg-pill').forEach(p => p.classList.remove('active'));
      const activeAgg = document.getElementById(`agg_${{currentSpec.aggFn}}`);
      if (activeAgg) activeAgg.classList.add('active');

      if (currentSpec.measureCol) document.getElementById('selMeasureCol').value = currentSpec.measureCol;
      if (currentSpec.rateCol) document.getElementById('selRateCol').value = currentSpec.rateCol;
      document.getElementById('selBreakdown').value = currentSpec.breakdown;
      document.getElementById('selFilterKey').value = currentSpec.filterKey;

      updateFilterValues();
      renderVizChips();
    }}

    function updateFilterValues() {{
      const key = currentSpec.filterKey;
      const valSel = document.getElementById('selFilterVal');
      if (key === 'none') {{
        valSel.style.display = 'none';
        return;
      }}
      valSel.style.display = 'block';
      const uniq = Array.from(new Set(rawDataset.map(r => r[key]))).filter(v => v !== null && v !== '').sort();
      valSel.innerHTML = '<option value="__all__">All</option>' + uniq.map(v => `<option value="${{v}}">${{v}}</option>`).join('');
      valSel.value = currentSpec.filterVal;
    }}

    function onMeasureTypeChange(val) {{
      currentSpec.measureType = val;
      syncFormUI();
      updateLivePreview();
    }}

    function onMeasureColChange(col) {{
      currentSpec.measureCol = col;
      updateLivePreview();
    }}

    function onRateColChange(col) {{
      currentSpec.rateCol = col;
      updateLivePreview();
    }}

    function setAggFn(fn) {{
      currentSpec.aggFn = fn;
      syncFormUI();
      updateLivePreview();
    }}

    function onBreakdownChange(val) {{
      currentSpec.breakdown = val;
      currentSpec.vizOverride = null;
      renderVizChips();
      updateLivePreview();
    }}

    function onFilterKeyChange(val) {{
      currentSpec.filterKey = val;
      currentSpec.filterVal = '__all__';
      updateFilterValues();
      updateLivePreview();
    }}

    function onFilterValChange(val) {{
      currentSpec.filterVal = val;
      updateLivePreview();
    }}

    function setVizChip(viz) {{
      currentSpec.vizOverride = viz;
      renderVizChips();
      updateLivePreview();
    }}

    function renderVizChips() {{
      const res = computeResult(currentSpec);
      const isGrouped = currentSpec.breakdown !== 'none';
      const activeViz = currentSpec.vizOverride || res.suggestedViz;

      let chips = [];
      if (!isGrouped) {{
        chips = [{{ id: 'kpi', label: 'KPI card' }}];
      }} else {{
        chips = [
          {{ id: 'bar', label: 'bar' }},
          {{ id: 'line', label: 'line' }},
          {{ id: 'pie', label: 'pie' }},
          {{ id: 'table', label: 'table' }}
        ];
      }}

      const html = chips.map(c => {{
        const isAct = c.id === activeViz;
        const isSugg = c.id === res.suggestedViz;
        return `
          <span class="viz-chip ${{isAct ? 'active' : ''}} ${{isSugg ? 'suggested' : ''}}" onclick="setVizChip('${{c.id}}')">
            ${{c.label}}
          </span>
        `;
      }}).join('');

      document.getElementById('vizChips').innerHTML = html;
    }}

    function updateLivePreview() {{
      const res = computeResult(currentSpec);
      const title = buildTitle(currentSpec);
      const targetCol = currentSpec.measureType === 'rate' ? currentSpec.rateCol : currentSpec.measureCol;

      document.getElementById('previewTitle').innerText = title;
      if (res.kind === 'single') {{
        document.getElementById('previewVal').innerText = formatValue(res.value, currentSpec.measureType, targetCol);
      }} else {{
        document.getElementById('previewVal').innerText = `${{res.entries.length}} groups`;
      }}
    }}

    // --- ADD / PERSIST TILES ---
    function addCurrentKpiToDashboard() {{
      const res = computeResult(currentSpec);
      const activeViz = currentSpec.vizOverride || res.suggestedViz;
      const targetCol = currentSpec.measureType === 'rate' ? currentSpec.rateCol : currentSpec.measureCol;

      const tile = {{
        id: 'kpi_' + Date.now(),
        title: buildTitle(currentSpec),
        spec: {{ ...currentSpec }},
        result: res,
        vizType: activeViz,
        targetCol: targetCol
      }};

      savedTiles.unshift(tile);
      saveTilesToStorage();
      renderDashboardGrid();
    }}

    function removeTile(id) {{
      savedTiles = savedTiles.filter(t => t.id !== id);
      saveTilesToStorage();
      renderDashboardGrid();
    }}

    function clearAllTiles() {{
      savedTiles = [];
      saveTilesToStorage();
      renderDashboardGrid();
    }}

    function saveTilesToStorage() {{
      try {{
        localStorage.setItem('flight_kpi_saved_tiles', JSON.stringify(savedTiles));
      }} catch (e) {{}}
    }}

    function loadTilesFromStorage() {{
      try {{
        const raw = localStorage.getItem('flight_kpi_saved_tiles');
        if (raw) savedTiles = JSON.parse(raw);
      }} catch (e) {{}}
    }}

    function renderDashboardGrid() {{
      const container = document.getElementById('dashboardGrid');
      if (savedTiles.length === 0) {{
        container.innerHTML = `
          <div class="empty-state" style="grid-column: 1 / -1;">
            Nothing here yet. Build a KPI on the left, or click a suggestion above, then add it to see it here.
          </div>
        `;
        return;
      }}

      const html = savedTiles.map(tile => {{
        const isSingle = tile.result.kind === 'single' || tile.vizType === 'kpi';
        const isChart = ['bar', 'line', 'pie'].includes(tile.vizType);

        let bodyHtml = '';
        if (isSingle) {{
          const numStr = formatValue(tile.result.value, tile.spec.measureType, tile.targetCol);
          bodyHtml = `
            <div>
              <div class="tile-num">${{numStr}}</div>
              <div class="tile-sub">${{tile.result.sampleSize.toLocaleString()}} records in sample</div>
            </div>
          `;
        }} else if (tile.vizType === 'table') {{
          bodyHtml = `
            <div style="max-height: 180px; overflow-y: auto; margin-top: 8px;">
              <table style="width:100%; font-size:11.5px; border-collapse: collapse;">
                <thead>
                  <tr style="color:var(--muted); text-align:left; border-bottom:1px solid var(--border);">
                    <th style="padding:4px 6px;">Group</th>
                    <th style="padding:4px 6px; text-align:right;">Value</th>
                    <th style="padding:4px 6px; text-align:right;">Count</th>
                  </tr>
                </thead>
                <tbody>
                  ${{tile.result.entries.slice(0, 8).map(e => `
                    <tr style="border-bottom:1px solid var(--border-light);">
                      <td style="padding:4px 6px; color:#fff;">${{e.name}}</td>
                      <td style="padding:4px 6px; text-align:right; color:var(--teal); font-family:monospace; font-weight:600;">
                        ${{formatValue(e.value, tile.spec.measureType, tile.targetCol)}}
                      </td>
                      <td style="padding:4px 6px; text-align:right; color:var(--muted); font-family:monospace;">${{e.count}}</td>
                    </tr>
                  `).join('')}}
                </tbody>
              </table>
            </div>
          `;
        }} else if (tile.vizType === 'bar') {{
          const maxVal = Math.max(...tile.result.entries.map(e => e.value), 0.001);
          bodyHtml = `
            <div class="chart-container" style="overflow-y:auto; max-height:160px;">
              ${{tile.result.entries.slice(0, 6).map(e => {{
                const pct = Math.max(0, Math.min(100, (e.value / maxVal) * 100));
                return `
                  <div class="bar-row">
                    <span class="bar-lbl" title="${{e.name}}">${{e.name}}</span>
                    <div class="bar-track">
                      <div class="bar-fill" style="width: ${{pct}}%;"></div>
                    </div>
                    <span class="bar-val">${{formatValue(e.value, tile.spec.measureType, tile.targetCol)}}</span>
                  </div>
                `;
              }}).join('')}}
            </div>
          `;
        }} else if (tile.vizType === 'line') {{
          bodyHtml = renderSvgLineChart(tile.result.entries, tile.spec.measureType, tile.targetCol);
        }} else if (tile.vizType === 'pie') {{
          const totalVal = tile.result.entries.reduce((a, b) => a + b.value, 0) || 1;
          bodyHtml = `
            <div style="display:flex; flex-direction:column; gap:6px; margin-top:8px;">
              ${{tile.result.entries.slice(0, 5).map((e, i) => `
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px;">
                  <span style="color:var(--text); display:flex; align-items:center; gap:6px;">
                    <span style="width:8px; height:8px; border-radius:50%; background:${{ACCENTS[i % ACCENTS.length]}};"></span>
                    ${{e.name}}
                  </span>
                  <span style="font-family:monospace; color:var(--teal); font-weight:600;">
                    ${{formatValue(e.value, tile.spec.measureType, tile.targetCol)}} (${{((e.value/totalVal)*100).toFixed(1)}}%)
                  </span>
                </div>
              `).join('')}}
            </div>
          `;
        }}

        return `
          <div class="tile ${{!isSingle ? 'tile-chart' : ''}}">
            <button class="tile-del" onclick="removeTile('${{tile.id}}')">✕</button>
            <div class="tile-title">${{tile.title}}</div>
            ${{bodyHtml}}
          </div>
        `;
      }}).join('');

      container.innerHTML = html;
    }}

    function renderSvgLineChart(entries, measureType, targetCol) {{
      if (entries.length < 2) return '<div style="color:var(--muted); font-size:12px;">Need multiple points for trend</div>';
      const W = 420;
      const H = 140;
      const PAD = 20;
      const vals = entries.map(e => e.value);
      const minV = Math.min(...vals);
      const maxV = Math.max(...vals);
      const range = maxV - minV || 1;

      const pts = entries.map((e, i) => {{
        const x = PAD + (i / (entries.length - 1)) * (W - PAD * 2);
        const y = H - PAD - ((e.value - minV) / range) * (H - PAD * 2);
        return [x, y];
      }});

      const pathD = pts.map((p, i) => `${{i === 0 ? 'M' : 'L'}} ${{p[0].toFixed(1)}} ${{p[1].toFixed(1)}}`).join(' ');
      const areaD = `${{pathD}} L ${{pts[pts.length - 1][0]}} ${{H - PAD}} L ${{pts[0][0]}} ${{H - PAD}} Z`;

      return `
        <div style="width:100%;">
          <svg viewBox="0 0 ${{W}} ${{H}}" style="width:100%; height:130px;">
            <defs>
              <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#35C7B3" stop-opacity="0.3" />
                <stop offset="100%" stop-color="#35C7B3" stop-opacity="0.0" />
              </linearGradient>
            </defs>
            <path d="${{areaD}}" fill="url(#lineGrad)" />
            <path d="${{pathD}}" fill="none" stroke="#35C7B3" stroke-width="2.5" />
            ${{pts.map(p => `<circle cx="${{p[0]}}" cy="${{p[1]}}" r="3" fill="#F2A93B" stroke="#121B26" stroke-width="1.5" />`).join('')}}
          </svg>
          <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--muted); margin-top:2px;">
            <span>${{entries[0].name}}</span>
            <span>${{entries[Math.floor(entries.length/2)].name}}</span>
            <span>${{entries[entries.length-1].name}}</span>
          </div>
        </div>
      `;
    }}

    // --- EXPLORER LOGIC ---
    function updateExpFilterVals(slot) {{
      const key = slot === 1 ? expFilter1.key : expFilter2.key;
      const sel = document.getElementById(`expFilterVal${{slot}}`);
      if (key === 'none') {{
        sel.innerHTML = '<option value="__all__">All</option>';
        return;
      }}
      const uniq = Array.from(new Set(rawDataset.map(r => r[key]))).filter(v => v !== null && v !== '').sort();
      sel.innerHTML = '<option value="__all__">All</option>' + uniq.map(v => `<option value="${{v}}">${{v}}</option>`).join('');
      sel.value = slot === 1 ? expFilter1.val : expFilter2.val;
    }}

    function onExpFilterKeyChange(slot, val) {{
      if (slot === 1) {{
        expFilter1.key = val;
        expFilter1.val = '__all__';
      }} else {{
        expFilter2.key = val;
        expFilter2.val = '__all__';
      }}
      updateExpFilterVals(slot);
      currentPage = 1;
      renderExplorer();
    }}

    function onExpFilterValChange(slot, val) {{
      if (slot === 1) expFilter1.val = val;
      else expFilter2.val = val;
      currentPage = 1;
      renderExplorer();
    }}

    function onSearchInput(val) {{
      searchQuery = val;
      document.getElementById('clearSearchBtn').style.display = val ? 'block' : 'none';
      currentPage = 1;
      renderExplorer();
    }}

    function clearSearch() {{
      searchQuery = '';
      document.getElementById('globalSearchInput').value = '';
      document.getElementById('clearSearchBtn').style.display = 'none';
      currentPage = 1;
      renderExplorer();
    }}

    function getFilteredRecords() {{
      return rawDataset.filter(row => {{
        if (expFilter1.key !== 'none' && expFilter1.val !== '__all__') {{
          if (String(row[expFilter1.key]) !== String(expFilter1.val)) return false;
        }}
        if (expFilter2.key !== 'none' && expFilter2.val !== '__all__') {{
          if (String(row[expFilter2.key]) !== String(expFilter2.val)) return false;
        }}
        if (searchQuery.trim()) {{
          const q = searchQuery.toLowerCase();
          const match = Object.values(row).some(v => String(v ?? '').toLowerCase().includes(q));
          if (!match) return false;
        }}
        return true;
      }});
    }}

    function renderExplorer() {{
      const filtered = getFilteredRecords();
      const totalCount = filtered.length;
      const totalPages = Math.ceil(totalCount / pageSize) || 1;
      if (currentPage > totalPages) currentPage = totalPages;

      document.getElementById('resultsCount').innerText = `${{totalCount.toLocaleString()}} ${{totalCount === 1 ? 'record' : 'records'}}`;
      document.getElementById('pageIndicator').innerText = `Page ${{currentPage}} of ${{totalPages}}`;
      document.getElementById('btnPrevPage').disabled = currentPage <= 1;
      document.getElementById('btnNextPage').disabled = currentPage >= totalPages;

      const pageRows = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

      // Best effort summary line
      const summaryKeys = ['FlightNumber', 'Route', 'Airline', 'Status'].filter(k => datasetFields.includes(k));
      const fallbackKeys = summaryKeys.length ? summaryKeys : datasetFields.slice(0, 4);

      if (pageRows.length === 0) {{
        document.getElementById('resultsList').innerHTML = `
          <div style="padding:24px 16px; text-align:center; color:var(--muted); font-size:12.5px;">
            No records match that search.
          </div>
        `;
      }} else {{
        document.getElementById('resultsList').innerHTML = pageRows.map((row, i) => {{
          const isAct = selectedRecord === row;
          const summary = fallbackKeys.map(k => row[k]).filter(Boolean).join(' · ') || `Record ${{(currentPage - 1) * pageSize + i + 1}}`;
          return `
            <div class="result-row ${{isAct ? 'active' : ''}}" onclick="selectRecordByRowIndex(${{(currentPage - 1) * pageSize + i}})">
              <span class="result-main">${{summary}}</span>
              <span class="result-arrow">›</span>
            </div>
          `;
        }}).join('');
      }}

      // Default select first row if current selected is not in filtered list
      if ((!selectedRecord || !filtered.includes(selectedRecord)) && pageRows.length > 0) {{
        selectedRecord = pageRows[0];
      }}

      renderRecordDetail();
    }}

    function selectRecordByRowIndex(idx) {{
      const filtered = getFilteredRecords();
      selectedRecord = filtered[idx];
      renderExplorer();
    }}

    function renderRecordDetail() {{
      if (!selectedRecord) {{
        document.getElementById('detailHeaderTitle').innerText = 'No Record Selected';
        document.getElementById('detailGrid').innerHTML = '<div class="empty-state">Select a record on the left to see every field.</div>';
        return;
      }}

      const recordLabel = selectedRecord.FlightNumber || selectedRecord.FlightID || selectedRecord.ID || selectedRecord.id || (datasetFields && datasetFields.length > 0 ? selectedRecord[datasetFields[0]] : null) || 'Record';
      document.getElementById('detailHeaderTitle').innerText = `${{recordLabel}} Details (${{datasetFields.length}} Columns)`;

      const gridHtml = datasetFields.map(field => {{
        const val = selectedRecord[field];
        const isNum = typeof val === 'number';
        const formatted = formatCellValue(field, val);
        const isNull = val === null || val === undefined || val === '';

        return `
          <div class="detail-cell">
            <div class="k">${{labelFor(field)}}</div>
            <div class="v ${{isNum ? 'num' : ''}} ${{isNull ? 'empty' : ''}}">${{formatted}}</div>
          </div>
        `;
      }}).join('');

      document.getElementById('detailGrid').innerHTML = gridHtml;
      document.getElementById('modalDetailGrid').innerHTML = gridHtml;
      document.getElementById('modalRecordTitle').innerText = `${{recordLabel}} Complete Row Inspector`;
    }}

    function openDetailModal() {{
      document.getElementById('detailModal').style.display = 'flex';
    }}

    function closeDetailModal() {{
      document.getElementById('detailModal').style.display = 'none';
    }}

    document.addEventListener('keydown', e => {{
      if (e.key === 'Escape') closeDetailModal();
    }});

    // --- TAB SWITCHING ---
    function switchTab(tab) {{
      activeTab = tab;
      document.getElementById('tabBtnDashboard').classList.toggle('active', tab === 'dashboard');
      document.getElementById('tabBtnExplore').classList.toggle('active', tab === 'explore');
      document.getElementById('tabDashboard').style.display = tab === 'dashboard' ? 'grid' : 'none';
      document.getElementById('tabExplore').style.display = tab === 'explore' ? 'block' : 'none';
    }}

    // --- FILE UPLOAD ---
    function handleFileUpload(e) {{
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = evt => {{
        const text = evt.target.result;
        initData(text);
      }};
      reader.readAsText(file);
    }}

    function resetToSample() {{
      initData(EMBEDDED_CSV);
    }}

    function changePage(delta) {{
      currentPage += delta;
      renderExplorer();
    }}

    // --- BOOTSTRAP ---
    window.addEventListener('DOMContentLoaded', () => {{
      loadTilesFromStorage();
      initData(EMBEDDED_CSV);
      renderDashboardGrid();
    }});
  </script>
</body>
</html>
'''

# Write to root, templates, and static
with open('flight_kpi_tool.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

os.makedirs('app/static', exist_ok=True)
with open('app/static/flight_kpi_tool.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

os.makedirs('app/templates', exist_ok=True)
with open('app/templates/flight_kpi_tool.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Successfully generated flight_kpi_tool.html with pure Vanilla JS and embedded 450 rows!")
