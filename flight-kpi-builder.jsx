import React, { useState, useMemo, useEffect, useRef } from 'react';

// ============================================================================
// 1. DATASET-AGNOSTIC SCHEMA INFERENCE ENGINE
// ============================================================================

/**
 * Auto-detects the analytical role of every column in an arbitrary dataset.
 * Does NOT hardcode any column names.
 */
export function analyzeDatasetSchema(data) {
  if (!data || data.length === 0) return { columns: {}, columnList: [] };

  const sampleSize = Math.min(data.length, 2000);
  const sample = data.slice(0, sampleSize);
  const totalRows = sample.length;
  const colKeys = Object.keys(data[0] || {});

  const columns = {};

  colKeys.forEach((key) => {
    const values = sample.map((row) => row[key]).filter((v) => v !== null && v !== undefined && v !== '');
    const nonNullCount = values.length;
    const uniqueValues = new Set(values.map((v) => String(v).trim()));
    const uniqueCount = uniqueValues.size;
    const uniquenessRatio = nonNullCount > 0 ? uniqueCount / nonNullCount : 0;

    // Check if values represent boolean flags (binary)
    const isBinary =
      uniqueCount <= 2 &&
      Array.from(uniqueValues).every((v) => {
        const lower = v.toLowerCase();
        return ['true', 'false', '1', '0', 'yes', 'no', 't', 'f', 'y', 'n'].includes(lower);
      });

    // Check if values are numeric
    const numericValues = values.map((v) => Number(v)).filter((n) => !isNaN(n));
    const isNumeric = values.length > 0 && numericValues.length / values.length > 0.85;

    // Check if values are temporal (dates/timestamps)
    const isDate =
      !isNumeric &&
      values.length > 0 &&
      values.slice(0, 50).every((v) => {
        const str = String(v).trim();
        return str.length >= 8 && !isNaN(Date.parse(str));
      });

    let role = 'category'; // default

    if (isBinary) {
      role = 'binary_flag';
    } else if (isDate) {
      role = 'temporal_dimension';
    } else if (isNumeric) {
      // Numbers with very few distinct values (e.g. Year [3-4], Month [12], DayOfWeek [7])
      // are dimensions, NOT measurable numbers
      if (uniqueCount <= 12 && uniqueCount < totalRows * 0.05) {
        role = 'discrete_numeric_dimension';
      } else {
        role = 'continuous_measure';
      }
    } else {
      // Text columns: check for unique IDs/keys
      if (uniquenessRatio > 0.85 && uniqueCount > 30) {
        role = 'unique_identifier';
      } else if (uniqueCount <= 5) {
        role = 'low_cardinality_category';
      } else {
        role = 'category';
      }
    }

    // Optional lightweight hint map for formatting units (purely cosmetic)
    const lowerKey = key.toLowerCase();
    let unit = '';
    let format = 'number';

    if (lowerKey.includes('price') || lowerKey.includes('usd') || lowerKey.includes('cost') || lowerKey.includes('revenue') || lowerKey.includes('fare')) {
      unit = '$';
      format = 'currency';
    } else if (lowerKey.includes('delay') || lowerKey.includes('duration') || lowerKey.includes('minute')) {
      unit = 'min';
      format = 'duration';
    } else if (lowerKey.includes('distance') || lowerKey.includes('km')) {
      unit = 'km';
      format = 'number';
    } else if (lowerKey.includes('mile')) {
      unit = 'mi';
      format = 'number';
    } else if (isBinary || lowerKey.includes('factor') || lowerKey.includes('rate') || lowerKey.includes('pct') || lowerKey.includes('percent')) {
      unit = '%';
      format = 'percentage';
    }

    columns[key] = {
      name: key,
      role,
      isNumeric,
      isBinary,
      isDate,
      uniqueCount,
      uniqueValues: Array.from(uniqueValues).slice(0, 100),
      nullCount: totalRows - nonNullCount,
      unit,
      format,
    };
  });

  return {
    columns,
    columnList: colKeys,
    measures: colKeys.filter((k) => columns[k].role === 'continuous_measure'),
    binaryFlags: colKeys.filter((k) => columns[k].role === 'binary_flag'),
    dimensions: colKeys.filter((k) =>
      ['category', 'low_cardinality_category', 'discrete_numeric_dimension', 'temporal_dimension'].includes(columns[k].role)
    ),
    identifiers: colKeys.filter((k) => columns[k].role === 'unique_identifier'),
  };
}

// ============================================================================
// 2. DETERMINISTIC KPI COMPUTATION ENGINE
// ============================================================================

