const AVAILABLE_YEARS = [2021, 2022, 2023, 2024, 2025];

const DEFAULT_NUM_RUNS = 1000;
const DEFAULT_PHASE = '[RUNTIME]';

// Two-letter codes supported by frontend/dist/css/flag.min.css (Semantic UI 2.5.0 sprite).
const FOMANTIC_FLAG_CODES = new Set(('ad ae af ag ai al am an ao ar as at au aw ax az ba bb bd be bf bg bh bi bj bm bn bo br bs bt bv bw by bz ca cc cd cf cg ch ci ck cl cm cn co cr cs cu cv cx cy cz de dj dk dm do dz ec ee eg eh er es et eu fi fj fk fm fo fr ga gb gd ge gf gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il in io iq ir is it jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls lt lu lv ly ma mc md me mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz na nc ne nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw py qa re ro rs ru rw sa sb sc sd se sg sh si sj sk sl sm sn so sr st sv sy sz tc td tf tg th tj tk tl tm tn to tr tt tv tw tz ua ug uk um us uy uz va vc ve vg vi vn vu wf ws ye yt za zm zw').split(' '));

const flagHtmlForZone = (zoneCode) => {
    if (typeof zoneCode !== 'string' || zoneCode.length < 2) return '';
    const cc = zoneCode.slice(0, 2).toLowerCase();
    if (!FOMANTIC_FLAG_CODES.has(cc)) return '';
    return `<i class="${cc} flag"></i>`;
};

const yearlyState = {
    runId: null,
    measurements: [],
    availableMetrics: [],
    selectedMetric: null,
    selectedYear: null,
    yearlyData: {},
    dataTable: null,
    totalEnergyKwh: null,
    numRuns: DEFAULT_NUM_RUNS,
    phases: [],
    selectedPhase: null,
    savedRows: [],
    savedTable: null
};

const queryY = (selector) => document.querySelector(selector);

const setTextY = (selector, value) => {
    const el = queryY(selector);
    if (el) el.textContent = value;
};

const setLoadFailureVisible = (visible, header, text) => {
    const message = queryY('#message-load-failure');
    if (!message) return;
    if (header) setTextY('#message-load-failure-header', header);
    if (text) setTextY('#message-load-failure-text', text);
    message.classList.toggle('hidden', !visible);
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
        if (err instanceof APIEmptyResponse204) return [];
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
    if (metrics.length === 0) return [];
    const psuMetrics = metrics.filter((metric) => metric.startsWith('psu_energy_'));
    if (psuMetrics.length > 0) return psuMetrics;
    return metrics.filter((metric) => metric.includes('_energy_'));
};

const getDefaultMetric = (metrics) => {
    if (!Array.isArray(metrics) || metrics.length === 0) return null;
    const preferred = 'psu_energy_ac_mcp_machine';
    return metrics.includes(preferred) ? preferred : metrics[0];
};

const getPhaseTimeRange = (phaseName) => {
    if (!phaseName) return null;
    const phase = yearlyState.phases.find((p) => p?.name === phaseName);
    if (!phase || phase.start == null || phase.end == null) return null;
    return { start: Number(phase.start), end: Number(phase.end) };
};

const computeTotalEnergyKwh = (measurements, metric, phaseName) => {
    if (!Array.isArray(measurements) || measurements.length === 0 || !metric) return null;
    const range = getPhaseTimeRange(phaseName);
    if (!range) return null;
    const inRange = (entry) => {
        const t = Number(entry?.[1]);
        if (!Number.isFinite(t)) return false;
        return t >= range.start && t <= range.end;
    };
    let total = 0;
    let matched = 0;
    measurements.forEach((entry) => {
        if (entry?.[2] !== metric) return;
        if (entry?.[0] !== '[MACHINE]') return;
        if (!inRange(entry)) return;
        const kwh = convertEnergyToKwh(entry[3], entry[4], metric);
        if (kwh == null) return;
        total += kwh;
        matched += 1;
    });
    if (matched === 0) {
        // Fall back to all detail rows summed if no [MACHINE] aggregate is present.
        measurements.forEach((entry) => {
            if (entry?.[2] !== metric) return;
            if (!inRange(entry)) return;
            const kwh = convertEnergyToKwh(entry[3], entry[4], metric);
            if (kwh == null) return;
            total += kwh;
            matched += 1;
        });
    }
    return matched > 0 ? total : null;
};

