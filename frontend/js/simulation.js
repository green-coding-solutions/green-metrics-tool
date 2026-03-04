
const MINI_CHART_COLORS = {
    provider: '#6ea9c9',
    metric: '#5c9d6e'
};
const SIMULATION_CHART_COLORS = {
    provider: '#6ea9c9',
    emission: '#5c9d6e'
};
const DEFAULT_PROVIDER_HISTORY_FALLBACK_HALF_WINDOW_MS = 30 * 60 * 1000; // 30 minutes
const PROVIDER_HISTORY_PAST_HOURS = 12;
const PROVIDER_HISTORY_FUTURE_HOURS = 12;
const METRIC_SHIFT_STEP_MS = 5 * 60 * 1000; // 5 minutes
const SHIFT_ONE_HOUR_MS = 60 * 60 * 1000;
const SHIFT_ONE_DAY_MS = 24 * 60 * 60 * 1000;
const SHIFT_THIRTY_DAYS_MS = 30 * SHIFT_ONE_DAY_MS;
const NO_METRIC_DATA_DETAIL = 'Either the run has not produced any data yet, or the data was deleted. In the latter case consider upgrading to a paid plan to retain data for longer periods (30-90 days by default).';
const BEST_RUNTIME_STEP_RULES = [
    { maxWindowMs: SHIFT_ONE_DAY_MS, stepMs:            5 * 60 * 1000 }, // <= 1 day
    { maxWindowMs: 3 * SHIFT_ONE_DAY_MS, stepMs:        15 * 60 * 1000 }, // > 1 day to <= 3 days
    { maxWindowMs: 5 * SHIFT_ONE_DAY_MS, stepMs:        30 * 60 * 1000 }, // > 3 days to <= 5 days
    { maxWindowMs: Number.POSITIVE_INFINITY, stepMs:    60 * 60 * 1000  } // > 5 days
];

const query = (selector) => document.querySelector(selector);

const setTextContent = (selector, value) => {
    query(selector).textContent = value;
};

const bindClick = (selector, handler) => {
    query(selector).addEventListener('click', handler);
};

const setButtonDisabledState = (button, disabled) => {
    button.classList.toggle('disabled', disabled);
    if (disabled) {
        button.setAttribute('disabled', 'disabled');
    } else {
        button.removeAttribute('disabled');
    }
};

const setButtonLoadingState = (button, loading) => {
    button.classList.toggle('loading', loading);
};

const getBestRuntimeStepMs = (searchWindowMs) => {
    const rule = BEST_RUNTIME_STEP_RULES.find((entry) => searchWindowMs <= entry.maxWindowMs);
    return rule
        ? rule.stepMs
        : BEST_RUNTIME_STEP_RULES[1].stepMs; // Default to 10 minutes if no rule matches (should not happen)
};

const simulationState = {
    runId: null,
    runTimes: null,
    chart: null,
    measurements: [],
    availableMetrics: [],
    providers: [],
    selectedProvider: null,
    selectedMetric: null,
    providerMiniChart: null,
    metricMiniChart: null,
    providerMiniRequestId: 0,
    providerHistory: null,
    providerRangeStartMs: null,
    providerRangeEndMs: null,
    metricTimeOffsetMs: 0,
    shiftInProgress: false,
    resizeHandlerBound: false,
    providerAutoFallbackActive: false,
    bestRuntime: null,
    bestRuntimeSearching: false,
    bestProviderSearching: false
};

const setDropdownLoading = (selector, loading) => {
    const dropdown = query(selector);
    dropdown.classList.toggle('loading', loading);
};

const setProviderDropdownLoading = (loading) => {
    setDropdownLoading('#provider-dropdown', loading);
};

const setMetricDropdownLoading = (loading) => {
    setDropdownLoading('#metric-dropdown', loading);
};

const setMiniChartPlaceholder = (selector, message) => {
    const container = query(selector);
    container.innerHTML = '';
    const placeholder = document.createElement('div');
    placeholder.className = 'simulation-mini-chart-placeholder';
    placeholder.textContent = message;
    container.appendChild(placeholder);
};

const resetMiniChart = (chartKey, selector, message) => {
    if (simulationState[chartKey]) {
        simulationState[chartKey].dispose();
        simulationState[chartKey] = null;
    }
    setMiniChartPlaceholder(selector, message);
};

const setShiftButtonsDisabled = (disabled) => {
    const buttons = [
        query('#shift-left'),
        query('#shift-right'),
        query('#shift-left-hour'),
        query('#shift-right-hour'),
        query('#shift-left-day'),
        query('#shift-right-day'),
        query('#shift-left-30d'),
        query('#shift-right-30d')
    ];
    buttons.forEach((button) => setButtonDisabledState(button, disabled));
};

const logSimulationDebug = (...args) => {
    if (!window.SIMULATION_DEBUG) return;
    console.log('[simulation]', ...args);
};

const updateShiftButtonsAvailability = () => {
    const ready = Boolean(
        simulationState.selectedProvider
        && simulationState.selectedMetric
        && simulationState.providerHistory
        && !simulationState.shiftInProgress
    );
    setShiftButtonsDisabled(!ready);
    updateBestRuntimeAvailability();
};

const toLocalDatetimeInputValue = (timeMs) => {
    const date = new Date(timeMs);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (value) => String(value).padStart(2, '0');
    const year = date.getFullYear();
    const month = pad(date.getMonth() + 1);
    const day = pad(date.getDate());
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    return `${year}-${month}-${day}T${hours}:${minutes}`;
};

const parseLocalDatetimeInputValue = (value) => {
    const parsed = new Date(value);
    const timeMs = parsed.getTime();
    return Number.isNaN(timeMs) ? null : timeMs;
};

const getDefaultProviderHistoryRangeMs = () => {
    const anchorMs = simulationState.runTimes?.startMs ?? Date.now();
    const halfWindowMs = DEFAULT_PROVIDER_HISTORY_FALLBACK_HALF_WINDOW_MS;
    return {
        startMs: anchorMs - halfWindowMs,
        endMs: anchorMs + halfWindowMs
    };
};

const getProviderHistoryRangeAroundTimeMs = (anchorMs) => {
    const pastWindowMs = PROVIDER_HISTORY_PAST_HOURS * 60 * 60 * 1000;
    const futureWindowMs = PROVIDER_HISTORY_FUTURE_HOURS * 60 * 60 * 1000;
    return {
        startMs: anchorMs - pastWindowMs,
        endMs: anchorMs + futureWindowMs
    };
};

const ensureProviderHistoryRange = () => {
    if (simulationState.providerRangeStartMs != null && simulationState.providerRangeEndMs != null) {
        return {
            startMs: simulationState.providerRangeStartMs,
            endMs: simulationState.providerRangeEndMs
        };
    }
    const defaults = getDefaultProviderHistoryRangeMs();
    simulationState.providerRangeStartMs = defaults.startMs;
    simulationState.providerRangeEndMs = defaults.endMs;
    return defaults;
};

