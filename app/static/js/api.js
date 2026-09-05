/**
 * MetricMind API Client - Communicates with FastAPI backend
 */
export const ApiClient = {
  baseUrl: '/api/v1',

  async getDatasets() {
    const res = await fetch(`${this.baseUrl}/datasets`);
    if (!res.ok) throw new Error('Failed to fetch datasets');
    return res.json();
  },

  async uploadDataset(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${this.baseUrl}/datasets/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async deleteDataset(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete dataset' }));
      throw new Error(err.detail || 'Failed to delete dataset');
    }
    return res.json();
  },

  async clearPastDatasets(keepDatasetId) {
    const url = keepDatasetId
      ? `${this.baseUrl}/datasets/clear-past?keep_dataset_id=${encodeURIComponent(keepDatasetId)}`
      : `${this.baseUrl}/datasets/clear-past`;
    const res = await fetch(url, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to clear past datasets' }));
      throw new Error(err.detail || 'Failed to clear past datasets');
    }
    return res.json();
  },


  async getDefaultDashboard(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/dashboards/default`);
    if (!res.ok) throw new Error('Failed to load dashboard');
    return res.json();
  },

  async getDashboard(dashboardId) {
    const res = await fetch(`${this.baseUrl}/dashboards/${dashboardId}`);
    if (!res.ok) throw new Error('Failed to load dashboard');
    return res.json();
  },

  async getQualityReport(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/quality-report`);
    if (!res.ok) throw new Error('Failed to load quality report');
    return res.json();
  },

  async getDatasetProfile(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/profile`);
    if (!res.ok) throw new Error('Failed to load dataset profile');
    return res.json();
  },

  async getAIUnderstanding(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/ai-understanding`);
    if (!res.ok) return null;
    return res.json();
  },

  async getInsights(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/insights`);
    if (!res.ok) return { insights: [] };
    return res.json();
  },

  async getAnomalies(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/anomalies`);
    if (!res.ok) return { anomalies: [] };
    return res.json();
  },

  async getKpiBreakdown(datasetId, metricId = 'total_revenue') {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/analytics/kpi-breakdown?metric=${metricId}`);
    if (!res.ok) return { breakdowns: {} };
    return res.json();
  },

  async computeBreakdown(datasetId, payload) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/analytics/breakdown`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to compute breakdown');
    return res.json();
  },

  async computeTimeSeries(datasetId, payload) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/analytics/timeseries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to compute time-series');
    return res.json();
  },

  async getForecast(datasetId, metric = 'total_revenue', periods = 3) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/forecast`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ metric, periods_ahead: periods }),
    });
    if (!res.ok) throw new Error('Failed to generate forecast');
    return res.json();
  },

  async simulateScenario(datasetId, payload) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to simulate scenario');
    return res.json();
  },

  async getExecutiveReport(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/report`);
    if (!res.ok) throw new Error('Failed to generate executive report');
    return res.json();
  },

  async askChat(datasetId, query, history = []) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, conversation_history: history }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Analysis failed' }));
      throw new Error(err.detail || 'Analysis failed');
    }
    return res.json();
  },

  async getSuggestedQuestions(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/chat/suggested-questions`);
    if (!res.ok) return { questions: [] };
    return res.json();
  },

  async getChatSessions(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/chat/sessions`);
    if (!res.ok) return [];
    return res.json();
  },

  async getChatMessages(datasetId, sessionId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/chat/sessions/${sessionId}/messages`);
    if (!res.ok) return [];
    return res.json();
  },

  async getGeoBreakdown(datasetId, metricId = 'total_revenue', filters = []) {
    if (filters && filters.length > 0) {
      const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/analytics/geo-breakdown?metric=${metricId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filters),
      });
      if (!res.ok) return { features: [], has_geographic_data: false };
      return res.json();
    }
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/analytics/geo-breakdown?metric=${metricId}`);
    if (!res.ok) return { features: [], has_geographic_data: false };
    return res.json();
  },


  async registerCustomMetric(datasetId, payload) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/metrics/custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create metric' }));
      throw new Error(err.detail || 'Failed to create metric');
    }
    return res.json();
  },

  async getCustomMetrics(datasetId) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/metrics/custom`);
    if (!res.ok) return [];
    return res.json();
  },

  async getDimensionValues(datasetId, dimension) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/analytics/dimensions/${encodeURIComponent(dimension)}/values`);
    if (!res.ok) return [];
    return res.json();
  },

  async getFilteredMetricsSummary(datasetId, filters = []) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/metrics/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    });
    if (!res.ok) return null;
    return res.json();
  },

  async previewCustomKpi(datasetId, spec) {
    const res = await fetch(`${this.baseUrl}/datasets/${datasetId}/dashboards/kpis/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to preview KPI' }));
      throw new Error(err.detail || 'Failed to preview KPI');
    }
    return res.json();
  },

  async addCustomWidget(dashboardId, spec) {
    const res = await fetch(`${this.baseUrl}/dashboards/${dashboardId}/widgets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to add custom widget' }));
      throw new Error(err.detail || 'Failed to add custom widget');
    }
    return res.json();
  },

  async deleteWidget(dashboardId, widgetId) {
    const res = await fetch(`${this.baseUrl}/dashboards/${dashboardId}/widgets/${encodeURIComponent(widgetId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete widget' }));
      throw new Error(err.detail || 'Failed to delete widget');
    }
    return res.json();
  }
};