const formatEnergy = (kwh) => {
    if (kwh == null || Number.isNaN(kwh)) return '-';
    if (kwh < 0.001) return `${numberFormatter.format(kwh * 1_000_000)} mWh`;
    if (kwh < 1)     return `${numberFormatter.format(kwh * 1_000)} Wh`;
    return `${numberFormatter.format(kwh)} kWh`;
};

const loadYearData = async (year) => {
    if (yearlyState.yearlyData[year]) return yearlyState.yearlyData[year];
    const module = await import(`/js/yearly_co2/yearly_${year}.js`);
    yearlyState.yearlyData[year] = module.data || {};
    return yearlyState.yearlyData[year];
};

const buildTableRows = (yearData, totalKwh) => {
    const rows = [];
    Object.entries(yearData).forEach(([zoneCode, zoneEntry]) => {
        const intensity = zoneEntry?.carbonIntensity?.value;
        if (intensity == null) return;
        const zoneName = zoneEntry?.zone?.zoneName
            || zoneEntry?.zone?.countryName
            || zoneEntry?.zone?.displayName
            || zoneCode;
        const renewable = zoneEntry?.renewableEnergy?.value;
        const carbonFree = zoneEntry?.carbonFreeEnergy?.value;
        const emissions = totalKwh != null ? totalKwh * intensity * yearlyState.numRuns : null;
        rows.push([
            zoneCode,
            zoneName,
            intensity,
            renewable != null ? renewable : null,
            carbonFree != null ? carbonFree : null,
            emissions
        ]);
    });
    return rows;
};

const emissionsFormatter = new Intl.NumberFormat('en-US', {
    style: 'decimal',
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
});

const numericRender = (data, type) => {
    if (data == null) return type === 'display' ? '-' : null;
    if (type === 'display') return numberFormatter.format(data);
    return data;
};

const emissionsRender = (data, type) => {
    if (data == null) return type === 'display' ? '-' : null;
    if (type === 'display') return emissionsFormatter.format(data);
    return data;
};

const flagRender = (data, type) => type === 'display' ? flagHtmlForZone(data) : '';
const zoneRender = (data, type) => type === 'display' ? escapeString(data) : data;
const stringRender = (data, type) => type === 'display' ? escapeString(data) : data;

const renderTable = (rows) => {
    const tableEl = $('#yearly-table');
    if (yearlyState.dataTable) {
        yearlyState.dataTable.clear();
        yearlyState.dataTable.rows.add(rows);
        yearlyState.dataTable.draw();
        return;
    }
    yearlyState.dataTable = tableEl.DataTable({
        data: rows,
        deferRender: true,
        lengthMenu: [[25, 50, 100, 500], [25, 50, 100, 'All']],
        pageLength: 500,
        layout: {
            topStart: 'pageLength',
            topEnd: 'search',
            bottomStart: 'pageLength',
            bottomEnd: 'paging'
        },
        order: [[6, 'desc']],
        columns: [
            { title: 'Flag', data: 0, orderable: false, searchable: false, className: 'collapsing center aligned', render: flagRender },
            { title: 'Zone', data: 0, render: zoneRender },
            { title: 'Country / Region', data: 1, render: stringRender },
            { title: 'Carbon Intensity (gCO2eq/kWh)', data: 2, render: numericRender },
            { title: 'Renewable Energy (%)', data: 3, render: numericRender },
            { title: 'Carbon Free Energy (%)', data: 4, render: numericRender },
            { title: 'Estimated Run Emissions (gCO2eq)', data: 5, render: emissionsRender },
            {
                title: '',
                data: null,
                orderable: false,
                searchable: false,
                className: 'collapsing center aligned',
                defaultContent: '',
                render: () => '<i class="plus circle large green link icon save-row-btn" title="Save row"></i>'
            }
        ]
    });

    tableEl.on('click', '.save-row-btn', function () {
        const rowData = yearlyState.dataTable.row($(this).closest('tr')).data();
        if (!rowData) return;
        addSavedRow({
            year: yearlyState.selectedYear,
            zone: rowData[0],
            country: rowData[1],
            intensity: rowData[2],
            renewable: rowData[3],
            carbonFree: rowData[4],
            numRuns: yearlyState.numRuns,
            emissions: rowData[5]
        });
    });
};