const openDatetimePicker = (input) => {
    if (typeof input.showPicker === 'function') {
        try {
            input.focus({ preventScroll: true });
            input.showPicker();
            return;
        } catch (err) {
            // Fall back to manual prompt below.
        }
    }
    const currentValue = input.value ? input.value.replace('T', ' ') : '';
    const enteredValue = window.prompt('Enter date and time (YYYY-MM-DD HH:mm)', currentValue);
    if (enteredValue == null) return;
    const normalizedValue = enteredValue.trim().replace(' ', 'T');
    const parsedMs = parseLocalDatetimeInputValue(normalizedValue);
    if (parsedMs == null) {
        showNotification('Invalid date/time', 'Use the format YYYY-MM-DD HH:mm.');
        return;
    }
    input.value = toLocalDatetimeInputValue(parsedMs);
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('change'));
};

const getProviderRangeElements = () => ({
    startButton: query('#provider-range-start-button'),
    endButton: query('#provider-range-end-button'),
    startInput: query('#provider-range-start-input'),
    endInput: query('#provider-range-end-input')
});

const updateProviderRangeControls = () => {
    const {
        startButton,
        endButton,
        startInput,
        endInput
    } = getProviderRangeElements();
    const { startMs, endMs } = ensureProviderHistoryRange();
    const startLabel = new Date(startMs).toLocaleString();
    const endLabel = new Date(endMs).toLocaleString();

    if (startButton) startButton.textContent = `Start: ${startLabel}`;
    if (endButton) endButton.textContent = `End: ${endLabel}`;

    if (startInput) {
        startInput.value = toLocalDatetimeInputValue(startMs);
        startInput.max = toLocalDatetimeInputValue(endMs);
    }
    if (endInput) {
        endInput.value = toLocalDatetimeInputValue(endMs);
        endInput.min = toLocalDatetimeInputValue(startMs);
    }
};

const setProviderHistoryRange = (startMs, endMs, refreshProvider = true, providerOptions = {}) => {
    let resolvedStart = startMs;
    let resolvedEnd = endMs;
    if (resolvedStart > resolvedEnd) {
        [resolvedStart, resolvedEnd] = [resolvedEnd, resolvedStart];
    }
    simulationState.providerRangeStartMs = resolvedStart;
    simulationState.providerRangeEndMs = resolvedEnd;
    updateProviderRangeControls();
    if (refreshProvider && simulationState.selectedProvider) {
        return updateProviderMiniChart(simulationState.selectedProvider, providerOptions);
    }
    return Promise.resolve(true);
};

const bindProviderRangeControls = () => {
    const {
        startButton,
        endButton,
        startInput,
        endInput
    } = getProviderRangeElements();

    startButton.addEventListener('click', () => openDatetimePicker(startInput));
    endButton.addEventListener('click', () => openDatetimePicker(endInput));

    const handleStartInput = (refreshProvider) => {
        const parsedStart = parseLocalDatetimeInputValue(startInput.value);
        if (parsedStart == null) {
            updateProviderRangeControls();
            return;
        }
        const currentRange = ensureProviderHistoryRange();
        const nextEnd = Math.max(parsedStart, currentRange.endMs);
        setProviderHistoryRange(parsedStart, nextEnd, refreshProvider);
    };

    const handleEndInput = (refreshProvider) => {
        const parsedEnd = parseLocalDatetimeInputValue(endInput.value);
        if (parsedEnd == null) {
            updateProviderRangeControls();
            return;
        }
        const currentRange = ensureProviderHistoryRange();
        const nextStart = Math.min(parsedEnd, currentRange.startMs);
        setProviderHistoryRange(nextStart, parsedEnd, refreshProvider);
    };

    startInput.addEventListener('input', () => handleStartInput(false));
    startInput.addEventListener('change', () => handleStartInput(true));
    endInput.addEventListener('input', () => handleEndInput(false));
    endInput.addEventListener('change', () => handleEndInput(true));
};

const getEmissionDisplay = (totalValue) => {
    if (totalValue == null || Number.isNaN(totalValue)) {
        return null;
    }

    let value = totalValue;
    let unit = 'gCO2eq';
    if (Math.abs(value) >= 1000) {
        value /= 1000;
        unit = 'kgCO2eq';
    }

    return {
        value,
        unit,
        text: `${numberFormatter.format(value)} ${unit}`
    };
};

const setCarbonSummary = (totalValue, statusMessage) => {
    const valueEl = query('#carbon-summary-value');
    const unitEl = query('#carbon-summary-unit');
    const statusEl = query('#carbon-summary-status');

    if (statusEl) {
        statusEl.textContent = statusMessage || '';
    }

    const emissionDisplay = getEmissionDisplay(totalValue);
    if (!emissionDisplay) {
        valueEl.textContent = '-';
        unitEl.textContent = 'gCO2eq';
        return;
    }

    valueEl.textContent = numberFormatter.format(emissionDisplay.value);
    unitEl.textContent = emissionDisplay.unit;
};

const getBestRuntimeDefaultStatus = () => {
    if (!simulationState.selectedProvider || !simulationState.selectedMetric) {
        return 'Select a provider and metric.';
    }
    if (!simulationState.providerHistory) {
        return 'Loading carbon intensity data.';
    }
    return 'Click to find the lowest CO2eq runtime.';
};

const setBestRuntimeSummary = (totalValue, startMs, statusMessage) => {
    const valueEl = query('#best-runtime-value');
    const unitEl = query('#best-runtime-unit');
    const timeEl = query('#best-runtime-time');
    const statusEl = query('#best-runtime-status');

    if (statusEl) {
        statusEl.textContent = statusMessage || '';
    }

    const emissionDisplay = getEmissionDisplay(totalValue);
    if (!emissionDisplay) {
        valueEl.textContent = '-';
        unitEl.textContent = 'gCO2eq';
    } else {
        valueEl.textContent = numberFormatter.format(emissionDisplay.value);
        unitEl.textContent = emissionDisplay.unit;
    }

    if (startMs == null || Number.isNaN(startMs)) {
        timeEl.textContent = 'Start time: -';
    } else {
        timeEl.textContent = `Start time: ${new Date(startMs).toLocaleString()}`;
    }
};

const resetBestRuntimeSummary = (statusMessage) => {
    simulationState.bestRuntime = null;
    setBestRuntimeSummary(null, null, statusMessage || getBestRuntimeDefaultStatus());
};

const setBestRuntimeButtonDisabled = (disabled) => {
    setButtonDisabledState(query('#find-best-runtime'), disabled);
};

const setBestRuntimeSearching = (loading) => {
    setButtonLoadingState(query('#find-best-runtime'), loading);
};

const setBestProviderButtonDisabled = (disabled) => {
    setButtonDisabledState(query('#find-best-provider'), disabled);
};

const setBestProviderSearching = (loading) => {
    setButtonLoadingState(query('#find-best-provider'), loading);
};

const updateBestProviderAvailability = () => {
    const ready = Boolean(simulationState.selectedMetric && simulationState.providers.length > 0);
    setBestProviderButtonDisabled(!ready || simulationState.bestProviderSearching);
};

const updateBestRuntimeAvailability = () => {
    const ready = Boolean(simulationState.selectedProvider && simulationState.selectedMetric && simulationState.providerHistory);
    setBestRuntimeButtonDisabled(!ready || simulationState.bestRuntimeSearching);
    updateBestProviderAvailability();
    if (simulationState.bestRuntimeSearching) return;
    if (!simulationState.bestRuntime) {
        setBestRuntimeSummary(null, null, getBestRuntimeDefaultStatus());
    }
};

const calculateEmissionTotal = (emissionSeriesData) => emissionSeriesData
    .reduce((sum, point) => sum + (Array.isArray(point) ? point[1] : 0), 0);