export function computeCustomKPI(data, spec, schema) {
  if (!data || data.length === 0) return null;

  const { measureType, column, aggregation, dimension, filterColumn, filterValue } = spec;

  // 1. Apply optional row-level filter
  let filteredData = data;
  if (filterColumn && filterValue !== '' && filterValue !== undefined && filterValue !== null) {
    filteredData = data.filter((row) => {
      const val = row[filterColumn];
      return String(val).toLowerCase() === String(filterValue).toLowerCase();
    });
  }

  const totalFilteredCount = filteredData.length;

  // Helper to extract numeric value
  const getNumeric = (val) => {
    const n = Number(val);
    return isNaN(n) ? 0 : n;
  };

  // Helper to evaluate truthy for binary flags
  const isTruthy = (val) => {
    if (typeof val === 'boolean') return val;
    const str = String(val).trim().toLowerCase();
    return ['true', '1', 'yes', 't', 'y'].includes(str);
  };

  // Helper to compute a single scalar metric over an array of rows
  const evaluateScalar = (rows) => {
    if (rows.length === 0) return 0;

    if (measureType === 'count') {
      return rows.length;
    }

    if (measureType === 'rate') {
      const trueCount = rows.filter((r) => isTruthy(r[column])).length;
      return (trueCount / rows.length) * 100;
    }

    // Continuous numeric aggregations
    const nums = rows.map((r) => getNumeric(r[column]));
    if (aggregation === 'sum') {
      return nums.reduce((acc, v) => acc + v, 0);
    }
    if (aggregation === 'min') {
      return Math.min(...nums);
    }
    if (aggregation === 'max') {
      return Math.max(...nums);
    }
    // Default: Average
    const sum = nums.reduce((acc, v) => acc + v, 0);
    return sum / nums.length;
  };

  // 2. Compute result (Single KPI vs Grouped Breakdown)
  if (!dimension) {
    // Single KPI Card
    const val = evaluateScalar(filteredData);
    return {
      type: 'scalar',
      value: val,
      rowCount: totalFilteredCount,
      suggestedVisual: 'card',
    };
  }

  // Grouped Breakdown by Dimension
  const groups = {};
  filteredData.forEach((row) => {
    const rawDim = row[dimension];
    const dimVal = rawDim !== null && rawDim !== undefined && rawDim !== '' ? String(rawDim) : 'Unknown';
    if (!groups[dimVal]) groups[dimVal] = [];
    groups[dimVal].push(row);
  });

  const rows = Object.entries(groups).map(([dimVal, groupRows]) => ({
    dimension: dimVal,
    value: evaluateScalar(groupRows),
    count: groupRows.length,
  }));

  // Auto-sort: chronological if temporal, descending by value if categorical
  const dimInfo = schema.columns[dimension] || {};
  if (dimInfo.role === 'temporal_dimension') {
    rows.sort((a, b) => new Date(a.dimension) - new Date(b.dimension));
  } else {
    rows.sort((a, b) => b.value - a.value);
  }

  // Visual type recommendation
  let suggestedVisual = 'bar';
  if (dimInfo.role === 'temporal_dimension') {
    suggestedVisual = 'line';
  } else if (dimInfo.role === 'low_cardinality_category' || rows.length <= 5) {
    suggestedVisual = 'pie';
  } else if (rows.length > 20) {
    suggestedVisual = 'table';
  }

  return {
    type: 'breakdown',
    dimension,
    rows: rows.slice(0, 30), // top 30
    totalGroups: rows.length,
    rowCount: totalFilteredCount,
    suggestedVisual,
  };
}

// ============================================================================
// 3. NUMBER FORMATTER
// ============================================================================