const addSavedRow = (entry) => {
    if (!entry || entry.year == null || !entry.zone) return;
    const exists = yearlyState.savedRows.some((r) => r.zone === entry.zone && r.year === entry.year && r.numRuns === entry.numRuns);
    if (exists) return;
    yearlyState.savedRows.push(entry);
    renderSavedTable();
};

const removeSavedRow = (zone, year, numRuns) => {
    const idx = yearlyState.savedRows.findIndex((r) => r.zone === zone && r.year === year && r.numRuns === numRuns);
    if (idx === -1) return;
    yearlyState.savedRows.splice(idx, 1);
    renderSavedTable();
};

const savedRowsToTableData = () => yearlyState.savedRows.map((r) => [
    r.year,
    r.zone,
    r.country,
    r.intensity,
    r.renewable != null ? r.renewable : null,
    r.carbonFree != null ? r.carbonFree : null,
    r.numRuns,
    r.emissions
]);

const renderSavedTable = () => {
    const card = queryY('#saved-rows-card');
    if (card) card.classList.toggle('hidden', yearlyState.savedRows.length === 0);

    const rows = savedRowsToTableData();
    const tableEl = $('#saved-rows-table');
    if (yearlyState.savedTable) {
        yearlyState.savedTable.clear();
        yearlyState.savedTable.rows.add(rows);
        yearlyState.savedTable.draw();
        return;
    }
    yearlyState.savedTable = tableEl.DataTable({
        data: rows,
        deferRender: true,
        paging: false,
        info: false,
        layout: {
            topStart: '',
            topEnd: 'search',
            bottomStart: '',
            bottomEnd: ''
        },
        order: [[8, 'desc']],
        columns: [
            { title: 'Year', data: 0 },
            { title: 'Flag', data: 1, orderable: false, searchable: false, className: 'collapsing center aligned', render: flagRender },
            { title: 'Zone', data: 1, render: zoneRender },
            { title: 'Country / Region', data: 2, render: stringRender },
            { title: 'Carbon Intensity (gCO2eq/kWh)', data: 3, render: numericRender },
            { title: 'Renewable Energy (%)', data: 4, render: numericRender },
            { title: 'Carbon Free Energy (%)', data: 5, render: numericRender },
            { title: '# Runs', data: 6, render: (data, type) => type === 'display' ? data.toLocaleString('en-US') : data },
            { title: 'Estimated Run Emissions (gCO2eq)', data: 7, render: emissionsRender },
            {
                title: '',
                data: null,
                orderable: false,
                searchable: false,
                className: 'collapsing center aligned',
                defaultContent: '',
                render: () => '<i class="trash large red link icon remove-row-btn" title="Remove row"></i>'
            }
        ]
    });

    tableEl.on('click', '.remove-row-btn', function () {
        const rowData = yearlyState.savedTable.row($(this).closest('tr')).data();
        if (!rowData) return;
        removeSavedRow(rowData[1], rowData[0], rowData[6]);
    });
};

const updateYearButtonsState = () => {
    const container = queryY('#year-buttons');
    if (!container) return;
    container.querySelectorAll('button[data-year]').forEach((btn) => {
        const isActive = Number(btn.dataset.year) === yearlyState.selectedYear;
        btn.classList.toggle('active', isActive);
        btn.classList.toggle('blue', isActive);
    });
};

const recalculateAndRender = async () => {
    if (yearlyState.selectedYear == null) return;
    if (!yearlyState.selectedMetric) return;

    yearlyState.totalEnergyKwh = computeTotalEnergyKwh(yearlyState.measurements, yearlyState.selectedMetric, yearlyState.selectedPhase);
    setTextY('#run-energy', formatEnergy(yearlyState.totalEnergyKwh));

    if (yearlyState.totalEnergyKwh == null) {
        setLoadFailureVisible(true, 'No energy data', 'Could not compute total energy for the selected metric.');
        renderTable([]);
        return;
    }
    setLoadFailureVisible(false);

    try {
        const yearData = await loadYearData(yearlyState.selectedYear);
        const rows = buildTableRows(yearData, yearlyState.totalEnergyKwh);
        renderTable(rows);
    } catch (err) {
        setLoadFailureVisible(true, 'Failed to load year data', String(err?.message || err));
        renderTable([]);
    }
};

const selectYear = (year) => {
    if (yearlyState.selectedYear === year) return;
    yearlyState.selectedYear = year;
    updateYearButtonsState();
    recalculateAndRender();
};