const formatEmissionValue = (totalValue) => {
    const emissionDisplay = getEmissionDisplay(totalValue);
    return emissionDisplay ? emissionDisplay.text : '-';
};

const formatMiniChartTime = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
};


const buildMiniLineOptions = (seriesData, unit, lineColor) => ({

    tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line' },
        formatter: (params) => {
            if (!params || params.length === 0) return '';
            const point = params[0];
            const rawValue = Array.isArray(point.value) ? point.value[1] : point.value;
            const pointTime = Array.isArray(point.value) ? point.value[0] : point.axisValue;
            const labelUnit = unit ? ` ${unit}` : '';
            const timestamp = new Date(pointTime);
            const dateTimeLabel = Number.isNaN(timestamp.getTime()) ? '' : dateToYMD(timestamp, false, true);
            return dateTimeLabel
                ? `Value: ${numberFormatter.format(rawValue)}${labelUnit}<br>Time: ${dateTimeLabel}`
                : `${numberFormatter.format(rawValue)}${labelUnit}`;
        }
    },
    grid: {
        left: 6,
        right: 6,
        top: 6,
        bottom: 22
    },
    xAxis: {
        type: 'time',
        show: true,
        axisLine: { show: true },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: {
            show: true,
            formatter: (value) => formatMiniChartTime(value)
        }
    },
    yAxis: {
        type: 'value',
        show: false,
        min: (value) => (value.min >= 0 ? 0 : value.min)
    },
    series: [{
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: lineColor, width: 2 },
        areaStyle: {
            color: lineColor,
            opacity: 0.3,
            origin: 'start'
        },
        data: seriesData
    }],
    animation: false
});

const renderMiniChart = (chartKey, selector, options) => {
    const container = query(selector);
    if (simulationState[chartKey]) {
        simulationState[chartKey].dispose();
        simulationState[chartKey] = null;
    }
    container.innerHTML = '';
    simulationState[chartKey] = echarts.init(container);
    simulationState[chartKey].setOption(options);
};

const getRunTimes = (runData, measurements = []) => {
    let startMs = null;
    let endMs = null;

    if (runData?.start_measurement != null) {
        startMs = Math.round(runData.start_measurement / 1000);
    }
    if (runData?.end_measurement != null) {
        endMs = Math.round(runData.end_measurement / 1000);
    }

    if ((startMs == null || endMs == null) && Array.isArray(measurements) && measurements.length > 0) {
        const measurementTimes = measurements
            .map((entry) => entry?.[1])
            .filter((value) => Number.isFinite(value))
            .map((value) => value / 1000);
        if (measurementTimes.length > 0) {
            const measuredStartMs = Math.min(...measurementTimes);
            const measuredEndMs = Math.max(...measurementTimes);
            if (startMs == null) startMs = Math.round(measuredStartMs);
            if (endMs == null) endMs = Math.round(measuredEndMs);
        }
    }

    if (startMs == null || endMs == null) {
        return null;
    }

    return {
        startMs,
        endMs,
        startIso: dateToYMD(new Date(startMs), false, true),
        endIso: dateToYMD(new Date(endMs), false, true)
    };
};

const renderRunDetails = (runData, runTimes) => {
    setTextContent('#run-id', runData?.id ?? '-');
    setTextContent('#run-start', runTimes?.startIso ?? '-');
    setTextContent('#run-end', runTimes?.endIso ?? '-');
};

const fetchRunData = async (runId) => {
    const run = await makeAPICall(`/v2/run/${runId}`);
    return run?.data;
};

const fetchMeasurements = async (runId) => {
    try {
        const measurements = await makeAPICall(`/v1/measurements/single/${runId}`);
        return measurements?.data || [];
    } catch (err) {
        if (err instanceof APIEmptyResponse204) {
            return [];
        }
        throw err;
    }
};

const getMeasurementMetrics = (measurements) => {
    const metrics = [];
    if (!Array.isArray(measurements)) return metrics;
    measurements.forEach((entry) => {
        const metric = entry?.[2];
        if (typeof metric !== 'string') return;
        if (!metrics.includes(metric)) metrics.push(metric);
    });
    return metrics;
};

const buildEnergyMetricOptions = (measurements) => {
    const metrics = getMeasurementMetrics(measurements);

    if (metrics.length === 0){
        return [];
    }

    const psuMetrics = metrics.filter((metric) => metric.startsWith('psu_energy_'));
    if (psuMetrics.length > 0) {
        return psuMetrics;
    }

    return metrics.filter((metric) => metric.includes('_energy_'));
};

const getDefaultMetric = (metrics) => {
    if (!Array.isArray(metrics) || metrics.length === 0) return null;
    const preferredMetric = 'psu_energy_ac_mcp_machine';
    return metrics.includes(preferredMetric) ? preferredMetric : metrics[0];
};

const buildEnergyData = (measurements, metric) => {
    if (!Array.isArray(measurements) || measurements.length === 0) return null;
    if (!metric) return null;

    const series = {};
    let unit = null;

    measurements.forEach((entry) => {
        if (entry?.[2] !== metric) return;
        const detail = entry?.[0];
        const timeMs = entry[1] / 1000;
        let value = entry[3];
        let valueUnit = entry[4];
        [value, valueUnit] = convertValue(value, valueUnit);
        if (!unit) unit = valueUnit;
        if (!series[detail]) {
            series[detail] = { name: detail, data: [] };
        }
        series[detail].data.push([timeMs, value]);
    });

    Object.values(series).forEach((entry) => entry.data.sort((a, b) => a[0] - b[0]));

    const seriesKeys = Object.keys(series);
    if (seriesKeys.length === 0) return null;

    const primarySeries = series['[MACHINE]'] || series[seriesKeys[0]];

    return {
        metric,
        unit,
        series,
        primarySeries
    };
};

const buildEnergySeriesRaw = (measurements, metric) => {
    if (!Array.isArray(measurements) || measurements.length === 0) return null;
    if (!metric) return null;

    const series = {};

    measurements.forEach((entry) => {
        if (entry?.[2] !== metric) return;
        const detail = entry?.[0] || '[MACHINE]';
        const timeMs = entry[1] / 1000;
        const value = entry[3];
        const unit = entry[4];
        if (!series[detail]) {
            series[detail] = { name: detail, data: [] };
        }
        series[detail].data.push({ timeMs, value, unit });
    });

    Object.values(series).forEach((entry) => entry.data.sort((a, b) => a.timeMs - b.timeMs));

    const seriesKeys = Object.keys(series);
    if (seriesKeys.length === 0) return null;

    const primarySeries = series['[MACHINE]'] || series[seriesKeys[0]];

    return {
        metric,
        series,
        primarySeries
    };
};

const normalizeEnergyUnit = (unit, metric) => {
    if (unit === '*' && typeof metric === 'string' && metric.includes('energy')) {
        return 'uJ';
    }
    return unit;
};

const convertEnergyToKwh = (value, unit, metric) => {
    if (value == null || !unit) return null;
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) return null;

    const resolvedUnit = normalizeEnergyUnit(unit, metric);
    const baseUnit = resolvedUnit.split('/', 2)[0];
    switch (baseUnit) {
        case 'uJ':
            return numericValue / 3_600_000_000_000;
        case 'mJ':
            return numericValue / 3_600_000_000;
        case 'J':
            return numericValue / 3_600_000;
        case 'kWh':
            return numericValue;
        case 'Wh':
            return numericValue / 1_000;
        case 'mWh':
            return numericValue / 1_000_000;
        case 'uWh':
            return numericValue / 1_000_000_000;
        default:
            return null;
    }
};

