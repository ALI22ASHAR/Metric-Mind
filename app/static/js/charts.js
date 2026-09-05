/**
 * Chart.js Visualizations with sleek dark glass aesthetics and interactive click handlers
 */
export const ChartManager = {
  activeCharts: {},

  destroyChart(canvasId) {
    if (this.activeCharts[canvasId]) {
      this.activeCharts[canvasId].destroy();
      delete this.activeCharts[canvasId];
    }
  },

  renderLineChart(canvasId, points, metrics) {
    this.destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas || !points || points.length === 0) return;

    const ctx = canvas.getContext('2d');
    const labels = points.map(p => p.period_label || p.period_start);

    const colors = [
      { border: '#6366f1', fillStart: 'rgba(99, 102, 241, 0.35)', fillEnd: 'rgba(99, 102, 241, 0.0)' },
      { border: '#10b981', fillStart: 'rgba(16, 185, 129, 0.35)', fillEnd: 'rgba(16, 185, 129, 0.0)' },
      { border: '#06b6d4', fillStart: 'rgba(6, 182, 212, 0.35)', fillEnd: 'rgba(6, 182, 212, 0.0)' }
    ];

    const datasets = metrics.map((metricId, idx) => {
      const color = colors[idx % colors.length];
      const gradient = ctx.createLinearGradient(0, 0, 0, 300);
      gradient.addColorStop(0, color.fillStart);
      gradient.addColorStop(1, color.fillEnd);

      return {
        label: metricId.replace(/_/g, ' ').toUpperCase(),
        data: points.map(p => p.values[metricId] || 0),
        borderColor: color.border,
        backgroundColor: gradient,
        borderWidth: 2.5,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: color.border,
        pointRadius: 4,
        pointHoverRadius: 6,
      };
    });

    this.activeCharts[canvasId] = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: datasets.length > 1,
            labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 12 } }
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleColor: '#f8fafc',
            bodyColor: '#cbd5e1',
            padding: 12,
            cornerRadius: 8,
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.04)' },
            ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11 } }
          }
        }
      }
    });
  },

  renderBarChart(canvasId, rows, dimension, metric, onElementClick) {
    this.destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas || !rows || rows.length === 0) return;

    const ctx = canvas.getContext('2d');
    const labels = rows.map(r => String(r.dimension_value || 'Unknown'));
    const data = rows.map(r => r[metric] || 0);

    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.85)');
    gradient.addColorStop(1, 'rgba(168, 85, 247, 0.4)');

    this.activeCharts[canvasId] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: metric.replace(/_/g, ' ').toUpperCase(),
          data,
          backgroundColor: gradient,
          borderRadius: 6,
          borderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        onClick: (evt, elements) => {
          if (elements.length > 0 && onElementClick) {
            const index = elements[0].index;
            onElementClick(labels[index], rows[index]);
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleColor: '#f8fafc',
            bodyColor: '#cbd5e1',
            padding: 12,
            cornerRadius: 8,
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.04)' },
            ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11 } }
          }
        }
      }
    });
  },

  renderDonutChart(canvasId, rows, dimension, metric, onElementClick) {
    this.destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas || !rows || rows.length === 0) return;

    const ctx = canvas.getContext('2d');
    const labels = rows.map(r => String(r.dimension_value || 'Unknown'));
    const data = rows.map(r => r[metric] || 0);

    const palette = [
      '#6366f1', '#10b981', '#06b6d4', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6', '#f43f5e'
    ];

    this.activeCharts[canvasId] = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: palette.slice(0, labels.length),
          borderWidth: 2,
          borderColor: '#0b0f19',
          hoverOffset: 8,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        onClick: (evt, elements) => {
          if (elements.length > 0 && onElementClick) {
            const index = elements[0].index;
            onElementClick(labels[index], rows[index]);
          }
        },
        plugins: {
          legend: {
            position: 'right',
            labels: {
              color: '#94a3b8',
              font: { family: 'Plus Jakarta Sans', size: 11 },
              boxWidth: 12,
              padding: 12
            }
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleColor: '#f8fafc',
            bodyColor: '#cbd5e1',
            padding: 12,
            cornerRadius: 8,
          }
        }
      }
    });
  },

  renderForecastChart(canvasId, forecastPoints, metric = 'Revenue') {
    this.destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas || !forecastPoints || forecastPoints.length === 0) return;

    const ctx = canvas.getContext('2d');
    const labels = forecastPoints.map(p => p.period);
    const predicted = forecastPoints.map(p => p.predicted_value);
    const upper95 = forecastPoints.map(p => p.upper_bound_95);
    const lower95 = forecastPoints.map(p => p.lower_bound_95);

    this.activeCharts[canvasId] = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Predicted Forecast',
            data: predicted,
            borderColor: '#6366f1',
            backgroundColor: 'rgba(99, 102, 241, 0.2)',
            borderWidth: 3,
            fill: false,
            tension: 0.3,
          },
          {
            label: '95% Upper Bound',
            data: upper95,
            borderColor: 'rgba(16, 185, 129, 0.5)',
            borderDash: [5, 5],
            fill: false,
            pointRadius: 0,
          },
          {
            label: '95% Lower Bound',
            data: lower95,
            borderColor: 'rgba(244, 63, 94, 0.5)',
            borderDash: [5, 5],
            fill: false,
            pointRadius: 0,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
          y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } }
        }
      }
    });
  },

  renderGeoMap(containerId, geoFeatures, onSegmentClick) {
    const container = document.getElementById(containerId);
    if (!container || !geoFeatures || geoFeatures.length === 0) return;

    if (!window.L) {
      container.innerHTML = '<p class="text-muted">Map library unavailable. Geographic results are still available through the dashboard filters.</p>';
      return;
    }

    container.innerHTML = '<div class="geo-map" style="height: 360px; border-radius: 8px; overflow: hidden;"></div>';
    const map = window.L.map(container.querySelector('.geo-map'), { worldCopyJump: true }).setView([20, 0], 2);
    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);

    const maxValue = Math.max(...geoFeatures.map(feature => feature.metric_value || 0), 1);
    const markers = [];
    geoFeatures.forEach(feature => {
      const radius = 7 + 18 * Math.sqrt((feature.metric_value || 0) / maxValue);
      const marker = window.L.circleMarker([feature.latitude, feature.longitude], {
        radius,
        color: '#0f172a',
        weight: 1,
        fillColor: feature.share_percentage >= 20 ? '#10b981' : '#38bdf8',
        fillOpacity: 0.78,
      }).addTo(map);
      marker.bindPopup(`<strong>${feature.region_name}</strong><br>${feature.formatted_value}<br>${feature.share_percentage}% of total`);
      marker.on('click', () => onSegmentClick(feature.region_name));
      markers.push(marker);
    });

    if (markers.length > 1) {
      map.fitBounds(window.L.featureGroup(markers).getBounds().pad(0.2));
    }
  }
};

