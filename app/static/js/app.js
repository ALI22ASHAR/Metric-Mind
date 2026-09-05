import { ApiClient } from './api.js';
import { DashboardRenderer } from './dashboard.js';
import { Uploader } from './uploader.js';
import { ChatDrawer } from './chat.js';
import { ChartManager } from './charts.js';

class MetricMindApp {
  constructor() {
    this.currentDatasetId = null;
  }

  async init() {
    this.setupEventListeners();
    this.setupExecutiveModals();
    this.setupSelfServiceKpiBuilder();
    Uploader.init((newDatasetId) => this.onDatasetUploaded(newDatasetId));
    ChatDrawer.init();
    await this.loadDatasets();
  }

  setupEventListeners() {
    const uploadModal = document.getElementById('upload-modal');
    const openUploadBtn = document.getElementById('btn-open-upload');
    const closeUploadBtn = document.getElementById('btn-close-upload');
    const datasetSelect = document.getElementById('dataset-select');

    if (openUploadBtn) {
      openUploadBtn.addEventListener('click', () => uploadModal.classList.add('active'));
    }
    if (closeUploadBtn) {
      closeUploadBtn.addEventListener('click', () => uploadModal.classList.remove('active'));
    }

    // KPI Modal Close
    document.getElementById('btn-close-kpi-modal')?.addEventListener('click', () => {
      document.getElementById('kpi-modal')?.classList.remove('active');
    });

    if (datasetSelect) {
      datasetSelect.addEventListener('change', (e) => {
        if (e.target.value) {
          this.switchDataset(e.target.value);
        }
      });
    }

    const deleteDatasetBtn = document.getElementById('btn-delete-dataset');
    if (deleteDatasetBtn) {
      deleteDatasetBtn.addEventListener('click', async () => {
        if (!this.currentDatasetId) return;
        const select = document.getElementById('dataset-select');
        const selectedText = select?.options[select.selectedIndex]?.text || 'this dataset';
        const confirmDelete = window.confirm(`Delete ${selectedText}?\nThis will permanently remove this dataset from the platform.`);
        if (!confirmDelete) return;

        try {
          deleteDatasetBtn.disabled = true;
          deleteDatasetBtn.style.opacity = '0.5';
          await ApiClient.deleteDataset(this.currentDatasetId);
          localStorage.removeItem('metricmind_active_dataset_id');
          await this.loadDatasets();
        } catch (err) {
          alert(`Failed to delete dataset: ${err.message}`);
        } finally {
          deleteDatasetBtn.disabled = false;
          deleteDatasetBtn.style.opacity = '1';
        }
      });
    }

    // Export Dropdown Toggle
    const exportDropdownBtn = document.getElementById('btn-export-dropdown');
    const exportMenu = document.getElementById('export-menu');
    if (exportDropdownBtn && exportMenu) {
      exportDropdownBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        exportMenu.style.display = exportMenu.style.display === 'flex' ? 'none' : 'flex';
      });
      document.addEventListener('click', () => {
        exportMenu.style.display = 'none';
      });
    }

    // Export Buttons
    document.getElementById('btn-export-csv')?.addEventListener('click', () => {
      if (this.currentDatasetId) window.open(`/api/v1/datasets/${this.currentDatasetId}/export/csv`, '_blank');
    });
    document.getElementById('btn-export-excel')?.addEventListener('click', () => {
      if (this.currentDatasetId) window.open(`/api/v1/datasets/${this.currentDatasetId}/export/excel`, '_blank');
    });
    document.getElementById('btn-export-report-md')?.addEventListener('click', () => {
      if (this.currentDatasetId) window.open(`/api/v1/datasets/${this.currentDatasetId}/export/report?format=markdown`, '_blank');
    });
    document.getElementById('btn-export-report-html')?.addEventListener('click', () => {
      if (this.currentDatasetId) window.open(`/api/v1/datasets/${this.currentDatasetId}/export/report?format=html`, '_blank');
    });
  }

  setupExecutiveModals() {
    // Executive Report Modal
    const reportModal = document.getElementById('report-modal');
    document.getElementById('btn-open-report')?.addEventListener('click', async () => {
      if (!this.currentDatasetId) return;
      reportModal.classList.add('active');
      const body = document.getElementById('report-body');
      body.innerHTML = '<p>Synthesizing comprehensive executive intelligence brief...</p>';
      try {
        const rep = await ApiClient.getExecutiveReport(this.currentDatasetId);
        document.getElementById('report-title-modal').innerText = rep.title || 'Executive Intelligence Report';
        
        let sectionsHtml = rep.sections.map(s => `
          <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-glass); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 1rem;">
            <h3 style="font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem; color: var(--accent-primary);">${s.title}</h3>
            <p style="margin-bottom: 0.5rem;">${s.content}</p>
            ${s.bullet_points && s.bullet_points.length ? `<ul style="padding-left: 1.25rem; font-size: 0.8125rem;">${s.bullet_points.map(b => `<li style="margin-bottom: 0.25rem;">${b}</li>`).join('')}</ul>` : ''}
          </div>
        `).join('');

        body.innerHTML = `
          <div style="margin-bottom: 1rem; font-size: 0.9375rem; color: var(--text-main); line-height: 1.5;">
            <p><strong>Executive Summary:</strong> ${rep.executive_summary}</p>
          </div>
          ${sectionsHtml}
        `;
      } catch (e) {
        body.innerHTML = `<p style="color: #f43f5e;">Failed to generate report: ${e.message}</p>`;
      }
    });
    document.getElementById('btn-close-report')?.addEventListener('click', () => {
      reportModal.classList.remove('active');
    });
    document.getElementById('btn-download-report-md')?.addEventListener('click', () => {
      if (this.currentDatasetId) window.open(`/api/v1/datasets/${this.currentDatasetId}/export/report?format=markdown`, '_blank');
    });
    document.getElementById('btn-download-report-html')?.addEventListener('click', () => {
      if (this.currentDatasetId) window.open(`/api/v1/datasets/${this.currentDatasetId}/export/report?format=html`, '_blank');
    });

    // 3. What-If Scenario Simulator Modal
    const scenarioModal = document.getElementById('scenario-modal');
    document.getElementById('btn-open-scenario')?.addEventListener('click', () => {
      if (!this.currentDatasetId) return;
      scenarioModal.classList.add('active');
      this.runScenarioSimulation();
    });
    document.getElementById('btn-close-scenario')?.addEventListener('click', () => {
      scenarioModal.classList.remove('active');
    });

    const updateSlider = (id, labelId) => {
      const slider = document.getElementById(id);
      slider?.addEventListener('input', () => {
        const val = parseInt(slider.value);
        document.getElementById(labelId).innerText = `${val >= 0 ? '+' : ''}${val}%`;
        this.runScenarioSimulation();
      });
    };
    updateSlider('slider-price', 'val-price-slider');
    updateSlider('slider-cost', 'val-cost-slider');
    updateSlider('slider-volume', 'val-volume-slider');

    // 4. Forecast Modal
    const forecastModal = document.getElementById('forecast-modal');
    const closeForecastModal = () => forecastModal?.classList.remove('active');
    document.getElementById('btn-close-forecast')?.addEventListener('click', closeForecastModal);
    forecastModal?.addEventListener('click', (event) => {
      if (event.target === forecastModal) closeForecastModal();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && forecastModal?.classList.contains('active')) {
        closeForecastModal();
      }
    });
    document.getElementById('btn-open-forecast')?.addEventListener('click', async () => {
      if (!this.currentDatasetId) return;
      forecastModal.classList.add('active');
      try {
        const dashboard = await ApiClient.getDefaultDashboard(this.currentDatasetId);
        const forecastMetric = dashboard.spec?.widgets?.find(widget => widget.type === 'kpi_card' && widget.metric_id)?.metric_id || 'total_records';
        const fc = await ApiClient.getForecast(this.currentDatasetId, forecastMetric, 3);
        ChartManager.renderForecastChart('forecast-canvas', fc.forecast, forecastMetric.replaceAll('_', ' '));
        document.getElementById('forecast-summary-text').innerText = 
          `${fc.summary} Projected change: ${fc.growth_rate_projected_pct.toFixed(1)}%.`;
      } catch (e) {
        document.getElementById('forecast-summary-text').innerText = `Forecast error: ${e.message}`;
      }
    });
    // 5. Custom Metric Formula Builder Modal
    const metricModal = document.getElementById('custom-metric-modal');
    document.getElementById('btn-open-metric-builder')?.addEventListener('click', async () => {
      if (!this.currentDatasetId) return;
      metricModal.classList.add('active');
      document.getElementById('metric-builder-status').style.display = 'none';
      
      // Populate available column chips
      try {
        const profile = await ApiClient.getQualityReport(this.currentDatasetId);
        const colContainer = document.getElementById('formula-token-chips');
        // Keep standard operator buttons and append column buttons
        const opsHtml = `
          <button class="formula-chip formula-chip-op" data-token="+">+</button>
          <button class="formula-chip formula-chip-op" data-token="-">-</button>
          <button class="formula-chip formula-chip-op" data-token="*">*</button>
          <button class="formula-chip formula-chip-op" data-token="/">/</button>
          <button class="formula-chip formula-chip-op" data-token="(">(</button>
          <button class="formula-chip formula-chip-op" data-token=")">)</button>
        `;
        const colChips = (profile.columns || []).map(c => `
          <button class="formula-chip" data-token="${c.name}">${c.name}</button>
        `).join('');
        colContainer.innerHTML = opsHtml + colChips;

        colContainer.querySelectorAll('.formula-chip').forEach(chip => {
          chip.onclick = () => {
            const input = document.getElementById('metric-formula-input');
            input.value = (input.value ? input.value + ' ' : '') + chip.dataset.token;
            input.focus();
          };
        });
      } catch (e) {
        console.warn('Failed to load columns for metric builder:', e);
      }
    });

    document.getElementById('btn-close-metric-builder')?.addEventListener('click', () => {
      metricModal.classList.remove('active');
    });

    document.getElementById('btn-save-custom-metric')?.addEventListener('click', async () => {
      if (!this.currentDatasetId) return;
      const label = document.getElementById('metric-label-input').value.trim();
      const formula = document.getElementById('metric-formula-input').value.trim();
      const formatType = document.getElementById('metric-format-select').value;
      const statusEl = document.getElementById('metric-builder-status');

      if (!label || !formula) {
        statusEl.style.display = 'block';
        statusEl.style.background = 'rgba(244, 63, 94, 0.2)';
        statusEl.style.color = '#f43f5e';
        statusEl.innerText = 'Please provide both a metric label and formula expression.';
        return;
      }

      try {
        const metricName = label.toLowerCase().replace(/[^a-z0-9_]/g, '_');
        await ApiClient.registerCustomMetric(this.currentDatasetId, {
          name: metricName,
          label: label,
          formula: formula,
          format_type: formatType,
        });

        statusEl.style.display = 'block';
        statusEl.style.background = 'rgba(16, 185, 129, 0.2)';
        statusEl.style.color = '#34d399';
        statusEl.innerText = 'Metric compiled and registered successfully! Refreshing dashboard...';

        setTimeout(async () => {
          metricModal.classList.remove('active');
          const dashData = await ApiClient.getDefaultDashboard(this.currentDatasetId);
          DashboardRenderer.render(dashData, this.currentDatasetId);
        }, 800);
      } catch (err) {
        statusEl.style.display = 'block';
        statusEl.style.background = 'rgba(244, 63, 94, 0.2)';
        statusEl.style.color = '#f43f5e';
        statusEl.innerText = err.message || 'Failed to compile custom metric.';
      }
    });

    // 6. PDF Dashboard 1-Click Export
    document.getElementById('btn-export-pdf')?.addEventListener('click', () => {
      if (!this.currentDatasetId) return;
      
      const element = document.getElementById('dashboard-view');
      if (window.html2pdf && element) {
        const opt = {
          margin: [10, 10, 10, 10],
          filename: `MetricMind_Executive_Dashboard_${this.currentDatasetId}.pdf`,
          image: { type: 'jpeg', quality: 0.98 },
          html2canvas: { scale: 2, useCORS: true, backgroundColor: '#0b0f19' },
          jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' }
        };
        window.html2pdf().set(opt).from(element).save();
      } else {
        window.open(`/api/v1/datasets/${this.currentDatasetId}/export/pdf`, '_blank');
      }
    });
  }

  async runScenarioSimulation() {
    if (!this.currentDatasetId) return;
    const priceShift = parseInt(document.getElementById('slider-price').value) / 100.0;
    const costShift = parseInt(document.getElementById('slider-cost').value) / 100.0;
    const volumeShift = parseInt(document.getElementById('slider-volume').value) / 100.0;

    try {
      const res = await ApiClient.simulateScenario(this.currentDatasetId, {
        price_change_pct: priceShift,
        cost_change_pct: costShift,
        volume_change_pct: volumeShift,
      });

      const grid = document.getElementById('scenario-results-grid');
      const revDiff = res.simulated_revenue - res.baseline_revenue;
      const profitDiff = res.simulated_profit - res.baseline_profit;

      grid.innerHTML = `
        <div class="glass-panel" style="padding: 0.75rem; text-align: center;">
          <div style="font-size: 0.6875rem; color: var(--text-muted);">Simulated Revenue</div>
          <div style="font-size: 1.125rem; font-weight: 700; color: var(--text-main);">$${(res.simulated_revenue).toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
          <div style="font-size: 0.6875rem; color: ${revDiff >= 0 ? '#10b981' : '#f43f5e'}; font-weight: 600;">${revDiff >= 0 ? '+' : ''}$${revDiff.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
        </div>
        <div class="glass-panel" style="padding: 0.75rem; text-align: center;">
          <div style="font-size: 0.6875rem; color: var(--text-muted);">Simulated Net Profit</div>
          <div style="font-size: 1.125rem; font-weight: 700; color: #10b981;">$${(res.simulated_profit).toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
          <div style="font-size: 0.6875rem; color: ${profitDiff >= 0 ? '#10b981' : '#f43f5e'}; font-weight: 600;">${profitDiff >= 0 ? '+' : ''}$${profitDiff.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
        </div>
        <div class="glass-panel" style="padding: 0.75rem; text-align: center;">
          <div style="font-size: 0.6875rem; color: var(--text-muted);">Simulated Margin</div>
          <div style="font-size: 1.125rem; font-weight: 700; color: var(--accent-primary);">${res.simulated_margin.toFixed(1)}%</div>
          <div style="font-size: 0.6875rem; color: ${res.simulated_margin >= res.baseline_margin ? '#10b981' : '#f43f5e'}; font-weight: 600;">${(res.simulated_margin - res.baseline_margin) >= 0 ? '+' : ''}${(res.simulated_margin - res.baseline_margin).toFixed(1)}% pts</div>
        </div>
      `;

      document.getElementById('scenario-takeaway').innerText = res.executive_takeaway || 'Simulation calculated deterministically in DuckDB.';
    } catch (e) {
      console.error('Scenario error:', e);
    }
  }

  async loadDatasets() {
    try {
      const data = await ApiClient.getDatasets();
      const select = document.getElementById('dataset-select');
      const deleteBtn = document.getElementById('btn-delete-dataset');
      select.innerHTML = '';
      const rawDatasets = data.items || data.datasets || [];

      // Deduplicate datasets by filename to prevent past duplicate clutter
      const datasets = [];
      const seenNames = new Set();
      for (const ds of rawDatasets) {
        if (!seenNames.has(ds.filename)) {
          seenNames.add(ds.filename);
          datasets.push(ds);
        }
      }

      if (datasets.length === 0) {
        this.currentDatasetId = null;
        localStorage.removeItem('metricmind_active_dataset_id');
        if (deleteBtn) deleteBtn.style.display = 'none';
        document.getElementById('no-dataset-view').style.display = 'block';
        document.getElementById('dashboard-view').style.display = 'none';
        const opt = document.createElement('option');
        opt.value = '';
        opt.innerText = 'No datasets available';
        select.appendChild(opt);
        return;
      }

      datasets.forEach((ds) => {
        const opt = document.createElement('option');
        opt.value = ds.id;
        opt.innerText = `${ds.filename} (${ds.row_count || 0} rows)`;
        select.appendChild(opt);
      });

      if (deleteBtn) deleteBtn.style.display = 'flex';

      // Pick previously active dataset if available in localStorage, otherwise pick the first
      const savedId = localStorage.getItem('metricmind_active_dataset_id');
      const matched = datasets.find((d) => d.id === savedId);
      const targetId = matched ? matched.id : datasets[0].id;

      select.value = targetId;
      await this.switchDataset(targetId);
    } catch (err) {
      console.error('Failed to load datasets:', err);
    }
  }

  async switchDataset(datasetId) {
    this.currentDatasetId = datasetId;
    localStorage.setItem('metricmind_active_dataset_id', datasetId);
    document.getElementById('no-dataset-view').style.display = 'none';
    document.getElementById('dashboard-view').style.display = 'block';

    const deleteBtn = document.getElementById('btn-delete-dataset');
    if (deleteBtn) deleteBtn.style.display = 'flex';

    // Update Chat Drawer active dataset
    ChatDrawer.setDataset(datasetId);

    try {
      // 1. Fetch AI Understanding & Quality
      this.loadMetadataBadges(datasetId);

      // 2. Fetch and render default dashboard
      const dashData = await ApiClient.getDefaultDashboard(datasetId);
      DashboardRenderer.render(dashData, datasetId);
    } catch (err) {
      console.error('Error switching dataset:', err);
    }
  }

  async loadMetadataBadges(datasetId) {
    try {
      const quality = await ApiClient.getQualityReport(datasetId);
      const qualityScore = quality?.overall_quality_score ?? 100;
    } catch (e) {
      // ignore
    }

    try {
      const understanding = await ApiClient.getAIUnderstanding(datasetId);
      const domainBadge = document.getElementById('domain-badge');
      if (domainBadge && understanding?.domain) {
        domainBadge.innerText = understanding.domain.replace(/_/g, ' ').toUpperCase();
        domainBadge.style.display = 'inline-flex';
      }
    } catch (e) {
      // ignore
    }
  }

  async onDatasetUploaded(newDatasetId) {
    localStorage.setItem('metricmind_active_dataset_id', newDatasetId);
    await this.loadDatasets();
    const select = document.getElementById('dataset-select');
    if (select) select.value = newDatasetId;
    await this.switchDataset(newDatasetId);
  }

  setupSelfServiceKpiBuilder() {
    const modal = document.getElementById('self-service-kpi-modal');
    const openBtn = document.getElementById('btn-open-kpi-builder');
    const closeBtn = document.getElementById('btn-close-kpi-builder');
    const cancelBtn = document.getElementById('btn-cancel-kpi-builder');
    const saveBtn = document.getElementById('btn-save-kpi-to-dash');

    const colSelect = document.getElementById('kpi-builder-col');
    const dimSelect = document.getElementById('kpi-builder-dim');
    const titleInput = document.getElementById('kpi-builder-title');
    const formatSelect = document.getElementById('kpi-builder-format');
    const unitInput = document.getElementById('kpi-builder-unit');
    const rateCondWrap = document.getElementById('kpi-rate-condition-wrap');
    const rateValInput = document.getElementById('rate-condition-value');
    const rateColSpan = document.getElementById('rate-condition-col-name');
    const errorBox = document.getElementById('kpi-builder-error');
    const autoReasonPill = document.getElementById('kpi-auto-reason-pill');
    const timingBadge = document.getElementById('kpi-preview-timing');
    const typeBadge = document.getElementById('col-data-type-badge');

    let currentAgg = 'avg';
    let currentVisual = 'auto';
    let debounceTimer = null;

    const closeModal = () => {
      modal?.classList.remove('active');
      ChartManager.destroyChart('kpi-preview-canvas');
    };

    const openModal = async () => {
      const activeId = this.currentDatasetId || document.getElementById('dataset-select')?.value;
      if (!activeId) {
        if (window.openFlightKpiModal) {
          window.openFlightKpiModal();
        } else {
          document.getElementById('upload-modal')?.classList.add('active');
        }
        return;
      }
      this.currentDatasetId = activeId;
      modal?.classList.add('active');
      if (errorBox) errorBox.style.display = 'none';

      try {
        let columnsInfo = [];
        try {
          const profile = await ApiClient.getDatasetProfile(this.currentDatasetId);
          columnsInfo = profile.columns_info || [];
        } catch (e) {
          console.warn('Profile fetch failed:', e);
        }

        const numericCols = [];
        const catCols = [];
        const dateCols = [];
        const boolCols = [];

        columnsInfo.forEach(c => {
          const detected = (c.detected_type || '').toLowerCase();
          const role = (c.role || '').toLowerCase();
          if (detected === 'boolean' || detected.includes('bool')) {
            boolCols.push(c);
          } else if (detected === 'numeric' || detected === 'integer' || detected === 'float' || role === 'measure') {
            numericCols.push(c);
          } else if (detected === 'temporal' || detected === 'date' || detected.includes('date') || detected.includes('time') || role.includes('time')) {
            dateCols.push(c);
          } else {
            catCols.push(c);
          }
        });

        let colHtml = '';
        if (numericCols.length) {
          colHtml += `<optgroup label="Numeric Measures">${numericCols.map(c => `<option value="${c.name}" data-type="numeric">${c.name}</option>`).join('')}</optgroup>`;
        }
        if (boolCols.length) {
          colHtml += `<optgroup label="Boolean Flags / Indicators">${boolCols.map(c => `<option value="${c.name}" data-type="boolean">${c.name}</option>`).join('')}</optgroup>`;
        }
        if (catCols.length) {
          colHtml += `<optgroup label="Categorical Dimensions">${catCols.map(c => `<option value="${c.name}" data-type="categorical">${c.name}</option>`).join('')}</optgroup>`;
        }
        if (dateCols.length) {
          colHtml += `<optgroup label="Temporal Dates">${dateCols.map(c => `<option value="${c.name}" data-type="temporal">${c.name}</option>`).join('')}</optgroup>`;
        }
        colSelect.innerHTML = colHtml;

        let dimHtml = '<option value="">(None - Single Metric KPI Card)</option>';
        if (catCols.length) {
          dimHtml += `<optgroup label="Categorical Segments">${catCols.map(c => `<option value="${c.name}">${c.name}</option>`).join('')}</optgroup>`;
        }
        if (dateCols.length) {
          dimHtml += `<optgroup label="Time-Series Progression">${dateCols.map(c => `<option value="${c.name}">${c.name}</option>`).join('')}</optgroup>`;
        }
        dimSelect.innerHTML = dimHtml;

        if (numericCols.length > 0) {
          const matchCol = numericCols.find(c => {
            const n = c.name.toLowerCase();
            return n.includes('delay') || n.includes('factor') || n.includes('passenger') || n.includes('price');
          }) || numericCols[0];
          colSelect.value = matchCol.name;
        } else if (boolCols.length > 0) {
          colSelect.value = boolCols[0].name;
        }

        syncColumnState();
        schedulePreview();
      } catch (err) {
        console.error('Failed to initialize KPI builder columns:', err);
      }
    };

    window.openCustomKpiBuilder = openModal;
    openBtn?.addEventListener('click', openModal);

    modal?.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal?.classList.contains('active')) {
        closeModal();
      }
    });

    closeBtn?.addEventListener('click', closeModal);
    cancelBtn?.addEventListener('click', closeModal);

    const aggButtons = document.querySelectorAll('.kpi-agg-btn');
    aggButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        aggButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentAgg = btn.dataset.agg;
        if (currentAgg === 'rate') {
          if (rateCondWrap) rateCondWrap.style.display = 'block';
          if (rateColSpan) rateColSpan.innerText = colSelect.value;
        } else {
          if (rateCondWrap) rateCondWrap.style.display = 'none';
        }
        updateDefaultTitle();
        schedulePreview();
      });
    });

    const visualButtons = document.querySelectorAll('.kpi-visual-btn');
    visualButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        visualButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentVisual = btn.dataset.type;
        schedulePreview();
      });
    });

    const syncColumnState = () => {
      const selectedOption = colSelect.options[colSelect.selectedIndex];
      const colType = selectedOption?.dataset?.type || 'numeric';
      if (typeBadge) typeBadge.innerText = colType.charAt(0).toUpperCase() + colType.slice(1);
      if (rateColSpan) rateColSpan.innerText = colSelect.value;

      if (colType === 'boolean') {
        aggButtons.forEach(b => b.classList.toggle('active', b.dataset.agg === 'rate'));
        currentAgg = 'rate';
        if (rateCondWrap) rateCondWrap.style.display = 'block';
        formatSelect.value = 'percentage';
        unitInput.value = '%';
      } else if (colType === 'numeric') {
        if (currentAgg === 'rate') {
          aggButtons.forEach(b => b.classList.toggle('active', b.dataset.agg === 'avg'));
          currentAgg = 'avg';
          if (rateCondWrap) rateCondWrap.style.display = 'none';
        }
        const colLower = (colSelect.value || '').toLowerCase();
        if (colLower.includes('delay')) {
          unitInput.value = 'min';
          formatSelect.value = 'duration';
        } else if (colLower.includes('price') || colLower.includes('revenue') || colLower.includes('cost')) {
          formatSelect.value = 'currency';
          unitInput.value = '';
        } else if (colLower.includes('rate') || colLower.includes('factor') || colLower.includes('pct') || colLower.includes('percent')) {
          formatSelect.value = 'percentage';
          unitInput.value = '%';
        } else {
          formatSelect.value = 'number';
          unitInput.value = '';
        }
      } else {
        aggButtons.forEach(b => b.classList.toggle('active', b.dataset.agg === 'count'));
        currentAgg = 'count';
        if (rateCondWrap) rateCondWrap.style.display = 'none';
        formatSelect.value = 'number';
        unitInput.value = '';
      }
      updateDefaultTitle();
    };

    const updateDefaultTitle = () => {
      const col = colSelect.value || '';
      const dim = dimSelect.value;
      let aggLabel = currentAgg.toUpperCase();
      if (currentAgg === 'avg') aggLabel = 'Average';
      if (currentAgg === 'sum') aggLabel = 'Total';
      if (currentAgg === 'count') aggLabel = 'Count of';
      if (currentAgg === 'rate') aggLabel = 'Rate of';
      if (currentAgg === 'percent_of_total') aggLabel = '% Share of';

      const prettyCol = col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      const prettyDim = dim ? dim.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : '';

      titleInput.value = `${aggLabel} ${prettyCol}` + (prettyDim ? ` by ${prettyDim}` : '');
    };

    colSelect?.addEventListener('change', () => {
      syncColumnState();
      schedulePreview();
    });

    dimSelect?.addEventListener('change', () => {
      updateDefaultTitle();
      schedulePreview();
    });

    formatSelect?.addEventListener('change', schedulePreview);
    unitInput?.addEventListener('input', schedulePreview);
    rateValInput?.addEventListener('input', schedulePreview);

    function schedulePreview() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => executePreview(), 160);
    }

    const executePreview = async () => {
      if (!this.currentDatasetId || !colSelect.value) return;

      if (errorBox) errorBox.style.display = 'none';
      let condVal = rateValInput?.value?.trim() ?? 'true';
      if (condVal.toLowerCase() === 'true') condVal = true;
      else if (condVal.toLowerCase() === 'false') condVal = false;
      else if (!isNaN(Number(condVal)) && condVal !== '') condVal = Number(condVal);

      const spec = {
        label: titleInput.value.trim() || 'Custom Metric',
        column: colSelect.value,
        aggregation: currentAgg,
        condition: currentAgg === 'rate' ? { operator: '==', value: condVal } : null,
        dimension: dimSelect.value || null,
        output_type: currentVisual,
        format_type: formatSelect.value,
        unit: unitInput.value.trim() || null,
      };

      try {
        const preview = await ApiClient.previewCustomKpi(this.currentDatasetId, spec);
        if (timingBadge) timingBadge.innerText = `${preview.execution_time_ms} ms DuckDB`;
        if (autoReasonPill) autoReasonPill.innerText = `✦ Visual: ${preview.suggested_visual_reason}`;

        renderPreviewData(preview, spec);
      } catch (err) {
        if (errorBox) {
          errorBox.style.display = 'block';
          errorBox.innerText = err.message || 'Failed to calculate metric preview.';
        }
      }
    };

    const renderPreviewData = (preview, spec) => {
      const cardContainer = document.getElementById('preview-mode-card');
      const chartContainer = document.getElementById('preview-mode-chart');
      const tableContainer = document.getElementById('preview-mode-table');

      const resolvedType = preview.resolved_widget_type;

      if (resolvedType === 'kpi_card') {
        if (chartContainer) chartContainer.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'none';
        if (cardContainer) cardContainer.style.display = 'block';

        document.getElementById('preview-card-title').innerText = spec.label;
        document.getElementById('preview-card-value').innerText = preview.formatted_value || String(preview.scalar_value ?? '--');
        document.getElementById('preview-card-subtitle').innerText = 'Calculated deterministically via DuckDB';
      } else if (resolvedType === 'table') {
        if (cardContainer) cardContainer.style.display = 'none';
        if (chartContainer) chartContainer.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'block';

        const rows = preview.rows || [];
        const thDim = document.getElementById('preview-table-th-dim');
        const thVal = document.getElementById('preview-table-th-val');
        if (thDim) thDim.innerText = preview.dimension || 'Segment';
        if (thVal) thVal.innerText = spec.label;

        const tbody = document.getElementById('preview-table-tbody');
        if (tbody) {
          tbody.innerHTML = rows.map(r => `
            <tr>
              <td style="font-weight: 600;">${r.dimension_value}</td>
              <td style="color: var(--accent-cyan); font-weight: 500;">${r.formatted_value || r.metric_value}</td>
            </tr>
          `).join('') || '<tr><td colspan="2">No data rows</td></tr>';
        }
      } else {
        if (cardContainer) cardContainer.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'none';
        if (chartContainer) chartContainer.style.display = 'block';

        const rows = preview.rows || [];
        const dimName = preview.dimension || 'category';

        if (resolvedType === 'line_chart') {
          const points = rows.map(r => ({
            period_label: r.dimension_value,
            values: { [spec.label]: r.metric_value }
          }));
          ChartManager.renderLineChart('kpi-preview-canvas', points, [spec.label]);
        } else if (resolvedType === 'pie_chart') {
          const pieRows = rows.map(r => ({
            dimension_value: r.dimension_value,
            [spec.label]: r.metric_value
          }));
          ChartManager.renderDonutChart('kpi-preview-canvas', pieRows, dimName, spec.label);
        } else {
          const barRows = rows.map(r => ({
            dimension_value: r.dimension_value,
            [spec.label]: r.metric_value
          }));
          ChartManager.renderBarChart('kpi-preview-canvas', barRows, dimName, spec.label);
        }
      }
    };

    saveBtn?.addEventListener('click', async () => {
      if (!this.currentDatasetId) return;
      saveBtn.innerText = 'Saving...';
      saveBtn.disabled = true;

      let condVal = rateValInput?.value?.trim() ?? 'true';
      if (condVal.toLowerCase() === 'true') condVal = true;
      else if (condVal.toLowerCase() === 'false') condVal = false;
      else if (!isNaN(Number(condVal)) && condVal !== '') condVal = Number(condVal);

      const spec = {
        label: titleInput.value.trim() || 'Custom Metric',
        column: colSelect.value,
        aggregation: currentAgg,
        condition: currentAgg === 'rate' ? { operator: '==', value: condVal } : null,
        dimension: dimSelect.value || null,
        output_type: currentVisual,
        format_type: formatSelect.value,
        unit: unitInput.value.trim() || null,
      };

      try {
        const dashboardId = DashboardRenderer.currentSpec?.id;
        if (!dashboardId) throw new Error('No active dashboard loaded');

        const updated = await ApiClient.addCustomWidget(dashboardId, spec);
        closeModal();
        DashboardRenderer.render(updated, this.currentDatasetId);
      } catch (err) {
        if (errorBox) {
          errorBox.style.display = 'block';
          errorBox.innerText = err.message || 'Failed to save widget to dashboard.';
        }
      } finally {
        saveBtn.innerText = '✦ Save to Dashboard';
        saveBtn.disabled = false;
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const app = new MetricMindApp();
  app.init();
});