const buildEmissionSeries = (energySeries, carbonHistory, metric, timeOffsetMs = 0) => {
    if (!energySeries || !Array.isArray(energySeries.data)) {
        return { data: [], debug: { reason: 'invalid_energy_series' } };
    }

    const carbonSeries = carbonHistory
        .filter((entry) => entry?.time && entry?.carbon_intensity != null)
        .map((entry) => ({
            time: Date.parse(entry.time),
            value: entry.carbon_intensity
        }))
        .filter((entry) => !Number.isNaN(entry.time))
        .sort((a, b) => a.time - b.time);

    if (carbonSeries.length === 0) return { data: [], debug: { reason: 'no_carbon_series' } };

    let index = 0;
    let current = null;
    const result = [];
    const debug = {
        metric,
        timeOffsetMs,
        energyPoints: 0,
        energyPointsWithKwh: 0,
        skippedNoKwh: 0,
        skippedNoCarbon: 0,
        matchedPoints: 0,
        energyUnitSample: energySeries.data[0]?.unit ?? null,
        energyTimeStart: energySeries.data[0]?.timeMs ?? null,
        energyTimeEnd: energySeries.data[energySeries.data.length - 1]?.timeMs ?? null,
        carbonPoints: carbonSeries.length,
        carbonTimeStart: carbonSeries[0]?.time ?? null,
        carbonTimeEnd: carbonSeries[carbonSeries.length - 1]?.time ?? null
    };

    energySeries.data.forEach((point) => {
        const shiftedTime = point.timeMs + timeOffsetMs;
        const energyKwh = convertEnergyToKwh(point.value, point.unit, metric);
        debug.energyPoints += 1;
        if (energyKwh == null) {
            debug.skippedNoKwh += 1;
            return;
        }
        debug.energyPointsWithKwh += 1;

        while (index < carbonSeries.length && carbonSeries[index].time <= shiftedTime) {
            current = carbonSeries[index];
            index += 1;
        }

        if (current) {
            result.push([shiftedTime, energyKwh * current.value]);
            debug.matchedPoints += 1;
        } else {
            debug.skippedNoCarbon += 1;
        }
    });

    return { data: result, debug };
};

const findRuntimeExtremesForHistory = (energySeriesRaw, providerHistory) => {
    const energySeries = energySeriesRaw?.primarySeries;
    if (!energySeries || !Array.isArray(energySeries.data) || energySeries.data.length === 0) {
        return null;
    }

    const carbonSeries = buildCarbonIntensitySeries(providerHistory);
    if (carbonSeries.length === 0) return null;

    const energyStart = energySeries.data[0].timeMs;
    const energyEnd = energySeries.data[energySeries.data.length - 1].timeMs;
    const carbonStart = carbonSeries[0][0];
    const carbonEnd = carbonSeries[carbonSeries.length - 1][0];

    let searchStart = carbonStart - energyStart;
    let searchEnd = carbonEnd - energyEnd;
    let mode = 'full';

    if (searchStart > searchEnd) {
        mode = 'partial';
        searchStart = carbonStart - energyEnd;
        searchEnd = carbonEnd - energyStart;
    }

    if (searchStart > searchEnd) return null;

    const searchWindowMs = searchEnd - searchStart;
    const step = getBestRuntimeStepMs(searchWindowMs);
    const alignedStart = Math.ceil(searchStart / step) * step;
    const alignedEnd = Math.floor(searchEnd / step) * step;

    let best = null;
    let worst = null;
    for (let offset = alignedStart; offset <= alignedEnd; offset += step) {
        const emissionResult = buildEmissionSeries(
            energySeries,
            providerHistory,
            energySeriesRaw?.metric,
            offset
        );
        const emissionSeriesData = emissionResult?.data || [];
        if (emissionSeriesData.length === 0) continue;

        const total = calculateEmissionTotal(emissionSeriesData);
        const coverage = emissionSeriesData.length / energySeries.data.length;
        const candidate = {
            offsetMs: offset,
            total,
            coverage,
            mode,
            startMs: energyStart + offset
        };

        if (!best || coverage > best.coverage || (coverage === best.coverage && total < best.total)) {
            best = candidate;
        }

        if (!worst || coverage > worst.coverage || (coverage === worst.coverage && total > worst.total)) {
            worst = candidate;
        }
    }

    if (!best || !worst) return null;
    return { best, worst };
};

const findBestRuntimeCandidate = () => {
    const metric = simulationState.selectedMetric;
    const providerHistory = simulationState.providerHistory;
    if (!metric || !providerHistory) return null;

    const energySeriesRaw = buildEnergySeriesRaw(simulationState.measurements, metric);
    if (!energySeriesRaw) return null;

    const runtimeExtremes = findRuntimeExtremesForHistory(energySeriesRaw, providerHistory);
    return runtimeExtremes?.best || null;
};

const findBestRuntime = async () => {
    if (simulationState.bestRuntimeSearching) return;

    simulationState.bestRuntimeSearching = true;
    setBestRuntimeSearching(true);
    updateBestRuntimeAvailability();
    setBestRuntimeSummary(null, null, 'Searching for the lowest CO2eq runtime...');

    await new Promise((resolve) => setTimeout(resolve, 80));

    const bestRuntime = findBestRuntimeCandidate();
    simulationState.bestRuntimeSearching = false;
    setBestRuntimeSearching(false);
    updateBestRuntimeAvailability();

    if (!bestRuntime) {
        setBestRuntimeSummary(null, null, 'No suitable runtime found for this data.');
        return;
    }

    simulationState.bestRuntime = bestRuntime;
    simulationState.metricTimeOffsetMs = bestRuntime.offsetMs;

    updateSimulationChart();
    updateShiftButtonsAvailability();

    const coveragePct = Math.round(bestRuntime.coverage * 100);
    const status = bestRuntime.mode === 'partial' || bestRuntime.coverage < 0.99
        ? `Best available (${coveragePct}% coverage).`
        : 'Best runtime found.';
    setBestRuntimeSummary(bestRuntime.total, bestRuntime.startMs, status);
};

