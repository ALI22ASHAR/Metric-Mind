import { ChartManager } from './charts.js';
import { ApiClient } from './api.js';

export const DashboardRenderer = {
  currentSpec: null,
  currentData: null,
  currentDatasetId: null,
  cachedInsights: [],
  cachedAnomalies: [],
  activeFilters: [], // [{ column, operator: 'eq', value }]
  filterHistory: [], // [[{column, operator, value}], ...]

  async render(dashboardResponse, datasetId) {
    this.currentSpec = dashboardResponse.spec;
    this.currentData = dashboardResponse.data;
    this.currentDatasetId = datasetId;
    this.activeFilters = [];
    this.filterHistory = [];

    // 1. Render Header Title & Subtitle
    document.getElementById('dash-title').innerText = this.currentSpec.title || 'Executive Dashboard';
    document.getElementById('dash-subtitle').innerText = this.currentSpec.subtitle || 'Real-time performance analytics';

    // 2. Render Global Filters & Breadcrumbs
    this.renderFilterBreadcrumbs();

    // 3. Render Dynamic 12-Column Grid
    this.renderGridWidgets();

    // 4. Render Geographic Regional Distribution Map if available
    this.renderGeoMapWidget(datasetId);
  },

  renderGridWidgets() {
    const gridEl = document.getElementById('dashboard-grid');
    gridEl.innerHTML = '';

    const widgets = this.currentSpec.widgets || [];

    // Top Row: KPI Cards
    const kpiWidgets = widgets.filter(w => w.type === 'kpi_card');
    const otherWidgets = widgets.filter(w => w.type !== 'kpi_card');

    for (const widget of kpiWidgets) {
      const colSpan = `col-span-${widget.position?.w || 3}`;
      const widgetData = this.currentData[widget.id] || {};
      const cardEl = this.createKpiCard(widget, widgetData, colSpan);
      
      const targetMetric = widget.metrics?.[0] || 'total_revenue';
      cardEl.onclick = () => this.openKpiBreakdownModal(targetMetric, widget.title);
      
      gridEl.appendChild(cardEl);
    }

    // Insert Sleek Summary Strip on top of charts
    const summaryStripContainer = document.createElement('div');
    summaryStripContainer.id = 'insights-feed-container';
    summaryStripContainer.className = 'col-span-12';
    gridEl.appendChild(summaryStripContainer);
    this.loadInsightsAndAnomalies(this.currentDatasetId, summaryStripContainer);

    // Render remaining charts and tables
    for (const widget of otherWidgets) {
      const colSpan = `col-span-${widget.position?.w || 6}`;
      const widgetData = this.currentData[widget.id] || {};

      if (widget.type === 'line_chart' || widget.type === 'area_chart') {
        gridEl.appendChild(this.createChartCard(widget, colSpan));
        setTimeout(() => {
          ChartManager.renderLineChart(`canvas_${widget.id}`, widgetData.points || [], widget.metrics || []);
        }, 50);
      } else if (widget.type === 'bar_chart') {
        gridEl.appendChild(this.createChartCard(widget, colSpan));
        setTimeout(() => {
          const metric = widget.metrics?.[0] || 'total_revenue';
          ChartManager.renderBarChart(
            `canvas_${widget.id}`,
            widgetData.rows || [],
            widget.dimension,
            metric,
            (dimValue) => window.onSegmentClick(widget.dimension, dimValue)
          );
        }, 50);
      } else if (widget.type === 'pie_chart') {
        gridEl.appendChild(this.createChartCard(widget, colSpan));
        setTimeout(() => {
          const metric = widget.metrics?.[0] || 'total_revenue';
          ChartManager.renderDonutChart(
            `canvas_${widget.id}`,
            widgetData.rows || [],
            widget.dimension,
            metric,
            (dimValue) => window.onSegmentClick(widget.dimension, dimValue)
          );
        }, 50);
      } else if (widget.type === 'table') {
        gridEl.appendChild(this.createTableCard(widget, widgetData, colSpan));
      }
    }
  },

  async renderGeoMapWidget(datasetId, apiFilters = []) {
    try {
      document.getElementById('geographic-map-card')?.remove();
      const primaryMetric = (this.currentSpec?.widgets || [])
        .find(widget => widget.type === 'kpi_card' && widget.metric_id)?.metric_id || 'total_records';
      const geoData = await ApiClient.getGeoBreakdown(datasetId, primaryMetric, apiFilters);
      if (!geoData.has_geographic_data || !geoData.features || geoData.features.length === 0) return;

      const gridEl = document.getElementById('dashboard-grid');
      const mapCard = document.createElement('div');
      mapCard.id = 'geographic-map-card';
      mapCard.className = 'glass-panel col-span-12 animate-fade-in';
      mapCard.innerHTML = `
        <div class="chart-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h3 class="chart-title">${geoData.geo_column || 'Geographic'} Performance Map</h3>
            <p class="chart-subtitle">${geoData.metric_id.replaceAll('_', ' ')} by market (Click a marker to cross-filter)</p>
          </div>
          <span class="badge badge-indigo">${geoData.features.length} Markets</span>
        </div>
        <div id="geo-map-container" style="margin-top: 0.75rem;"></div>
      `;
      gridEl.appendChild(mapCard);

      setTimeout(() => {
        ChartManager.renderGeoMap('geo-map-container', geoData.features, (reg) => window.onSegmentClick(geoData.geo_column, reg));
      }, 50);
    } catch (e) {
      console.warn('Geographic distribution unavailable:', e);
    }
  },

  renderFilterBreadcrumbs() {
    let breadcrumbEl = document.getElementById('filter-breadcrumbs');
    if (!breadcrumbEl) {
      const parent = document.querySelector('.dashboard-header');
      if (parent) {
        breadcrumbEl = document.createElement('div');
        breadcrumbEl.id = 'filter-breadcrumbs';
        breadcrumbEl.className = 'filter-breadcrumbs-bar';
        parent.appendChild(breadcrumbEl);
      }
    }

    if (!breadcrumbEl) return;

    const hasFilters = this.activeFilters.length > 0;
    const hasHistory = this.filterHistory.length > 0;

    if (!hasFilters && !hasHistory) {
      breadcrumbEl.innerHTML = '';
      breadcrumbEl.style.display = 'none';
      return;
    }

    breadcrumbEl.style.display = 'flex';
    breadcrumbEl.innerHTML = `
      ${hasHistory ? `
        <button class="btn btn-secondary btn-sm btn-back-filter" onclick="window.goBackFilter()" title="Step back to previous filter state">
          ◀ Back
        </button>
      ` : ''}
      <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; align-self: center;">Active Slicers:</span>
      ${this.activeFilters.map((f, idx) => `
        <div class="filter-chip animate-fade-in">
          <span>${f.column}: <strong>${f.value}</strong></span>
          <button class="filter-chip-remove" onclick="window.removeFilter(${idx})">&times;</button>
        </div>
      `).join('')}
      ${hasFilters ? `<button class="btn btn-secondary btn-sm" style="padding: 0.15rem 0.5rem; font-size: 0.75rem;" onclick="window.clearAllFilters()">Clear All</button>` : ''}
    `;
  },

  async toggleCrossFilter(column, value) {
    // Save previous state to history stack for Back feature
    this.filterHistory.push(JSON.parse(JSON.stringify(this.activeFilters)));

    const existingIdx = this.activeFilters.findIndex(f => f.column.toLowerCase() === column.toLowerCase() && f.value === value);
    if (existingIdx >= 0) {
      this.activeFilters.splice(existingIdx, 1);
    } else {
      // Replace existing filter for same column or append
      const sameColIdx = this.activeFilters.findIndex(f => f.column.toLowerCase() === column.toLowerCase());
      if (sameColIdx >= 0) {
        this.activeFilters[sameColIdx].value = value;
      } else {
        this.activeFilters.push({ column, operator: 'eq', value });
      }
    }

    this.renderFilterBreadcrumbs();
    await this.refreshFilteredDashboard();
  },

  async goBackFilter() {
    if (this.filterHistory.length > 0) {
      this.activeFilters = this.filterHistory.pop();
      this.renderFilterBreadcrumbs();
      await this.refreshFilteredDashboard();
    }
  },

  async refreshFilteredDashboard() {
    if (!this.currentDatasetId || !this.currentSpec) return;

    try {
      const widgets = this.currentSpec.widgets || [];
      const updatedData = { ...this.currentData };

      // Convert activeFilters to API format
      const apiFilters = this.activeFilters.map(f => ({
        column: f.column,
        operator: 'eq',
        value: f.value,
      }));

      // Pre-fetch filtered KPI summary so top KPI cards recalculate with selected category / country / active filters!
      try {
        const filteredSummary = await ApiClient.getFilteredMetricsSummary(this.currentDatasetId, apiFilters);
        if (filteredSummary && filteredSummary.metrics) {
          widgets.filter(w => w.type === 'kpi_card').forEach(w => {
            const mId = w.metric_id || w.metrics?.[0] || 'total_revenue';
            const metricRes = filteredSummary.metrics[mId];
            if (metricRes) {
              updatedData[w.id] = {
                metric_id: mId,
                value: metricRes.value,
                formatted_value: metricRes.formatted_value,
              };
            }
          });
        }
      } catch (err) {
        console.warn('Failed to calculate filtered KPI summary:', err);
      }

      // Recompute each non-KPI widget with active filters
      const updatePromises = widgets.map(async (w) => {
        if (w.type === 'bar_chart' || w.type === 'pie_chart' || w.type === 'table') {
          try {
            const res = await ApiClient.computeBreakdown(this.currentDatasetId, {
              dimension: w.dimension,
              metrics: w.metrics || ['total_revenue'],
              filters: apiFilters,
              limit: 10,
            });
            updatedData[w.id] = { rows: res.rows, dimension: w.dimension };
          } catch (e) {
            console.warn(`Failed to filter widget ${w.id}:`, e);
          }
        } else if (w.type === 'line_chart' || w.type === 'area_chart') {
          try {
            const gran = document.getElementById(`ts-granularity-${w.id}`)?.value || 'month';
            const localFilters = [...apiFilters];
            this._timeFilterDefinitions(w).forEach(filter => {
              const value = document.getElementById(this._timeFilterId(w, filter.column))?.value || '';
              if (value) localFilters.push({ column: filter.column, operator: 'eq', value });
            });

            const res = await ApiClient.computeTimeSeries(this.currentDatasetId, {
              metrics: w.metrics || ['total_revenue'],
              granularity: gran,
              filters: localFilters,
            });
            updatedData[w.id] = { points: res.points };
          } catch (e) {
            console.warn(`Failed to filter time-series ${w.id}:`, e);
          }
        }
      });

      await Promise.all(updatePromises);
      this.currentData = updatedData;
      this.renderGridWidgets();
      this.renderGeoMapWidget(this.currentDatasetId, apiFilters);
    } catch (e) {
      console.error('Failed to apply cross-filters:', e);
    }
  },

  async openKpiBreakdownModal(metricId, metricTitle, initialDim = null) {
    const modal = document.getElementById('kpi-modal');
    if (!modal) return;

    modal.classList.add('active');
    document.getElementById('kpi-modal-title').innerText = `${metricTitle} Breakdown`;
    document.getElementById('kpi-modal-badge').innerText = metricId.replace(/_/g, ' ').toUpperCase();

    const tabsContainer = document.getElementById('kpi-dimension-tabs');
    const tbody = document.getElementById('kpi-tbody');
    tabsContainer.innerHTML = '<span>Loading dimensional breakdowns...</span>';
    tbody.innerHTML = '<tr><td colspan="4">Querying columnar database...</td></tr>';

    try {
      const data = await ApiClient.getKpiBreakdown(this.currentDatasetId, metricId);
      const breakdowns = data.breakdowns || {};
      const dimensions = Object.keys(breakdowns);

      if (dimensions.length === 0) {
        tabsContainer.innerHTML = '<span style="color: var(--text-muted);">No categorical dimensions discovered for breakdown.</span>';
        tbody.innerHTML = '<tr><td colspan="4">No categorical segments available in dataset.</td></tr>';
        return;
      }

      tabsContainer.innerHTML = '';
      const selectedDim = initialDim && breakdowns[initialDim] ? initialDim : dimensions[0];

      dimensions.forEach((dim) => {
        const btn = document.createElement('button');
        btn.className = `tab-btn ${dim === selectedDim ? 'active' : ''}`;
        btn.innerText = dim.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
        btn.onclick = () => {
          document.querySelectorAll('#kpi-dimension-tabs .tab-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this.renderKpiDimensionData(dim, breakdowns[dim], metricId);
        };
        tabsContainer.appendChild(btn);
      });

      this.renderKpiDimensionData(selectedDim, breakdowns[selectedDim], metricId);
    } catch (e) {
      console.error('Failed to load KPI breakdown:', e);
      tbody.innerHTML = '<tr><td colspan="4" style="color: #f43f5e;">Failed to load breakdown.</td></tr>';
    }
  },

  renderKpiDimensionData(dimensionName, rows, metricId) {
    const displayDimension = dimensionName.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
    document.getElementById('kpi-th-dimension').innerText = `${displayDimension} Segment`;
    document.getElementById('kpi-th-metric').innerText = metricId.replace(/_/g, ' ').toUpperCase();

    const tbody = document.getElementById('kpi-tbody');
    tbody.innerHTML = '';

    rows.forEach(r => {
      const tr = document.createElement('tr');
      const valStr = r.formatted_value || (typeof r.value === 'number' ? r.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : r.value);
      tr.innerHTML = `
        <td class="clickable-category-cell">
          <div class="category-pill-link">
            <span></span>
            <span class="pill-badge-action">&rarr;</span>
          </div>
        </td>
        <td>${valStr}</td>
        <td><span class="badge badge-indigo" style="font-size: 0.75rem;">${r.share_percentage}%</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">Filter</button>
        </td>
      `;
      const dimensionValue = String(r.dimension_value ?? 'Unknown');
      tr.querySelector('.category-pill-link span').textContent = dimensionValue;
      const applyFilter = () => window.onSegmentClick(dimensionName, dimensionValue);
      tr.querySelector('.clickable-category-cell').addEventListener('click', applyFilter);
      tr.querySelector('button').addEventListener('click', applyFilter);
      tbody.appendChild(tr);
    });

    setTimeout(() => {
      const chartRows = rows.map(r => ({ dimension_value: r.dimension_value, [metricId]: r.value }));
      ChartManager.renderBarChart('kpi-breakdown-canvas', chartRows, dimensionName, metricId);
    }, 50);
  },

  async loadInsightsAndAnomalies(datasetId, container) {
    try {
      const [insightsData, anomalyData] = await Promise.all([
        ApiClient.getInsights(datasetId),
        ApiClient.getAnomalies(datasetId),
      ]);

      const insights = insightsData.insights || [];
      const anomalies = anomalyData.anomalies || [];
      this.cachedInsights = insights;
      this.cachedAnomalies = anomalies;

      const totalCount = insights.length + anomalies.length;

      const notifBadge = document.getElementById('nav-insights-count');
      if (notifBadge) {
        if (totalCount > 0) {
          notifBadge.innerText = totalCount;
          notifBadge.style.display = 'inline-block';
        } else {
          notifBadge.style.display = 'none';
        }
      }

      this.setupNotificationDrawer();

      if (totalCount === 0) {
        container.style.display = 'none';
        return;
      }

      const criticalCount = anomalies.filter(a => a.severity === 'critical').length;
      container.innerHTML = `
        <div class="intelligence-summary-strip animate-fade-in" onclick="document.getElementById('notifications-drawer').classList.add('active')" title="Click to open full executive feed">
          <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
            <span class="badge ${criticalCount > 0 ? 'badge-rose' : 'badge-emerald'}">⚡ Live Intelligence Feed</span>
            <span style="font-size: 0.875rem; font-weight: 600; color: var(--text-main);">
              ${insights.length} Strategic Drivers &middot; ${anomalies.length} Statistical Anomalies ${criticalCount > 0 ? `(${criticalCount} Critical Risks)` : ''}
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.8125rem; color: var(--accent-primary); font-weight: 600;">
            <span>View Feed</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>
        </div>
      `;

      this.renderNotificationFeed('all');
    } catch (e) {
      console.warn('Failed to load insights feed:', e);
    }
  },

  setupNotificationDrawer() {
    const drawer = document.getElementById('notifications-drawer');
    const openBtn = document.getElementById('btn-open-notifications');
    const closeBtn = document.getElementById('btn-close-notifications');

    if (openBtn && !openBtn.dataset.wired) {
      openBtn.dataset.wired = 'true';
      openBtn.addEventListener('click', () => drawer.classList.add('active'));
    }
    if (closeBtn && !closeBtn.dataset.wired) {
      closeBtn.dataset.wired = 'true';
      closeBtn.addEventListener('click', () => drawer.classList.remove('active'));
    }

    document.querySelectorAll('.notif-filter-tabs .tab-btn').forEach(btn => {
      if (!btn.dataset.wired) {
        btn.dataset.wired = 'true';
        btn.addEventListener('click', () => {
          document.querySelectorAll('.notif-filter-tabs .tab-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this.renderNotificationFeed(btn.dataset.filter);
        });
      }
    });
  },

  renderNotificationFeed(filter = 'all') {
    const feedContainer = document.getElementById('notif-feed-list');
    if (!feedContainer) return;

    let items = [];

    if (filter === 'all' || filter === 'insights') {
      this.cachedInsights.forEach(i => {
        items.push({
          type: 'insight',
          category: i.type,
          title: i.title,
          description: i.description,
          action: i.recommendation,
          badgeText: `${i.type.toUpperCase()} · ${i.impact_score}% IMPACT`,
          badgeClass: i.type === 'growth_driver' ? 'badge-emerald' : i.type === 'risk' ? 'badge-rose' : 'badge-indigo',
          cardClass: i.type === 'growth_driver' ? 'notif-card-growth' : i.type === 'risk' ? 'notif-card-critical' : 'notif-card-insight',
        });
      });
    }

    if (filter === 'all' || filter === 'anomalies' || filter === 'critical') {
      this.cachedAnomalies.forEach(a => {
        if (filter === 'critical' && a.severity !== 'critical') return;
        items.push({
          type: 'anomaly',
          category: a.severity,
          title: `${a.metric.replace(/_/g, ' ').toUpperCase()} ${a.anomaly_type.toUpperCase()} (${a.period})`,
          description: a.explanation,
          badgeText: `${a.severity.toUpperCase()} ANOMALY · ${a.deviation_percentage > 0 ? '+' : ''}${a.deviation_percentage}%`,
          badgeClass: a.severity === 'critical' ? 'badge-rose' : 'badge-amber',
          cardClass: a.severity === 'critical' ? 'notif-card-critical' : 'notif-card-warning',
          queryPrompt: `Why did ${a.metric.replace(/_/g, ' ')} ${a.anomaly_type} in ${a.period}?`,
        });
      });
    }

    if (items.length === 0) {
      feedContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 0.8125rem; text-align: center; padding-top: 2rem;">No alerts matching this filter.</p>';
      return;
    }

    feedContainer.innerHTML = items.map(item => `
      <div class="notif-card ${item.cardClass} animate-fade-in">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
          <span class="badge ${item.badgeClass}" style="font-size: 0.6875rem;">${item.badgeText}</span>
        </div>
        <h4 style="font-size: 0.875rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.35rem; line-height: 1.35;">${item.title}</h4>
        <p style="font-size: 0.8125rem; color: var(--text-muted); line-height: 1.45;">${item.description}</p>
        ${item.action ? `<div class="notif-action-chip"><strong>Recommended Action:</strong> ${item.action}</div>` : ''}
        ${item.queryPrompt ? `
          <button class="btn btn-secondary btn-sm" style="margin-top: 0.6rem; padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="window.askAIAnalyst('${item.queryPrompt.replace(/'/g, "\\'")}')">
            💬 Investigate with AI
          </button>
        ` : ''}
      </div>
    `).join('');
  },

  createKpiCard(widget, data, colSpan) {
    const card = document.createElement('div');
    card.className = `glass-panel kpi-card ${colSpan} animate-fade-in`;
    card.style.cursor = 'pointer';
    card.title = 'Click to view dimensional breakdown matrix';
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');

    const formattedVal = data.formatted_value || (data.value !== undefined ? String(data.value) : '--');
    const hasGrowth = typeof data.growth_percentage === 'number';
    const growth = hasGrowth ? `${data.growth_percentage >= 0 ? '+' : ''}${data.growth_percentage.toFixed(1)}%` : null;
    const growthColor = data.trend === 'down' ? 'var(--accent-rose)' : data.trend === 'up' ? 'var(--accent-emerald)' : 'var(--text-muted)';
    const growthBg   = data.trend === 'down' ? 'rgba(251,113,133,0.12)' : data.trend === 'up' ? 'rgba(52,211,153,0.12)' : 'rgba(148,163,184,0.10)';
    const growthIcon = data.trend === 'down' ? '▼' : data.trend === 'up' ? '▲' : '–';

    // Period labels: backend sends PeriodOverPeriodGrowth with current/prior dates.
    const currentPeriod = data.current_period ? this._formatPeriod(data.current_period) : null;
    const priorPeriod   = data.prior_period   ? this._formatPeriod(data.prior_period)   : null;
    const priorValue    = (typeof data.prior_value === 'number') ? data.prior_value : null;
    const priorFormatted = (typeof data.prior_formatted_value === 'string')
      ? data.prior_formatted_value
      : (priorValue !== null ? this._formatKpiNumber(priorValue) : null);
    const absChange = typeof data.absolute_change === 'number' ? data.absolute_change : null;
    const absChangeFormatted = absChange !== null
      ? `${absChange >= 0 ? '+' : ''}${this._formatKpiNumber(absChange)}`
      : null;

    // Build a real sparkline (inline SVG path) instead of a string of numbers.
    const sparkline = this._renderSparkline(data.sparkline || [], data.trend);

    // Real confidence score from backend (falls back to heuristic if absent).
    const confidencePct = typeof data.data_quality_score === 'number'
      ? Math.round(data.data_quality_score)
      : (hasGrowth ? 85 : 55);
    const confidenceLabel = data.confidence_label
      || (hasGrowth ? 'High confidence' : 'Limited history');
    // Headline insight: "Driven by a +14% lift in Engineering; Sales flat."
    const headline = data.headline_insight || widget.description || 'Calculated deterministically';

    // Build a tooltip explaining the factors when the user hovers the bar.
    const factors = Array.isArray(data.confidence_factors) ? data.confidence_factors : [];
    const factorsTooltip = factors.length
      ? factors.map(f => `${f.label}: ${f.score.toFixed(0)} (${f.detail || '—'})`).join('  •  ')
      : 'Confidence derived from row count, nulls, and data quality warnings.';

    card.innerHTML = `
      <div class="kpi-header">
        <div class="kpi-header-text">
          <span class="kpi-title">${widget.title}</span>
          <span class="kpi-subtitle">${currentPeriod ? `As of ${currentPeriod}` : 'Real-time aggregate'}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.35rem;">
          ${widget.options?.custom_kpi ? `
            <button class="btn btn-secondary btn-sm" style="padding: 0.15rem 0.4rem; font-size: 0.75rem; color: var(--accent-rose); border-color: rgba(251,113,133,0.3); border-radius: 4px;" title="Remove custom KPI widget" onclick="event.stopPropagation(); window.onRemoveWidgetClick('${widget.id}')">&times;</button>
          ` : ''}
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
              <polyline points="17 6 23 6 23 12"></polyline>
            </svg>
          </div>
        </div>
      </div>

      <div class="kpi-value-row">
        <div class="kpi-value">${formattedVal}</div>
        ${growth !== null ? `
          <div class="kpi-growth-pill" style="color: ${growthColor}; background: ${growthBg};">
            <span class="kpi-growth-icon">${growthIcon}</span>
            <span>${growth}</span>
          </div>
        ` : ''}
      </div>

      <div class="kpi-sparkline-row">
        ${sparkline}
        <div class="kpi-sparkline-axis">
          ${priorPeriod ? `Prior: ${priorPeriod}` : ''}
        </div>
      </div>

      <div class="kpi-comparison">
        <div class="kpi-comparison-item">
          <span class="kpi-comparison-label">Current</span>
          <span class="kpi-comparison-value">${formattedVal}</span>
        </div>
        <div class="kpi-comparison-divider"></div>
        <div class="kpi-comparison-item">
          <span class="kpi-comparison-label">Previous</span>
          <span class="kpi-comparison-value">${priorFormatted || '—'}</span>
        </div>
        <div class="kpi-comparison-divider"></div>
        <div class="kpi-comparison-item">
          <span class="kpi-comparison-label">Change</span>
          <span class="kpi-comparison-value" style="color: ${growthColor};">${absChangeFormatted || '—'}</span>
        </div>
      </div>

      <div class="kpi-footer">
        <div class="kpi-footer-meta">
          <div class="kpi-confidence" title="${factorsTooltip}" style="cursor: help;">
            <div class="kpi-confidence-bar">
              <div class="kpi-confidence-fill"
                style="width: ${confidencePct}%;
                       background: ${confidencePct >= 80 ? 'linear-gradient(90deg, var(--accent-emerald), #6ee7b7)' : confidencePct >= 60 ? 'linear-gradient(90deg, var(--accent-amber), #fcd34d)' : 'linear-gradient(90deg, #f87171, #fca5a5)'};"
              ></div>
            </div>
            <span class="kpi-confidence-label">${confidenceLabel}</span>
          </div>
          <p class="kpi-description">${headline}</p>
        </div>
        <button class="kpi-breakdown-btn" type="button" aria-label="View breakdown">
          <span>Breakdown</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>
          </svg>
        </button>
      </div>
    `;
    return card;
  },

  /** Build a real mini sparkline as inline SVG with a soft area fill. */
  _renderSparkline(values, trend) {
    const valid = (values || []).filter(v => typeof v === 'number' && !isNaN(v));
    if (valid.length < 2) {
      return '<div class="kpi-sparkline kpi-sparkline-empty">No trend data yet</div>';
    }
    const W = 220, H = 44, PAD = 2;
    const min = Math.min(...valid);
    const max = Math.max(...valid);
    const range = max - min || 1;
    const stepX = (W - PAD * 2) / (valid.length - 1);
    const points = valid.map((v, i) => {
      const x = PAD + i * stepX;
      const y = H - PAD - ((v - min) / range) * (H - PAD * 2);
      return [x, y];
    });
    const pathD = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
    const areaD = pathD + ` L${points[points.length - 1][0].toFixed(1)} ${H} L${points[0][0].toFixed(1)} ${H} Z`;
    const stroke = trend === 'down' ? 'var(--accent-rose)' : trend === 'up' ? 'var(--accent-emerald)' : 'var(--accent-primary)';
    const gradId = `kpi-spark-${Math.random().toString(36).slice(2, 8)}`;
    return `
      <svg class="kpi-sparkline" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${stroke}" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="${stroke}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${areaD}" fill="url(#${gradId})" />
        <path d="${pathD}" fill="none" stroke="${stroke}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${points[points.length - 1][0].toFixed(1)}" cy="${points[points.length - 1][1].toFixed(1)}" r="2.5" fill="${stroke}"/>
      </svg>
    `;
  },

  /** Format a YYYY-MM-DD or ISO period string into a human label. */
  _formatPeriod(p) {
    if (!p) return null;
    try {
      const d = new Date(p);
      if (!isNaN(d.getTime())) {
        return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
      }
    } catch (e) { /* fall through */ }
    return String(p);
  },

  /** Compact formatter for KPI numbers (no currency/%-detection — uses the raw magnitude). */
  _formatKpiNumber(n) {
    const abs = Math.abs(n);
    if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (abs >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
    return Number(n.toFixed(2)).toString();
  },

  _timeFilterDefinitions(widget) {
    return widget.options?.filter_dimensions || [
      { column: 'Category', label: 'Category' },
      { column: 'Product', label: 'Product' },
      { column: 'Country', label: 'Country / Region' },
    ];
  },

  _timeFilterId(widget, column) {
    return `ts-filter-${widget.id}-${column.replace(/[^a-zA-Z0-9_-]/g, '_')}`;
  },

  createChartCard(widget, colSpan) {
    const card = document.createElement('div');
    card.className = `glass-panel chart-card ${colSpan} animate-fade-in`;

    const isTimeSeries = widget.type === 'line_chart' || widget.type === 'area_chart';

    if (isTimeSeries) {
      const filterDefinitions = this._timeFilterDefinitions(widget);
      card.innerHTML = `
        <div class="chart-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
          <div>
            <h3 class="chart-title">${widget.title}</h3>
            <p class="chart-subtitle">${widget.description || 'Chronological performance over time'}</p>
          </div>
          <div class="chart-header-controls">
            <select id="ts-granularity-${widget.id}" class="chart-control-select" title="Select Time Granularity">
              <option value="month" selected>Month-wise</option>
              <option value="week">Week-wise</option>
              <option value="quarter">Quarter-wise</option>
              <option value="day">Day-wise</option>
              <option value="year">Year-wise</option>
            </select>
            ${filterDefinitions.map(filter => `
              <select id="${this._timeFilterId(widget, filter.column)}" class="chart-control-select" title="${filter.label} Filter">
                <option value="">All ${filter.label}</option>
              </select>
            `).join('')}
          </div>
        </div>
        <div class="chart-container">
          <canvas id="canvas_${widget.id}"></canvas>
        </div>
      `;

      // Populate only dimensions that belong to the active domain.
      setTimeout(async () => {
        if (!this.currentDatasetId) return;
        try {
          const values = await Promise.all(filterDefinitions.map(filter =>
            ApiClient.getDimensionValues(this.currentDatasetId, filter.column).catch(() => [])
          ));
          filterDefinitions.forEach((filter, index) => {
            const select = document.getElementById(this._timeFilterId(widget, filter.column));
            if (select && values[index].length > 0) {
              select.innerHTML = `<option value="">All ${filter.label}</option>` +
                values[index].map(v => `<option value="${v}">${v}</option>`).join('');
            }
          });

          const onTimeSeriesFilterChange = async () => {
            const gran = document.getElementById(`ts-granularity-${widget.id}`)?.value || 'month';
            const localFilters = [...this.activeFilters.map(f => ({ column: f.column, operator: 'eq', value: f.value }))];
            filterDefinitions.forEach(filter => {
              const value = document.getElementById(this._timeFilterId(widget, filter.column))?.value || '';
              if (value) localFilters.push({ column: filter.column, operator: 'eq', value });
            });

            try {
              const res = await ApiClient.computeTimeSeries(this.currentDatasetId, {
                metrics: widget.metrics || ['total_revenue'],
                granularity: gran,
                filters: localFilters,
              });
              ChartManager.renderLineChart(`canvas_${widget.id}`, res.points || [], widget.metrics || ['total_revenue']);
            } catch (err) {
              console.warn('Failed to update time series chart:', err);
            }
          };

          document.getElementById(`ts-granularity-${widget.id}`)?.addEventListener('change', onTimeSeriesFilterChange);
          filterDefinitions.forEach(filter => {
            document.getElementById(this._timeFilterId(widget, filter.column))?.addEventListener('change', onTimeSeriesFilterChange);
          });
        } catch (e) {
          console.warn('Error fetching dimension dropdown values:', e);
        }
      }, 100);

      return card;
    }

    // Standard bar/pie chart card
    card.innerHTML = `
      <div class="chart-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h3 class="chart-title">${widget.title}</h3>
          <p class="chart-subtitle">${widget.description || 'Click any segment to cross-filter'}</p>
        </div>
        ${widget.options?.custom_kpi ? `
          <button class="btn btn-secondary btn-sm" style="padding: 0.15rem 0.4rem; font-size: 0.75rem; color: var(--accent-rose); border-color: rgba(251,113,133,0.3); border-radius: 4px;" title="Remove custom widget" onclick="event.stopPropagation(); window.onRemoveWidgetClick('${widget.id}')">&times;</button>
        ` : ''}
      </div>
      <div class="chart-container">
        <canvas id="canvas_${widget.id}"></canvas>
      </div>
    `;
    return card;
  },

  createTableCard(widget, data, colSpan) {
    const card = document.createElement('div');
    card.className = `glass-panel table-card ${colSpan} animate-fade-in`;

    const rows = data.rows || [];
    const dimensionKey = data.dimension || widget.dimension || 'Category';
    const metrics = data.metrics || widget.metrics || [];

    let thHeaders = `<th>${dimensionKey}</th>`;
    metrics.forEach(m => {
      thHeaders += `<th>${m.replace(/_/g, ' ').toUpperCase()}</th>`;
    });

    let trRows = '';
    rows.slice(0, 10).forEach(r => {
      const dimVal = r.dimension_value || 'Unknown';
      const cleanVal = String(dimVal).replace(/'/g, "\\'");
      trRows += `<tr style="cursor: pointer;" title="Click ${dimensionKey} to filter and drill down">
        <td class="clickable-category-cell" onclick="window.onSegmentClick('${dimensionKey}', '${cleanVal}')">
          <div class="category-pill-link">
            <span>${dimVal}</span>
            <span class="pill-badge-action">&rarr;</span>
          </div>
        </td>`;
      metrics.forEach(m => {
        const v = r[m];
        const valStr = r.formatted_values?.[m]
          || (typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : (v || '--'));
        trRows += `<td onclick="window.onSegmentClick('${dimensionKey}', '${cleanVal}')">${valStr}</td>`;
      });
      trRows += '</tr>';
    });

    card.innerHTML = `
      <div class="chart-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h3 class="chart-title">${widget.title}</h3>
          <p class="chart-subtitle">${widget.description || `Interactive ${dimensionKey} detail (click a row to filter and drill down)`}</p>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          ${widget.options?.custom_kpi ? `
            <button class="btn btn-secondary btn-sm" style="padding: 0.15rem 0.4rem; font-size: 0.75rem; color: var(--accent-rose); border-color: rgba(251,113,133,0.3); border-radius: 4px;" title="Remove custom widget" onclick="event.stopPropagation(); window.onRemoveWidgetClick('${widget.id}')">&times;</button>
          ` : ''}
          <span class="badge badge-indigo" style="font-size: 0.75rem;">Click ${dimensionKey} to Filter</span>
        </div>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead><tr>${thHeaders}</tr></thead>
          <tbody>${trRows || '<tr><td colspan="4">No data rows</td></tr>'}</tbody>
        </table>
      </div>
    `;
    return card;
  }
};

// Global cross-filtering helpers
window.onSegmentClick = function(dimension, value) {
  DashboardRenderer.toggleCrossFilter(dimension, value);
};

window.goBackFilter = function() {
  DashboardRenderer.goBackFilter();
};

window.removeFilter = function(idx) {
  DashboardRenderer.activeFilters.splice(idx, 1);
  DashboardRenderer.renderFilterBreadcrumbs();
  DashboardRenderer.refreshFilteredDashboard();
};

window.clearAllFilters = function() {
  DashboardRenderer.activeFilters = [];
  DashboardRenderer.filterHistory = [];
  DashboardRenderer.renderFilterBreadcrumbs();
  DashboardRenderer.refreshFilteredDashboard();
};

window.askAIAnalyst = function(promptText) {
  document.getElementById('notifications-drawer')?.classList.remove('active');
  const chatDrawer = document.getElementById('chat-drawer');
  if (chatDrawer) {
    chatDrawer.classList.add('active');
    const input = document.getElementById('chat-input');
    if (input) {
      input.value = promptText;
      document.getElementById('btn-chat-send')?.click();
    }
  }
};

window.onRemoveWidgetClick = async function(widgetId) {
  if (!confirm('Remove this custom widget from your dashboard?')) return;
  if (!DashboardRenderer.currentSpec || !DashboardRenderer.currentSpec.id) return;
  try {
    const updated = await ApiClient.deleteWidget(DashboardRenderer.currentSpec.id, widgetId);
    DashboardRenderer.render(updated, DashboardRenderer.currentDatasetId);
  } catch (err) {
    alert('Failed to remove widget: ' + err.message);
  }
};