const renderYearButtons = () => {
    const container = queryY('#year-buttons');
    if (!container) return;
    container.innerHTML = '';
    AVAILABLE_YEARS.forEach((year) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ui button';
        btn.dataset.year = String(year);
        btn.textContent = String(year);
        btn.addEventListener('click', () => selectYear(year));
        container.appendChild(btn);
    });
};

const prettyPhaseName = (rawName) => {
    if (typeof rawName !== 'string') return String(rawName);
    const stripped = rawName.replace(/^\[|\]$/g, '');
    if (stripped.length === 0) return rawName;
    const lower = stripped.toLowerCase();
    return lower.charAt(0).toUpperCase() + lower.slice(1);
};

const populatePhases = (phases) => {
    const menu = queryY('#phase-menu');
    if (!menu) return;
    menu.innerHTML = '';

    const visiblePhases = (Array.isArray(phases) ? phases : []).filter(
        (phase) => phase && typeof phase.name === 'string' && !phase.hidden
    );

    visiblePhases.forEach((phase) => {
        const entry = document.createElement('div');
        entry.className = 'item';
        entry.dataset.value = phase.name;
        entry.textContent = prettyPhaseName(phase.name);
        menu.appendChild(entry);
    });

    $('#phase-dropdown').dropdown({
        clearable: false,
        onChange: (value) => {
            if (!value || value === yearlyState.selectedPhase) return;
            yearlyState.selectedPhase = value;
            recalculateAndRender();
        }
    });

    const defaultPhase = visiblePhases.find((p) => p.name === DEFAULT_PHASE)?.name
        || visiblePhases[0]?.name;
    if (defaultPhase) {
        yearlyState.selectedPhase = defaultPhase;
        $('#phase-dropdown').dropdown('set selected', defaultPhase);
    }
};

const populateMetrics = (metrics) => {
    const menu = queryY('#metric-menu');
    menu.innerHTML = '';
    metrics.forEach((metric) => {
        const entry = document.createElement('div');
        entry.className = 'item';
        entry.dataset.value = metric;
        entry.textContent = metric;
        menu.appendChild(entry);
    });

    $('#metric-dropdown').dropdown({
        clearable: false,
        onChange: (value) => {
            if (!value || value === yearlyState.selectedMetric) return;
            yearlyState.selectedMetric = value;
            recalculateAndRender();
        }
    });

    const defaultMetric = getDefaultMetric(metrics);
    if (defaultMetric) {
        $('#metric-dropdown').dropdown('set selected', defaultMetric);
    }
};

$(document).ready(() => {
    (async () => {
        renderYearButtons();

        const numRunsInput = queryY('#num-runs-input');
        if (numRunsInput) {
            numRunsInput.addEventListener('change', () => {
                const parsed = Number(numRunsInput.value);
                if (!Number.isFinite(parsed) || parsed < 1) {
                    numRunsInput.value = String(yearlyState.numRuns);
                    return;
                }
                yearlyState.numRuns = Math.floor(parsed);
                numRunsInput.value = String(yearlyState.numRuns);
                recalculateAndRender();
            });
        }

        const urlParams = getURLParams();
        const runId = urlParams['id'];
        if (!runId || runId === 'null') {
            showNotification('No run id', 'ID parameter in URL is empty or missing.');
            queryY('#metric-dropdown')?.classList.remove('loading');
            return;
        }

        yearlyState.runId = runId;

        try {
            const [runData, measurements] = await Promise.all([
                fetchRunData(runId),
                fetchMeasurements(runId)
            ]);

            yearlyState.measurements = measurements;
            yearlyState.phases = Array.isArray(runData?.phases) ? runData.phases : [];
            populatePhases(yearlyState.phases);
            queryY('#phase-dropdown')?.classList.remove('loading');
            const metricOptions = buildEnergyMetricOptions(measurements);
            yearlyState.availableMetrics = metricOptions;

            if (metricOptions.length === 0) {
                setLoadFailureVisible(true, 'No metric data', 'Either the run has not produced any data yet, or the data was deleted.');
            } else {
                populateMetrics(metricOptions);
            }
        } catch (err) {
            showNotification('Could not load run data', err);
        } finally {
            queryY('#metric-dropdown')?.classList.remove('loading');
        }

        // Default to the largest available year.
        const defaultYear = AVAILABLE_YEARS[AVAILABLE_YEARS.length - 1];
        yearlyState.selectedYear = defaultYear;
        updateYearButtonsState();
        recalculateAndRender();
    })();
});