const renderSimulationChart = (
    providerSeriesData,
    emissionSeriesData,
    providerLabel,
    emissionLabel,
    providerName
) => {
    let chartInstance = simulationState.chart;
    let element = chartInstance?.getDom?.() || null;
    if (!element || !document.body.contains(element)) {
        const title = 'Carbon intensity and estimated emissions';
        element = createChartContainer('#chart-container', title);
        const card = element.closest('.statistics-chart-card');
        card.classList.add('full-width');
        card.classList.add('simulation-main-chart-card');
        chartInstance = echarts.init(element);
        simulationState.chart = chartInstance;
    }

    const options = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'line' },
            formatter: (params) => {
                if (!params || params.length === 0) return '';
                const providerPoint = params.find((item) => item.seriesName === providerLabel) || params[0];
                const carbonValueRaw = Array.isArray(providerPoint.value)
                    ? providerPoint.value[1]
                    : providerPoint.value;
                const carbonValue = Number.isFinite(carbonValueRaw)
                    ? numberFormatter.format(carbonValueRaw)
                    : '-';
                const pointTime = Array.isArray(providerPoint.value)
                    ? providerPoint.value[0]
                    : providerPoint.axisValue;
                const dateTime = dateToYMD(new Date(pointTime), false, true) || '-';
                const provider = providerName || simulationState.selectedProvider?.provider || '-';
                return `Carbon Intensity: ${carbonValue} gCO2<br>Provider: ${escapeString(provider)}<br>Date/Time: ${dateTime}`;
            }
        },
        grid: {
            left: 70,
            right: 120,
            top: 46,
            bottom: 44,
            containLabel: true
        },
        xAxis: {
            type: 'time',
            name: 'Time',
            nameLocation: 'middle',
            nameGap: 40,
            axisLabel: {
                margin: 12,
                hideOverlap: true,
                formatter: '{dd}-{MM}-{yy}\n{HH}:{mm}'
            },
            splitLine: { show: false }
        },
        yAxis: [
            {
                type: 'value',
                name: 'gCO2eq/kWh',
                position: 'left',
                splitLine: { show: true },
                min: (value) => (value.min >= 0 ? 0 : value.min)
            },
            {
                type: 'value',
                name: 'gCO2eq',
                position: 'right',
                splitLine: { show: false },
                min: (value) => (value.min >= 0 ? 0 : value.min)
            }
        ],
        series: [
            {
                name: providerLabel,
                type: 'line',
                smooth: true,
                symbol: 'none',
                lineStyle: { color: SIMULATION_CHART_COLORS.provider, width: 2 },
                areaStyle: {
                    color: SIMULATION_CHART_COLORS.provider,
                    opacity: 0.22,
                    origin: 'start'
                },
                data: providerSeriesData,
                yAxisIndex: 0
            },
            {
                name: emissionLabel,
                type: 'line',
                smooth: true,
                symbol: 'none',
                lineStyle: {
                    color: SIMULATION_CHART_COLORS.emission,
                    type: 'dashed',
                    width: 2
                },
                areaStyle: {
                    color: SIMULATION_CHART_COLORS.emission,
                    opacity: 0.18,
                    origin: 'start'
                },
                data: emissionSeriesData,
                yAxisIndex: 1
            }
        ],
        legend: {
            data: [providerLabel, emissionLabel],
            top: 4,
            left: 0,
            right: 190,
            type: 'scroll'
        },
        animation: false,
        toolbox: {
            itemSize: 25,
            top: 52,
            right: 12,
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {}
            }
        }
    };

    chartInstance.setOption(options, true);

    if (!simulationState.resizeHandlerBound) {
        window.addEventListener('resize', () => {
            if (simulationState.chart) {
                simulationState.chart.resize();
            }
            if (simulationState.providerMiniChart) {
                simulationState.providerMiniChart.resize();
            }
            if (simulationState.metricMiniChart) {
                simulationState.metricMiniChart.resize();
            }
        });
        simulationState.resizeHandlerBound = true;
    }
};

const setChartLoadFailureVisible = (visible, headerText, detailText) => {
    const message = query('#message-chart-load-failure');
    if (headerText) {
        setTextContent('#message-chart-load-failure-header', headerText);
    }
    if (detailText) {
        setTextContent('#message-chart-load-failure-text', detailText);
    }
    message.classList.toggle('hidden', !visible);
};

const setAlignButtonVisible = (visible) => {
    const button = query('#align-metric');
    button.classList.toggle('hidden', !visible);
};

const alignMetricToProviderMidpoint = () => {
    const metric = simulationState.selectedMetric;
    const providerHistory = simulationState.providerHistory;
    if (!metric || !providerHistory) return;

    const energySeriesRaw = buildEnergySeriesRaw(simulationState.measurements, metric);
    const energySeries = energySeriesRaw?.primarySeries;
    if (!energySeries || !Array.isArray(energySeries.data) || energySeries.data.length === 0) {
        return;
    }

    const carbonSeries = buildCarbonIntensitySeries(providerHistory);
    if (carbonSeries.length === 0) return;

    const energyStart = energySeries.data[0].timeMs;
    const energyEnd = energySeries.data[energySeries.data.length - 1].timeMs;
    const carbonStart = carbonSeries[0][0];
    const carbonEnd = carbonSeries[carbonSeries.length - 1][0];

    const energyMid = (energyStart + energyEnd) / 2;
    const carbonMid = (carbonStart + carbonEnd) / 2;
    const step = METRIC_SHIFT_STEP_MS;
    const alignedOffset = Math.round((carbonMid - energyMid) / step) * step;

    simulationState.metricTimeOffsetMs = alignedOffset;
    resetBestRuntimeSummary();
    updateSimulationChart();
    updateShiftButtonsAvailability();
};

const resetSimulationChart = () => {
    if (simulationState.chart) {
        simulationState.chart.dispose();
        simulationState.chart = null;
    }
    const container = query('#chart-container');
    if (container) {
        container.innerHTML = '';
    }
};

const updateMetricMiniChart = (metric, energyData) => {
    if (!metric) {
        resetMiniChart('metricMiniChart', '#metric-mini-chart', 'Select a metric to preview.');
        return;
    }

    const resolvedEnergyData = energyData || buildEnergyData(simulationState.measurements, metric);
    const series = resolvedEnergyData?.primarySeries?.data;
    if (!resolvedEnergyData || !Array.isArray(series) || series.length === 0) {
        resetMiniChart('metricMiniChart', '#metric-mini-chart', 'No metric data available.');
        return;
    }

    const options = buildMiniLineOptions(series, resolvedEnergyData.unit, MINI_CHART_COLORS.metric);
    renderMiniChart('metricMiniChart', '#metric-mini-chart', options);
};