export function formatMetricNumber(val, unit = '', formatType = 'number') {
  if (val === null || val === undefined || isNaN(val)) return '--';

  if (formatType === 'percentage' || unit === '%') {
    return `${val.toFixed(1)}%`;
  }
  if (formatType === 'currency' || unit === '$') {
    if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
    if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
    return `$${val.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  }

  // General numeric
  let formatted = '';
  if (Math.abs(val) >= 1_000_000) {
    formatted = `${(val / 1_000_000).toFixed(2)}M`;
  } else if (Math.abs(val) >= 10_000) {
    formatted = val.toLocaleString(undefined, { maximumFractionDigits: 0 });
  } else if (Number.isInteger(val)) {
    formatted = val.toLocaleString();
  } else {
    formatted = val.toFixed(2);
  }

  return unit ? `${formatted} ${unit}` : formatted;
}

// ============================================================================
// 4. EMBEDDED SVG CHARTS (Zero External Chart Library Dependencies)
// ============================================================================

function SvgBarChart({ rows, unit }) {
  if (!rows || rows.length === 0) return <div style={styles.emptyText}>No data available</div>;

  const maxVal = Math.max(...rows.map((r) => r.value), 0.001);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', width: '100%' }}>
      {rows.slice(0, 10).map((row, i) => {
        const pct = Math.max(0, Math.min(100, (row.value / maxVal) * 100));
        return (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
              <span style={{ color: '#cbd5e1', fontWeight: 500 }}>{row.dimension}</span>
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>{formatMetricNumber(row.value, unit)}</span>
            </div>
            <div style={styles.barTrack}>
              <div
                style={{
                  ...styles.barFill,
                  width: `${pct}%`,
                  background: 'linear-gradient(90deg, #6366f1 0%, #a855f7 100%)',
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SvgLineChart({ rows, unit }) {
  if (!rows || rows.length < 2) {
    return <SvgBarChart rows={rows} unit={unit} />;
  }

  const W = 480;
  const H = 200;
  const PAD = 30;

  const vals = rows.map((r) => r.value);
  const minV = Math.min(...vals);
  const maxV = Math.max(...vals);
  const range = maxV - minV || 1;

  const points = rows.map((r, i) => {
    const x = PAD + (i / (rows.length - 1)) * (W - PAD * 2);
    const y = H - PAD - ((r.value - minV) / range) * (H - PAD * 2);
    return [x, y];
  });

  const pathD = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const areaD = `${pathD} L ${points[points.length - 1][0]} ${H - PAD} L ${points[0][0]} ${H - PAD} Z`;

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', maxHeight: '240px' }}>
        <defs>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#818cf8" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#lineGrad)" />
        <path d={pathD} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round" />
        {points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="3.5" fill="#38bdf8" stroke="#0f172a" strokeWidth="1.5" />
        ))}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8' }}>
        <span>{rows[0].dimension}</span>
        <span>{rows[Math.floor(rows.length / 2)].dimension}</span>
        <span>{rows[rows.length - 1].dimension}</span>
      </div>
    </div>
  );
}

function SvgPieChart({ rows, unit }) {
  if (!rows || rows.length === 0) return <div style={styles.emptyText}>No data available</div>;

  const total = rows.reduce((sum, r) => sum + r.value, 0) || 1;
  const colors = ['#6366f1', '#38bdf8', '#34d399', '#f59e0b', '#ec4899', '#a855f7'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%' }}>
      {rows.slice(0, 5).map((row, i) => {
        const share = ((row.value / total) * 100).toFixed(1);
        const col = colors[i % colors.length];
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: col, display: 'inline-block' }} />
              <span style={{ color: '#cbd5e1', fontSize: '0.8125rem' }}>{row.dimension}</span>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <span style={{ color: '#fff', fontWeight: 600, fontSize: '0.8125rem' }}>{formatMetricNumber(row.value, unit)}</span>
              <span style={styles.badge}>{share}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// 5. MAIN COMPONENT: SELF-SERVICE ANALYTICS PLATFORM
// ============================================================================

export default function FlightKPIBuilder({ initialDataset = null }) {
  // State
  const [activeTab, setActiveTab] = useState('kpi_builder'); // 'kpi_builder' | 'record_explorer'
  const [rawData, setRawData] = useState([]);
  const [savedWidgets, setSavedWidgets] = useState([]);

  // KPI Builder Form State
  const [measureType, setMeasureType] = useState('numeric'); // 'numeric' | 'rate' | 'count'
  const [selectedColumn, setSelectedColumn] = useState('');
  const [selectedAgg, setSelectedAgg] = useState('avg');
  const [selectedDimension, setSelectedDimension] = useState('');
  const [filterCol, setFilterCol] = useState('');
  const [filterVal, setFilterVal] = useState('');
  const [outputType, setOutputType] = useState('auto'); // 'auto' | 'card' | 'bar' | 'line' | 'pie' | 'table'
  const [customTitle, setCustomTitle] = useState('');

  // Record Explorer State
  const [globalSearch, setGlobalSearch] = useState('');
  const [explorerFilterCol1, setExplorerFilterCol1] = useState('');
  const [explorerFilterVal1, setExplorerFilterVal1] = useState('');
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  // 1. Initialize dataset (with realistic fallback sample if none provided)
  useEffect(() => {
    if (initialDataset && initialDataset.length > 0) {
      setRawData(initialDataset);
    } else {
      // High-fidelity fallback representing airline_flights_dataset.csv
      const sampleFlights = generateSampleFlightData();
      setRawData(sampleFlights);
    }
  }, [initialDataset]);

  // 2. Derive Schema dynamically
  const schema = useMemo(() => analyzeDatasetSchema(rawData), [rawData]);

  // 3. Set default form selections once schema is analyzed
  useEffect(() => {
    if (schema.measures.length > 0 && !selectedColumn) {
      // Pick a great measure (e.g. DelayMinutes, Passengers, or first numeric)
      const preferred = schema.measures.find((m) => m.toLowerCase().includes('delay') || m.toLowerCase().includes('pass')) || schema.measures[0];
      setSelectedColumn(preferred);
    }
  }, [schema]);

  // 4. Live Preview Calculation
  const previewSpec = useMemo(
    () => ({
      measureType,
      column: selectedColumn,
      aggregation: selectedAgg,
      dimension: selectedDimension,
      filterColumn: filterCol,
      filterValue: filterVal,
    }),
    [measureType, selectedColumn, selectedAgg, selectedDimension, filterCol, filterVal]
  );

  const previewResult = useMemo(() => {
    if (!rawData.length) return null;
    return computeCustomKPI(rawData, previewSpec, schema);
  }, [rawData, previewSpec, schema]);

  // Resolved visual
  const resolvedVisual = outputType === 'auto' ? previewResult?.suggestedVisual || 'card' : outputType;

  // Active column metadata for units
  const activeColInfo = schema.columns[selectedColumn] || {};
  const activeUnit = measureType === 'rate' ? '%' : activeColInfo.unit || '';

  // 5. Handle Save KPI to Dashboard
  const handleSaveToDashboard = () => {
    if (!previewResult) return;

    const defaultTitle =
      customTitle.trim() ||
      (measureType === 'count'
        ? 'Total Flight Count'
        : measureType === 'rate'
        ? `Rate of ${selectedColumn}`
        : `${selectedAgg.toUpperCase()} of ${selectedColumn}`) +
        (selectedDimension ? ` by ${selectedDimension}` : '');

    const newWidget = {
      id: `kpi_${Date.now()}`,
      title: defaultTitle,
      spec: { ...previewSpec },
      result: previewResult,
      resolvedVisual,
      unit: activeUnit,
      createdAt: new Date().toLocaleTimeString(),
    };

    setSavedWidgets((prev) => [newWidget, ...prev]);
    setCustomTitle('');
  };

  const handleRemoveWidget = (widgetId) => {
    setSavedWidgets((prev) => prev.filter((w) => w.id !== widgetId));
  };

  // 6. Record Explorer: Global Full-Text Search across ALL columns
  const filteredRecords = useMemo(() => {
    if (!rawData.length) return [];

    return rawData.filter((row) => {
      // 1. Optional Dimension Filter
      if (explorerFilterCol1 && explorerFilterVal1) {
        if (String(row[explorerFilterCol1]).toLowerCase() !== explorerFilterVal1.toLowerCase()) {
          return false;
        }
      }

      // 2. Global Universal Search across EVERY column simultaneously
      if (globalSearch.trim() !== '') {
        const query = globalSearch.toLowerCase();
        const matchesAnyField = Object.values(row).some((val) => String(val).toLowerCase().includes(query));
        if (!matchesAnyField) return false;
      }

      return true;
    });
  }, [rawData, globalSearch, explorerFilterCol1, explorerFilterVal1]);

  const totalPages = Math.ceil(filteredRecords.length / pageSize) || 1;
  const paginatedRecords = filteredRecords.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // File Upload Handler (Generalizes to any CSV)
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const text = evt.target.result;
      const parsed = parseCSVToJSON(text);
      if (parsed.length > 0) {
        setRawData(parsed);
        setSelectedColumn('');
        setSelectedDimension('');
        setSavedWidgets([]);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div style={styles.appWrap}>
      {/* Top Header */}
      <header style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={styles.brandIcon}>✈</div>
          <div>
            <h1 style={styles.title}>Self-Service Analytics & Record Platform</h1>
            <p style={styles.subtitle}>
              Dataset: {rawData.length.toLocaleString()} records • {schema.columnList.length} auto-detected columns
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* CSV File Input */}
          <label style={styles.btnSecondary}>
            <span>Upload Any CSV</span>
            <input type="file" accept=".csv" onChange={handleFileUpload} style={{ display: 'none' }} />
          </label>

          {/* Tab Switcher */}
          <div style={styles.tabGroup}>
            <button
              onClick={() => setActiveTab('kpi_builder')}
              style={{ ...styles.tabBtn, ...(activeTab === 'kpi_builder' ? styles.tabBtnActive : {}) }}
            >
              1. KPI Builder
            </button>
            <button
              onClick={() => setActiveTab('record_explorer')}
              style={{ ...styles.tabBtn, ...(activeTab === 'record_explorer' ? styles.tabBtnActive : {}) }}
            >
              2. Record Explorer
            </button>
          </div>
        </div>
      </header>

      {/* =================================================================== */}
      {/* TAB 1: KPI BUILDER                                                  */}
      {/* =================================================================== */}
      {activeTab === 'kpi_builder' && (
        <div style={styles.mainGrid}>
          {/* Left Column: KPI Formulation Controls */}
          <div style={styles.configCard}>
            <h2 style={styles.sectionHeader}>Build Custom Business KPI</h2>
            <p style={{ fontSize: '0.8125rem', color: '#94a3b8', marginBottom: '1.25rem' }}>
              Select columns and aggregations. Columns are auto-categorized by statistical behavior.
            </p>

            {/* 1. Measure Category */}
            <div style={styles.formGroup}>
              <label style={styles.label}>1. What would you like to calculate?</label>
              <div style={styles.btnGrid3}>
                <button
                  type="button"
                  onClick={() => setMeasureType('numeric')}
                  style={{ ...styles.pillBtn, ...(measureType === 'numeric' ? styles.pillBtnActive : {}) }}
                >
                  Numeric Metric
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMeasureType('rate');
                    if (schema.binaryFlags.length > 0 && !schema.binaryFlags.includes(selectedColumn)) {
                      setSelectedColumn(schema.binaryFlags[0]);
                    }
                  }}
                  style={{ ...styles.pillBtn, ...(measureType === 'rate' ? styles.pillBtnActive : {}) }}
                >
                  Rate / Percentage (%)
                </button>
                <button
                  type="button"
                  onClick={() => setMeasureType('count')}
                  style={{ ...styles.pillBtn, ...(measureType === 'count' ? styles.pillBtnActive : {}) }}
                >
                  Record Count
                </button>
              </div>
            </div>

            {/* 2. Column Selection */}
            {measureType !== 'count' && (
              <div style={styles.formGroup}>
                <label style={styles.label}>
                  {measureType === 'rate' ? 'Target Boolean Flag:' : 'Target Numeric Column:'}
                </label>
                <select value={selectedColumn} onChange={(e) => setSelectedColumn(e.target.value)} style={styles.select}>
                  {measureType === 'rate' ? (
                    <optgroup label="Auto-Detected Binary Flags">
                      {schema.binaryFlags.map((col) => (
                        <option key={col} value={col}>
                          {col} (Boolean flag)
                        </option>
                      ))}
                    </optgroup>
                  ) : (
                    <optgroup label="Auto-Detected Numeric Measures">
                      {schema.measures.map((col) => (
                        <option key={col} value={col}>
                          {col} (continuous measure)
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </div>
            )}

            {/* 3. Aggregation Type (for continuous measures) */}
            {measureType === 'numeric' && (
              <div style={styles.formGroup}>
                <label style={styles.label}>Aggregation Type:</label>
                <div style={styles.btnGrid4}>
                  {['avg', 'sum', 'min', 'max'].map((agg) => (
                    <button
                      key={agg}
                      type="button"
                      onClick={() => setSelectedAgg(agg)}
                      style={{ ...styles.pillBtn, ...(selectedAgg === agg ? styles.pillBtnActive : {}) }}
                    >
                      {agg.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 4. Breakdown By (Dimension) */}
            <div style={styles.formGroup}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={styles.label}>Break Down By (Optional Dimension):</label>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Leave empty for Single KPI Card</span>
              </div>
              <select value={selectedDimension} onChange={(e) => setSelectedDimension(e.target.value)} style={styles.select}>
                <option value="">(None - Overall Aggregate)</option>
                <optgroup label="Auto-Detected Grouping Dimensions">
                  {schema.dimensions.map((dim) => {
                    const info = schema.columns[dim];
                    return (
                      <option key={dim} value={dim}>
                        {dim} ({info.role.replace(/_/g, ' ')})
                      </option>
                    );
                  })}
                </optgroup>
              </select>
            </div>

            {/* 5. Optional Row Filter */}
            <div style={styles.formGroup}>
              <label style={styles.label}>Filter by Specific Value (Optional):</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <select
                  value={filterCol}
                  onChange={(e) => {
                    setFilterCol(e.target.value);
                    setFilterVal('');
                  }}
                  style={styles.select}
                >
                  <option value="">All Records (No filter)</option>
                  {schema.dimensions.map((d) => (
                    <option key={d} value={d}>
                      Filter by {d}
                    </option>
                  ))}
                </select>

                <select
                  value={filterVal}
                  onChange={(e) => setFilterVal(e.target.value)}
                  disabled={!filterCol}
                  style={styles.select}
                >
                  <option value="">(Select value)</option>
                  {filterCol &&
                    (schema.columns[filterCol]?.uniqueValues || []).map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                </select>
              </div>
            </div>

            {/* 6. Output Type Selector */}
            <div style={styles.formGroup}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={styles.label}>Visualization Output:</label>
                <span style={styles.badgePurple}>Auto-inferred: {previewResult?.suggestedVisual}</span>
              </div>
              <div style={styles.btnGrid3}>
                {['auto', 'card', 'bar', 'line', 'pie', 'table'].map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setOutputType(t)}
                    style={{ ...styles.pillBtn, ...(outputType === t ? styles.pillBtnActive : {}) }}
                  >
                    {t === 'auto' ? '✦ Auto-Suggest' : t.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Title & Save */}
            <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
              <input
                type="text"
                placeholder="Custom Widget Title (Optional)"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                style={{ ...styles.input, marginBottom: '0.75rem' }}
              />
              <button onClick={handleSaveToDashboard} style={styles.btnPrimaryFull}>
                ✦ Save KPI to Dashboard
              </button>
            </div>
          </div>

          {/* Right Column: Live Interactive Preview Card */}
          <div style={styles.previewCard}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <span style={styles.previewTag}>LIVE CALCULATION PREVIEW</span>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                {previewResult?.rowCount.toLocaleString()} rows computed
              </span>
            </div>

            <div style={styles.previewContent}>
              {/* Scalar KPI Card View */}
              {resolvedVisual === 'card' && (
                <div style={{ textAlign: 'center', padding: '2rem 1rem' }}>
                  <div style={{ fontSize: '1rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
                    {measureType === 'count'
                      ? 'Total Count'
                      : measureType === 'rate'
                      ? `Rate of ${selectedColumn}`
                      : `${selectedAgg.toUpperCase()} of ${selectedColumn}`}
                  </div>
                  <div style={{ fontSize: '3.5rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.03em' }}>
                    {formatMetricNumber(previewResult?.value, activeUnit)}
                  </div>
                  {filterCol && filterVal && (
                    <div style={{ fontSize: '0.8125rem', color: '#38bdf8', marginTop: '0.5rem' }}>
                      Filtered where {filterCol} = {filterVal}
                    </div>
                  )}
                </div>
              )}

              {/* Bar Chart View */}
              {resolvedVisual === 'bar' && previewResult?.rows && (
                <SvgBarChart rows={previewResult.rows} unit={activeUnit} />
              )}

              {/* Line Chart View */}
              {resolvedVisual === 'line' && previewResult?.rows && (
                <SvgLineChart rows={previewResult.rows} unit={activeUnit} />
              )}

              {/* Pie / Donut View */}
              {resolvedVisual === 'pie' && previewResult?.rows && (
                <SvgPieChart rows={previewResult.rows} unit={activeUnit} />
              )}

              {/* Table View */}
              {resolvedVisual === 'table' && previewResult?.rows && (
                <div style={{ maxHeight: '320px', overflowY: 'auto', width: '100%' }}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.th}>{selectedDimension}</th>
                        <th style={styles.th}>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewResult.rows.map((r, i) => (
                        <tr key={i} style={styles.tr}>
                          <td style={styles.td}>{r.dimension}</td>
                          <td style={{ ...styles.td, color: '#38bdf8', fontWeight: 600 }}>
                            {formatMetricNumber(r.value, activeUnit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Saved Dashboard Widgets Grid */}
      {activeTab === 'kpi_builder' && savedWidgets.length > 0 && (
        <section style={{ marginTop: '2.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>Persistent Custom Dashboard</h3>
            <span style={styles.badge}>{savedWidgets.length} Saved KPIs</span>
          </div>

          <div style={styles.widgetsGrid}>
            {savedWidgets.map((widget) => (
              <div key={widget.id} style={styles.widgetCard}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                  <div>
                    <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>{widget.title}</h4>
                    <span style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Saved at {widget.createdAt}</span>
                  </div>
                  <button onClick={() => handleRemoveWidget(widget.id)} style={styles.removeBtn} title="Remove widget">
                    &times;
                  </button>
                </div>

                {widget.resolvedVisual === 'card' && (
                  <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                    <div style={{ fontSize: '2.25rem', fontWeight: 800, color: '#fff' }}>
                      {formatMetricNumber(widget.result.value, widget.unit)}
                    </div>
                  </div>
                )}

                {widget.resolvedVisual === 'bar' && (
                  <SvgBarChart rows={widget.result.rows} unit={widget.unit} />
                )}

                {widget.resolvedVisual === 'line' && (
                  <SvgLineChart rows={widget.result.rows} unit={widget.unit} />
                )}

                {widget.resolvedVisual === 'pie' && (
                  <SvgPieChart rows={widget.result.rows} unit={widget.unit} />
                )}

                {widget.resolvedVisual === 'table' && (
                  <div style={{ maxHeight: '180px', overflowY: 'auto' }}>
                    <table style={styles.table}>
                      <thead>
                        <tr>
                          <th style={styles.th}>{widget.spec.dimension}</th>
                          <th style={styles.th}>Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {widget.result.rows.slice(0, 5).map((r, i) => (
                          <tr key={i} style={styles.tr}>
                            <td style={styles.td}>{r.dimension}</td>
                            <td style={{ ...styles.td, color: '#38bdf8', fontWeight: 600 }}>
                              {formatMetricNumber(r.value, widget.unit)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* =================================================================== */}
      {/* TAB 2: RECORD EXPLORER                                              */}
      {/* =================================================================== */}
      {activeTab === 'record_explorer' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Search and Filters Bar */}
          <div style={styles.explorerToolbar}>
            {/* Universal Search across ALL columns */}
            <div style={{ flex: 2, position: 'relative' }}>
              <input
                type="text"
                placeholder="🔍 Universal Search across ALL columns (Flight, Route, City, Price, Gate, Aircraft...)"
                value={globalSearch}
                onChange={(e) => {
                  setGlobalSearch(e.target.value);
                  setCurrentPage(1);
                }}
                style={styles.searchInput}
              />
              {globalSearch && (
                <button onClick={() => setGlobalSearch('')} style={styles.clearSearchBtn}>
                  &times;
                </button>
              )}
            </div>

            {/* Dimension Filter 1 */}
            <div style={{ flex: 1, display: 'flex', gap: '0.5rem' }}>
              <select
                value={explorerFilterCol1}
                onChange={(e) => {
                  setExplorerFilterCol1(e.target.value);
                  setExplorerFilterVal1('');
                  setCurrentPage(1);
                }}
                style={styles.select}
              >
                <option value="">Filter by Dimension...</option>
                {schema.dimensions.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>

              {explorerFilterCol1 && (
                <select
                  value={explorerFilterVal1}
                  onChange={(e) => {
                    setExplorerFilterVal1(e.target.value);
                    setCurrentPage(1);
                  }}
                  style={styles.select}
                >
                  <option value="">All</option>
                  {(schema.columns[explorerFilterCol1]?.uniqueValues || []).map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Results Summary */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8125rem', color: '#94a3b8' }}>
            <span>
              Showing {filteredRecords.length.toLocaleString()} matching records (Click any row to inspect all 33+ fields)
            </span>
            <span>
              Page {currentPage} of {totalPages}
            </span>
          </div>

          {/* Records Table */}
          <div style={styles.tableContainer}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {schema.columnList.slice(0, 7).map((col) => (
                    <th key={col} style={styles.th}>
                      {col}
                    </th>
                  ))}
                  <th style={styles.th}>Action</th>
                </tr>
              </thead>
              <tbody>
                {paginatedRecords.map((row, idx) => (
                  <tr
                    key={idx}
                    onClick={() => setSelectedRecord(row)}
                    style={{ ...styles.tr, cursor: 'pointer' }}
                    title="Click to view all fields"
                  >
                    {schema.columnList.slice(0, 7).map((col) => (
                      <td key={col} style={styles.td}>
                        {String(row[col] ?? '—')}
                      </td>
                    ))}
                    <td style={styles.td}>
                      <span style={styles.badgeIndigo}>Inspect Full Row &rarr;</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              style={{ ...styles.btnSecondary, opacity: currentPage === 1 ? 0.5 : 1 }}
            >
              &larr; Previous
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              style={{ ...styles.btnSecondary, opacity: currentPage === totalPages ? 0.5 : 1 }}
            >
              Next &rarr;
            </button>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* 33+ COLUMN FULL RECORD DETAIL MODAL                                 */}
      {/* =================================================================== */}
      {selectedRecord && (
        <div style={styles.modalOverlay} onClick={() => setSelectedRecord(null)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '1rem', marginBottom: '1.25rem' }}>
              <div>
                <span style={styles.badgeCyan}>FULL ROW INSPECTOR</span>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff', marginTop: '0.25rem' }}>
                  Record Detail View ({schema.columnList.length} Fields)
                </h3>
              </div>
              <button onClick={() => setSelectedRecord(null)} style={styles.closeModalBtn}>
                &times;
              </button>
            </div>

            {/* Field Grid Listing ALL 33+ Columns */}
            <div style={styles.detailGrid}>
              {schema.columnList.map((col) => {
                const val = selectedRecord[col];
                const info = schema.columns[col] || {};
                const isNull = val === null || val === undefined || val === '';

                return (
                  <div key={col} style={styles.detailFieldCard}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>{col}</span>
                      <span style={{ fontSize: '0.625rem', color: '#64748b', textTransform: 'uppercase' }}>
                        {info.role?.replace(/_/g, ' ') || 'field'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: isNull ? '#64748b' : '#f8fafc', wordBreak: 'break-word' }}>
                      {isNull ? 'null' : String(val)}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button onClick={() => setSelectedRecord(null)} style={styles.btnSecondary}>
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 6. CSV PARSER & FALLBACK SAMPLE FLIGHT GENERATOR
// ============================================================================

function parseCSVToJSON(csvText) {
  const lines = csvText.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return [];

  const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''));
  const rows = [];

  for (let i = 1; i < lines.length; i++) {
    const rawCols = lines[i].split(',');
    if (rawCols.length !== headers.length) continue;

    const row = {};
    headers.forEach((h, idx) => {
      let val = rawCols[idx].trim().replace(/^"|"$/g, '');
      if (val.toLowerCase() === 'true') val = true;
      else if (val.toLowerCase() === 'false') val = false;
      else if (!isNaN(Number(val)) && val !== '') val = Number(val);
      row[h] = val;
    });
    rows.push(row);
  }
  return rows;
}

function generateSampleFlightData() {
  const airlines = ['Delta Air Lines', 'American Airlines', 'United Airlines', 'Southwest Airlines', 'Lufthansa'];
  const routes = ['JFK-LAX', 'ORD-DFW', 'ATL-MIA', 'SFO-SEA', 'LHR-JFK', 'DXB-SIN'];
  const aircrafts = ['Boeing 737-800', 'Airbus A320', 'Boeing 787-9', 'Airbus A350-900', 'Boeing 777-300ER'];
  const cabinClasses = ['Economy', 'Premium Economy', 'Business', 'First'];

  const rows = [];
  for (let i = 1; i <= 200; i++) {
    const isDelayed = Math.random() < 0.22;
    const isCancelled = !isDelayed && Math.random() < 0.03;
    const capacity = [160, 180, 240, 300][Math.floor(Math.random() * 4)];
    const passengers = Math.round(capacity * (0.65 + Math.random() * 0.32));

    rows.push({
      FlightID: `FL-${100000 + i}`,
      FlightNumber: `FL${200 + (i % 80)}`,
      Airline: airlines[i % airlines.length],
      Route: routes[i % routes.length],
      OriginCity: routes[i % routes.length].split('-')[0],
      DestinationCity: routes[i % routes.length].split('-')[1],
      ScheduledDeparture: `2024-${String((i % 12) + 1).padStart(2, '0')}-15 08:30`,
      ActualDeparture: isDelayed ? `2024-${String((i % 12) + 1).padStart(2, '0')}-15 09:12` : `2024-${String((i % 12) + 1).padStart(2, '0')}-15 08:32`,
      DelayMinutes: isDelayed ? Math.round(15 + Math.random() * 65) : 0,
      Status: isCancelled ? 'Cancelled' : isDelayed ? 'Delayed' : 'On-Time',
      AircraftType: aircrafts[i % aircrafts.length],
      Capacity: capacity,
      Passengers: passengers,
      LoadFactor: Number((passengers / capacity).toFixed(2)),
      TicketPriceUSD: Math.round(180 + Math.random() * 420),
      CabinClass: cabinClasses[i % cabinClasses.length],
      Terminal: `T${(i % 5) + 1}`,
      Gate: `G${(i % 30) + 1}`,
      Year: 2024,
      Month: (i % 12) + 1,
      DayOfWeek: (i % 7) + 1,
      IsDelayed: isDelayed,
      IsCancelled: isCancelled,
      IsInternational: i % 3 === 0,
    });
  }
  return rows;
}

// ============================================================================
// 7. COMPONENT STYLES (Modern Glassmorphic Dark UI)
// ============================================================================

const styles = {
  appWrap: {
    minHeight: '100vh',
    background: '#07091a',
    color: '#f8fafc',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    padding: '2rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '1rem',
    marginBottom: '2rem',
    paddingBottom: '1.25rem',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
  },
  brandIcon: {
    width: '40px',
    height: '40px',
    borderRadius: '10px',
    background: 'linear-gradient(135deg, #6366f1, #a855f7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '1.25rem',
  },
  title: { fontSize: '1.35rem', fontWeight: 800, margin: 0, letterSpacing: '-0.02em' },
  subtitle: { fontSize: '0.8125rem', color: '#94a3b8', margin: '0.2rem 0 0 0' },
  tabGroup: {
    display: 'flex',
    background: 'rgba(15, 23, 42, 0.6)',
    padding: '0.25rem',
    borderRadius: '8px',
    border: '1px solid rgba(255,255,255,0.08)',
  },
  tabBtn: {
    background: 'transparent',
    border: 'none',
    color: '#94a3b8',
    padding: '0.45rem 1rem',
    borderRadius: '6px',
    fontWeight: 600,
    fontSize: '0.8125rem',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  tabBtnActive: {
    background: '#6366f1',
    color: '#fff',
    boxShadow: '0 2px 10px rgba(99, 102, 241, 0.4)',
  },
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: '1.2fr 0.8fr',
    gap: '1.5rem',
    alignItems: 'start',
  },
  configCard: {
    background: 'rgba(20, 24, 50, 0.55)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px',
    padding: '1.75rem',
  },
  previewCard: {
    background: 'rgba(20, 24, 50, 0.55)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px',
    padding: '1.75rem',
    minHeight: '480px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
  },
  previewTag: {
    fontSize: '0.6875rem',
    fontWeight: 700,
    color: '#a5b4fc',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  previewContent: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    padding: '1rem 0',
  },
  sectionHeader: { fontSize: '1.125rem', fontWeight: 700, margin: '0 0 0.25rem 0' },
  formGroup: { marginBottom: '1.125rem' },
  label: { display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '0.4rem' },
  select: {
    width: '100%',
    padding: '0.55rem 0.75rem',
    background: 'rgba(15, 23, 42, 0.7)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '0.8125rem',
    outline: 'none',
  },
  input: {
    width: '100%',
    padding: '0.55rem 0.75rem',
    background: 'rgba(15, 23, 42, 0.7)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '0.8125rem',
    outline: 'none',
    boxSizing: 'border-box',
  },
  btnGrid3: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.4rem' },
  btnGrid4: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.4rem' },
  pillBtn: {
    background: 'rgba(15, 23, 42, 0.7)',
    border: '1px solid rgba(255,255,255,0.08)',
    color: '#94a3b8',
    padding: '0.45rem 0.5rem',
    borderRadius: '6px',
    fontSize: '0.75rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  pillBtnActive: {
    background: 'linear-gradient(135deg, #6366f1, #a855f7)',
    color: '#fff',
    borderColor: '#818cf8',
    boxShadow: '0 2px 10px rgba(99, 102, 241, 0.35)',
  },
  btnPrimaryFull: {
    width: '100%',
    padding: '0.75rem',
    background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
    border: 'none',
    borderRadius: '8px',
    color: '#fff',
    fontWeight: 700,
    fontSize: '0.875rem',
    cursor: 'pointer',
    boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)',
  },
  btnSecondary: {
    padding: '0.45rem 0.85rem',
    background: 'rgba(15, 23, 42, 0.6)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '6px',
    color: '#cbd5e1',
    fontWeight: 600,
    fontSize: '0.8125rem',
    cursor: 'pointer',
  },
  widgetsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '1.25rem',
  },
  widgetCard: {
    background: 'rgba(20, 24, 50, 0.55)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '12px',
    padding: '1.25rem',
  },
  removeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#f43f5e',
    fontSize: '1.25rem',
    cursor: 'pointer',
  },
  barTrack: {
    width: '100%',
    height: '6px',
    background: 'rgba(255,255,255,0.06)',
    borderRadius: '999px',
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: '999px' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' },
  th: {
    textAlign: 'left',
    padding: '0.5rem',
    color: '#94a3b8',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
  },
  td: { padding: '0.5rem', borderBottom: '1px solid rgba(255,255,255,0.04)' },
  tr: { transition: 'background 0.15s' },
  badge: {
    padding: '0.15rem 0.5rem',
    borderRadius: '999px',
    background: 'rgba(99, 102, 241, 0.15)',
    color: '#a5b4fc',
    fontSize: '0.6875rem',
    fontWeight: 600,
  },
  badgePurple: {
    padding: '0.15rem 0.5rem',
    borderRadius: '999px',
    background: 'rgba(168, 85, 247, 0.15)',
    color: '#d8b4fe',
    fontSize: '0.6875rem',
    fontWeight: 600,
  },
  badgeIndigo: {
    padding: '0.15rem 0.5rem',
    borderRadius: '999px',
    background: 'rgba(99, 102, 241, 0.2)',
    color: '#c7d2fe',
    fontSize: '0.6875rem',
    fontWeight: 600,
  },
  badgeCyan: {
    padding: '0.15rem 0.5rem',
    borderRadius: '999px',
    background: 'rgba(34, 211, 238, 0.15)',
    color: '#67e8f9',
    fontSize: '0.6875rem',
    fontWeight: 600,
  },
  explorerToolbar: {
    display: 'flex',
    gap: '0.75rem',
    background: 'rgba(20, 24, 50, 0.55)',
    padding: '1rem',
    borderRadius: '12px',
    border: '1px solid rgba(255,255,255,0.08)',
  },
  searchInput: {
    width: '100%',
    padding: '0.65rem 2rem 0.65rem 0.85rem',
    background: 'rgba(15, 23, 42, 0.7)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '0.875rem',
    boxSizing: 'border-box',
    outline: 'none',
  },
  clearSearchBtn: {
    position: 'absolute',
    right: '8px',
    top: '50%',
    transform: 'translateY(-50%)',
    background: 'transparent',
    border: 'none',
    color: '#94a3b8',
    fontSize: '1.1rem',
    cursor: 'pointer',
  },
  tableContainer: {
    background: 'rgba(20, 24, 50, 0.55)',
    borderRadius: '12px',
    border: '1px solid rgba(255,255,255,0.08)',
    overflowX: 'auto',
  },
  modalOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.8)',
    backdropFilter: 'blur(8px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 3000,
    padding: '1.5rem',
  },
  modalContent: {
    background: '#0b0f19',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '16px',
    padding: '1.75rem',
    maxWidth: '900px',
    width: '100%',
    maxHeight: '85vh',
    overflowY: 'auto',
  },
  closeModalBtn: {
    background: 'transparent',
    border: 'none',
    color: '#94a3b8',
    fontSize: '1.5rem',
    cursor: 'pointer',
  },
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: '0.75rem',
  },
  detailFieldCard: {
    background: 'rgba(15, 23, 42, 0.6)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: '8px',
    padding: '0.75rem',
  },
  emptyText: { color: '#94a3b8', fontSize: '0.8125rem' },
};