const updateSimulationChart = () => {
    const selection = simulationState.selectedProvider;
    const metric = simulationState.selectedMetric;
    const providerHistory = simulationState.providerHistory;

    logSimulationDebug('updating simulation chart', { selection, metric, providerHistory });

    if (simulationState.availableMetrics.length === 0) {
        resetSimulationChart();
        setCarbonSummary(null, 'No metric data available.');
        setAlignButtonVisible(false);
        setChartLoadFailureVisible(true, 'No metric data', NO_METRIC_DATA_DETAIL);
        return;
    }

    if (!selection) {
        resetSimulationChart();
        logSimulationDebug('missing provider selection');
        setCarbonSummary(null, 'Select a provider to compute emissions.');
        setAlignButtonVisible(false);
        setChartLoadFailureVisible(true, 'Select a provider', 'Pick a provider to load the chart.');
        return;
    }
    if (!providerHistory) {
        resetSimulationChart();
        logSimulationDebug('provider history unavailable', { provider: selection });
        setCarbonSummary(null, 'Loading carbon intensity data.');
        setAlignButtonVisible(false);
        setChartLoadFailureVisible(true, 'Loading carbon intensity', 'Carbon intensity data is not available for the time of the run. Please select another provider or adjust the provider history time range.');
        return;
    }
    if (!metric) {
        resetSimulationChart();
        logSimulationDebug('missing metric selection');
        setCarbonSummary(null, 'Select a metric to compute emissions.');
        setAlignButtonVisible(false);
        setChartLoadFailureVisible(true, 'Select a metric', 'Pick a metric to load the chart.');
        return;
    }

    const providerSeriesData = buildCarbonIntensitySeries(providerHistory);
    if (providerSeriesData.length === 0) {
        resetSimulationChart();
        logSimulationDebug('provider series empty', { providerHistoryCount: providerHistory.length });
        setCarbonSummary(null, 'No carbon intensity data available.');
        setAlignButtonVisible(false);
        setChartLoadFailureVisible(true, 'No carbon intensity data', 'No usable carbon intensity data returned.');
        return;
    }

    const energySeriesRaw = buildEnergySeriesRaw(simulationState.measurements, metric);
    const energySeries = energySeriesRaw?.primarySeries;
    if (!energySeries || !Array.isArray(energySeries.data) || energySeries.data.length === 0) {
        resetSimulationChart();
        logSimulationDebug('energy series empty', { metric });
        setCarbonSummary(null, 'No metric data available.');
        setAlignButtonVisible(false);
        setChartLoadFailureVisible(true, 'No metric data', 'Energy data could not be loaded for this run.');
        return;
    }

    const emissionResult = buildEmissionSeries(
        energySeries,
        providerHistory,
        energySeriesRaw?.metric,
        simulationState.metricTimeOffsetMs
    );
    const emissionSeriesData = emissionResult?.data || [];
    if (emissionSeriesData.length === 0) {
        logSimulationDebug('emission series empty', {
            providerHistoryCount: providerHistory.length,
            metric,
            offsetMs: simulationState.metricTimeOffsetMs,
            debug: emissionResult?.debug ?? null
        });
        const providerLabel = `Carbon intensity (${selection.provider} ${selection.region})`;
        const metricLabel = getPretty(metric, 'clean_name');
        const emissionLabel = `Estimated emissions (${metricLabel})`;
        renderSimulationChart(
            providerSeriesData,
            emissionSeriesData,
            providerLabel,
            emissionLabel,
            selection.provider
        );
        setCarbonSummary(null, 'Metric data could not be aligned.');
        setAlignButtonVisible(true);
        setChartLoadFailureVisible(true, 'Missing Energy Metric', 'Can not align carbon data with energy metric.');
        return;
    }

    const providerLabel = `Carbon intensity (${selection.provider} ${selection.region})`;
    const metricLabel = getPretty(metric, 'clean_name');
    const emissionLabel = `Estimated emissions (${metricLabel})`;
    renderSimulationChart(
        providerSeriesData,
        emissionSeriesData,
        providerLabel,
        emissionLabel,
        selection.provider
    );
    setCarbonSummary(calculateEmissionTotal(emissionSeriesData), '');
    setAlignButtonVisible(false);
    setChartLoadFailureVisible(false);
};

const hasEmissionOverlapForCurrentSelection = () => {
    const metric = simulationState.selectedMetric;
    const providerHistory = simulationState.providerHistory;
    if (!metric || !providerHistory) return false;

    const energySeriesRaw = buildEnergySeriesRaw(simulationState.measurements, metric);
    const energySeries = energySeriesRaw?.primarySeries;
    if (!energySeries || !Array.isArray(energySeries.data) || energySeries.data.length === 0) {
        return false;
    }

    const emissionResult = buildEmissionSeries(
        energySeries,
        providerHistory,
        energySeriesRaw?.metric,
        simulationState.metricTimeOffsetMs
    );
    return (emissionResult?.data || []).length > 0;
};

const hasFullCarbonCoverageForCurrentSelection = () => {
    const metric = simulationState.selectedMetric;
    const providerHistory = simulationState.providerHistory;
    if (!metric || !providerHistory) return false;

    const energySeriesRaw = buildEnergySeriesRaw(simulationState.measurements, metric);
    const energySeries = energySeriesRaw?.primarySeries;
    if (!energySeries || !Array.isArray(energySeries.data) || energySeries.data.length === 0) {
        return false;
    }

    const carbonSeries = buildCarbonIntensitySeries(providerHistory);
    if (carbonSeries.length === 0) return false;

    const shiftedStartMs = energySeries.data[0].timeMs + simulationState.metricTimeOffsetMs;
    const shiftedEndMs = energySeries.data[energySeries.data.length - 1].timeMs + simulationState.metricTimeOffsetMs;
    const carbonStartMs = carbonSeries[0][0];
    const carbonEndMs = carbonSeries[carbonSeries.length - 1][0];

    return shiftedStartMs >= carbonStartMs && shiftedEndMs <= carbonEndMs;
};

const shiftMetricTimeByMs = async (deltaMs) => {
    if (simulationState.shiftInProgress) return;

    simulationState.shiftInProgress = true;
    updateShiftButtonsAvailability();

    const previousOffsetMs = simulationState.metricTimeOffsetMs;
    const previousRangeStartMs = simulationState.providerRangeStartMs;
    const previousRangeEndMs = simulationState.providerRangeEndMs;

    try {
        simulationState.metricTimeOffsetMs += deltaMs;
        resetBestRuntimeSummary();

        const shiftedRunStartMs = simulationState.runTimes?.startMs != null
            ? simulationState.runTimes.startMs + simulationState.metricTimeOffsetMs
            : null;
        if (shiftedRunStartMs != null && simulationState.selectedProvider) {
            const nextRange = getProviderHistoryRangeAroundTimeMs(shiftedRunStartMs);
            const refreshed = await setProviderHistoryRange(
                nextRange.startMs,
                nextRange.endMs,
                true,
                { preserveCurrentView: true }
            );

            const hasValidCoverage = refreshed
                && hasEmissionOverlapForCurrentSelection()
                && hasFullCarbonCoverageForCurrentSelection();
            if (!hasValidCoverage) {
                simulationState.metricTimeOffsetMs = previousOffsetMs;
                if (previousRangeStartMs != null && previousRangeEndMs != null) {
                    await setProviderHistoryRange(
                        previousRangeStartMs,
                        previousRangeEndMs,
                        true,
                        { preserveCurrentView: true }
                    );
                } else {
                    updateSimulationChart();
                }
                showNotification(
                    'Reached carbon data boundary',
                    'Cannot shift further because the metric would leave the available carbon data window.'
                );
            }
            return;
        }

        updateSimulationChart();
    } finally {
        simulationState.shiftInProgress = false;
        updateShiftButtonsAvailability();
    }
};

const shiftMetricTime = async (direction) => shiftMetricTimeByMs(direction * METRIC_SHIFT_STEP_MS);

const populateMetrics = (metrics) => {
    const menu = query('#metric-menu');
    menu.innerHTML = '';

    metrics.forEach((metric) => {
        const entry = document.createElement('div');
        entry.className = 'item';
        entry.dataset.value = metric;
        entry.textContent = metric;
        menu.appendChild(entry);
    });

    $('#metric-dropdown')
        .dropdown({
            clearable: false,
            onChange: (value) => {
                if (!value || value === simulationState.selectedMetric) return;
                simulationState.selectedMetric = value;
                simulationState.metricTimeOffsetMs = 0;
                resetBestRuntimeSummary();
                updateMetricMiniChart(value);
                updateSimulationChart();
                updateShiftButtonsAvailability();
            }
        });

    const defaultMetric = getDefaultMetric(metrics);
    if (defaultMetric) {
        $('#metric-dropdown').dropdown('set selected', defaultMetric);
    }
    updateBestProviderAvailability();
};

const fetchProviders = async () => {
    if (!ELEPHANT_URL) {
        throw new Error('Elephant Carbon Service is not configured. Re-run install and enable it.');
    }
    const response = await fetch(`${ELEPHANT_URL}/providers`);
    if (!response.ok) {
        throw new Error(`Provider list request failed (${response.status})`);
    }
    const data = await response.json();
    if (!Array.isArray(data)) {
        throw new Error('Provider list response is not an array');
    }
    return data;
};

const populateProviders = (providers) => {
    const menu = query('#provider-menu');
    menu.innerHTML = '';

    simulationState.providers = providers
        .filter((item) => Array.isArray(item) && item.length >= 3)
        .map((item) => ({
            provider: item[0],
            region: item[1],
            value: item[2]
        }));

    simulationState.providers.forEach((providerItem) => {
        const provider = providerItem.provider;
        const region = providerItem.region;
        const entry = document.createElement('div');
        entry.className = 'item';
        entry.dataset.value = providerItem.value;
        entry.dataset.provider = provider;
        entry.dataset.region = region;
        //entry.innerHTML = `<i class="${escapeString(flag)} flag"></i>${escapeString(provider)} (${escapeString(region)})`;
        entry.innerHTML = `${escapeString(provider)} (${escapeString(region)})`;

        menu.appendChild(entry);
    });

    $('#provider-dropdown')
        .dropdown({
            clearable: true,
            onChange: async (value, text, $selectedItem) => {
                if (!$selectedItem || $selectedItem.length === 0) {
                    simulationState.selectedProvider = null;
                    simulationState.metricTimeOffsetMs = 0;
                    resetBestRuntimeSummary();
                    simulationState.providerAutoFallbackActive = false;
                    await updateProviderMiniChart(null);
                    return;
                }
                simulationState.selectedProvider = {
                    provider: $selectedItem.data('provider'),
                    region: $selectedItem.data('region'),
                    value: $selectedItem.data('value')
                };
                simulationState.metricTimeOffsetMs = 0;
                resetBestRuntimeSummary();
                const hasData = await updateProviderMiniChart(simulationState.selectedProvider);

                if (hasData || !simulationState.providerAutoFallbackActive) {
                    simulationState.providerAutoFallbackActive = false;
                    return;
                }

                const currentIndex = simulationState.providers.findIndex((providerItem) =>
                    providerItem.provider === simulationState.selectedProvider.provider
                    && providerItem.region === simulationState.selectedProvider.region
                    && providerItem.value === simulationState.selectedProvider.value
                );
                const nextProvider = currentIndex >= 0 ? simulationState.providers[currentIndex + 1] : null;
                if (nextProvider) {
                    $('#provider-dropdown').dropdown('set selected', nextProvider.value);
                    return;
                }

                simulationState.providerAutoFallbackActive = false;
            }
        });

    if (simulationState.providers.length > 0) {
        simulationState.providerAutoFallbackActive = true;
        const firstProvider = simulationState.providers[0];
        $('#provider-dropdown').dropdown('set selected', firstProvider.value);

        // Fallback for dropdown implementations that do not fire onChange on programmatic selection.
        if (!simulationState.selectedProvider) {
            (async () => {
                for (const providerItem of simulationState.providers) {
                    simulationState.selectedProvider = providerItem;
                    simulationState.metricTimeOffsetMs = 0;
                    resetBestRuntimeSummary();
                    const hasData = await updateProviderMiniChart(simulationState.selectedProvider);
                    if (hasData) {
                        simulationState.providerAutoFallbackActive = false;
                        $('#provider-dropdown').dropdown('set selected', providerItem.value);
                        return;
                    }
                }
                simulationState.providerAutoFallbackActive = false;
            })();
        }
    }

    updateBestProviderAvailability();
};

const buildCarbonIntensitySeries = (carbonHistory) => {
    if (!Array.isArray(carbonHistory)) return [];

    return carbonHistory
        .filter((entry) => entry?.time && entry?.carbon_intensity != null)
        .map((entry) => [Date.parse(entry.time), entry.carbon_intensity])
        .filter((entry) => !Number.isNaN(entry[0]))
        .sort((a, b) => a[0] - b[0]);
};

const getProviderHistoryRange = () => {
    const { startMs, endMs } = ensureProviderHistoryRange();
    const startTime = new Date(startMs).toISOString();
    const endTime = new Date(endMs).toISOString();
    return { startTime, endTime };
};

const fetchProviderCarbonHistory = async (selection, startTime, endTime) => {
    if (!ELEPHANT_URL) {
        throw new Error('Elephant Carbon Service is not configured. Re-run install and enable it.');
    }
    const params = new URLSearchParams({
        region: selection.region,
        startTime,
        endTime,
        provider: selection.value
    });

    const response = await fetch(`${ELEPHANT_URL}/carbon-intensity/history?${params.toString()}`);
    if (!response.ok) {
        throw new Error(`Carbon intensity request failed (${response.status})`);
    }

    const data = await response.json();
    return Array.isArray(data) ? data : [];
};

const openBestProviderDialog = () => {
    const dialog = query('#best-provider-dialog');
    if (typeof dialog.showModal === 'function') {
        if (!dialog.open) {
            dialog.showModal();
        }
        return;
    }
    dialog.setAttribute('open', 'open');
};

const closeBestProviderDialog = () => {
    const dialog = query('#best-provider-dialog');
    if (typeof dialog.close === 'function') {
        if (dialog.open) {
            dialog.close();
        }
        return;
    }
    dialog.removeAttribute('open');
};

const createBestProviderRow = (provider, index) => {
    const row = document.createElement('tr');
    row.dataset.providerIndex = String(index);
    row.innerHTML = `
        <td>${escapeString(provider.provider)} (${escapeString(provider.region)})</td>
        <td data-col="best-time">-</td>
        <td data-col="best-value">-</td>
        <td data-col="worst-value">-</td>
        <td data-col="status"><span class="provider-scan-status provider-scan-status-queued">Queued</span></td>
    `;
    return row;
};

const setBestProviderRowStatus = (row, status, message) => {
    if (!row) return;
    const statusCell = row.querySelector('[data-col="status"]');
    if (!statusCell) return;

    if (status === 'loading') {
        statusCell.innerHTML = '<span class="provider-scan-status provider-scan-status-loading"><span class="provider-scan-spinner"></span>Calculating</span>';
        return;
    }
    if (status === 'error') {
        statusCell.innerHTML = `<span class="provider-scan-status provider-scan-status-error">${escapeString(message || 'Failed')}</span>`;
        return;
    }
    statusCell.innerHTML = `<span class="provider-scan-status provider-scan-status-done">${escapeString(message || 'Done')}</span>`;
};

const renderBestProviderRows = (providers) => {
    const resultsBody = query('#best-provider-results');
    if (!resultsBody) return [];
    resultsBody.innerHTML = '';
    const rows = providers.map((provider, index) => {
        const row = createBestProviderRow(provider, index);
        resultsBody.appendChild(row);
        return row;
    });
    return rows;
};

const findBestProvider = async () => {
    if (simulationState.bestProviderSearching) return;
    if (!simulationState.selectedMetric) {
        showNotification('Select metric first', 'Please select a metric before scanning providers.');
        return;
    }
    if (!Array.isArray(simulationState.providers) || simulationState.providers.length === 0) {
        showNotification('No providers', 'Provider list is not available.');
        return;
    }

    const energySeriesRaw = buildEnergySeriesRaw(simulationState.measurements, simulationState.selectedMetric);
    if (!energySeriesRaw?.primarySeries?.data?.length) {
        showNotification('No metric data', 'Energy data could not be loaded for this run.');
        return;
    }

    simulationState.bestProviderSearching = true;
    setBestProviderSearching(true);
    updateBestProviderAvailability();

    const providers = simulationState.providers;
    const rows = renderBestProviderRows(providers);
    openBestProviderDialog();

    const { startTime, endTime } = getProviderHistoryRange();

    for (let index = 0; index < providers.length; index += 1) {
        const provider = providers[index];
        const row = rows[index];
        setBestProviderRowStatus(row, 'loading');

        try {
            const history = await fetchProviderCarbonHistory(provider, startTime, endTime);
            const runtimeExtremes = findRuntimeExtremesForHistory(energySeriesRaw, history);

            if (!runtimeExtremes?.best || !runtimeExtremes?.worst) {
                setBestProviderRowStatus(row, 'error', 'No overlapping data');
                continue;
            }

            const bestTimeCell = row.querySelector('[data-col="best-time"]');
            const bestValueCell = row.querySelector('[data-col="best-value"]');
            const worstValueCell = row.querySelector('[data-col="worst-value"]');

            if (bestTimeCell) {
                bestTimeCell.textContent = new Date(runtimeExtremes.best.startMs).toLocaleString();
            }
            if (bestValueCell) {
                bestValueCell.textContent = formatEmissionValue(runtimeExtremes.best.total);
            }
            if (worstValueCell) {
                worstValueCell.textContent = formatEmissionValue(runtimeExtremes.worst.total);
            }

            const coveragePct = Math.round(runtimeExtremes.best.coverage * 100);
            const isPartial = runtimeExtremes.best.mode === 'partial' || runtimeExtremes.best.coverage < 0.99;
            setBestProviderRowStatus(row, 'done', isPartial ? `Done (${coveragePct}% coverage)` : 'Done');
        } catch (err) {
            setBestProviderRowStatus(row, 'error', 'Fetch failed');
        }
    }

    simulationState.bestProviderSearching = false;
    setBestProviderSearching(false);
    updateBestProviderAvailability();
};

const updateProviderMiniChart = async (selection, options = {}) => {
    const preserveCurrentView = options?.preserveCurrentView === true;

    if (!selection) {
        simulationState.providerMiniRequestId += 1;
        simulationState.providerHistory = null;
        resetMiniChart('providerMiniChart', '#provider-mini-chart', 'Select a provider to preview.');
        updateSimulationChart();
        updateShiftButtonsAvailability();
        return false;
    }

    const requestId = simulationState.providerMiniRequestId + 1;
    simulationState.providerMiniRequestId = requestId;
    if (!preserveCurrentView) {
        simulationState.providerHistory = null;
        setMiniChartPlaceholder('#provider-mini-chart', 'Loading carbon intensity...');
        updateSimulationChart();
    }
    updateShiftButtonsAvailability();

    const { startTime, endTime } = getProviderHistoryRange();

    try {
        const data = await fetchProviderCarbonHistory(selection, startTime, endTime);
        if (requestId !== simulationState.providerMiniRequestId) return false;

        const nextHistory = Array.isArray(data) ? data : null;
        const seriesData = buildCarbonIntensitySeries(nextHistory);
        if (seriesData.length === 0) {
            if (!preserveCurrentView) {
                simulationState.providerHistory = null;
                resetMiniChart('providerMiniChart', '#provider-mini-chart', 'No carbon data available.');
                updateSimulationChart();
            }
            updateShiftButtonsAvailability();
            return false;
        }

        simulationState.providerHistory = nextHistory;
        const options = buildMiniLineOptions(seriesData, null, MINI_CHART_COLORS.provider);
        renderMiniChart('providerMiniChart', '#provider-mini-chart', options);
        updateSimulationChart();
        updateShiftButtonsAvailability();
        return true;
    } catch (err) {
        if (requestId !== simulationState.providerMiniRequestId) return false;
        if (!preserveCurrentView) {
            simulationState.providerHistory = null;
            resetMiniChart('providerMiniChart', '#provider-mini-chart', 'Could not load carbon data.');
            updateSimulationChart();
        }
        updateShiftButtonsAvailability();
        return false;
    }
};

$(document).ready(() => {
    (async () => {
        setMiniChartPlaceholder('#provider-mini-chart', 'Select a provider to preview.');
        setMiniChartPlaceholder('#metric-mini-chart', 'Select a metric to preview.');
        updateProviderRangeControls();
        bindProviderRangeControls();

        const urlParams = getURLParams();
        const runId = urlParams['id'];
        if (!runId || runId === 'null') {
            showNotification('No run id', 'ID parameter in URL is empty or missing.');
            setProviderDropdownLoading(false);
            setMetricDropdownLoading(false);
            return;
        }

        simulationState.runId = runId;

        try {
            const [runData, measurements] = await Promise.all([
                fetchRunData(runId),
                fetchMeasurements(runId)
            ]);

            simulationState.runTimes = getRunTimes(runData, measurements);
            renderRunDetails(runData, simulationState.runTimes);
            if (simulationState.runTimes?.endMs != null) {
                const defaultRange = getDefaultProviderHistoryRangeMs();
                setProviderHistoryRange(defaultRange.startMs, defaultRange.endMs, false);
            }

            simulationState.measurements = measurements;
            const metricOptions = buildEnergyMetricOptions(measurements);
            simulationState.availableMetrics = metricOptions;

            if (metricOptions.length === 0) {
                setChartLoadFailureVisible(true, 'No metric data', NO_METRIC_DATA_DETAIL);
                resetMiniChart('metricMiniChart', '#metric-mini-chart', 'No metric data available.');
            } else {
                populateMetrics(metricOptions);
            }
        } catch (err) {
            showNotification('Could not load run data', err);
        } finally {
            setMetricDropdownLoading(false);
        }

        try {
            const providers = await fetchProviders();
            populateProviders(providers);
        } catch (err) {
            showNotification('Could not load providers', err);
        } finally {
            setProviderDropdownLoading(false);
        }

        bindClick('#shift-left', () => shiftMetricTime(-1));
        bindClick('#shift-right', () => shiftMetricTime(1));
        bindClick('#shift-left-hour', () => shiftMetricTimeByMs(-SHIFT_ONE_HOUR_MS));
        bindClick('#shift-right-hour', () => shiftMetricTimeByMs(SHIFT_ONE_HOUR_MS));
        bindClick('#shift-left-day', () => shiftMetricTimeByMs(-SHIFT_ONE_DAY_MS));
        bindClick('#shift-right-day', () => shiftMetricTimeByMs(SHIFT_ONE_DAY_MS));
        bindClick('#shift-left-30d', () => shiftMetricTimeByMs(-SHIFT_THIRTY_DAYS_MS));
        bindClick('#shift-right-30d', () => shiftMetricTimeByMs(SHIFT_THIRTY_DAYS_MS));
        bindClick('#align-metric', () => alignMetricToProviderMidpoint());
        bindClick('#find-best-runtime', () => findBestRuntime());
        bindClick('#find-best-provider', () => findBestProvider());
        bindClick('#best-provider-dialog-close', () => closeBestProviderDialog());
        setShiftButtonsDisabled(true);
        setBestRuntimeButtonDisabled(true);
        setBestProviderButtonDisabled(true);
    })();
});
