"use strict";

const DEFAULT_PHASE = '[RUNTIME]';

const compareSimpleState = {
    runIds: [],
    runMeta: {},
    phaseStats: {},
    availablePhases: new Set(),
    selectedPhase: DEFAULT_PHASE,
    selectedMetrics: null, // null = no filter (show all); otherwise a Set of `${metric_name}||${detail_name}` keys
    metricsOnY: false,
    colorize: true,
    showSource: false,
    showDetail: false,
    dataTable: null,
};

// Green (hsl 120) → red (hsl 0), low = best.
const colorForRatio = (ratio) => {
    const r = Math.max(0, Math.min(1, ratio));
    const hue = 120 * (1 - r);
    return `hsl(${hue}, 70%, 80%)`;
};

// Round a value the same way it is displayed, so cells that show identical numbers also get
// identical colours (the raw means can differ below the displayed precision).
const roundForDisplay = (value) => {
    if (value == null || Number.isNaN(value)) return value;
    return Number(numberFormatter.format(value).replace(/,/g, ''));
};

const buildMetricRanges = (metricKeys, lookup) => {
    const ranges = {};
    metricKeys.forEach((m) => {
        const key = `${m.metric_name}||${m.detail_name}`;
        const values = compareSimpleState.runIds
            .map((rid) => lookup[rid][key]?.mean)
            .filter((v) => v != null && !Number.isNaN(v))
            .map(roundForDisplay);
        if (values.length < 2) return;
        const min = Math.min(...values);
        const max = Math.max(...values);
        if (min === max) return;
        ranges[key] = { min, max };
    });
    return ranges;
};

const fetchSinglePhaseStats = async (run_id) => {
    try {
        const response = await makeAPICall(`/v1/phase_stats/single/${encodeURIComponent(run_id)}`);
        return response?.data || null;
    } catch (err) {
        if (err instanceof APIHTTPError && err.status === 204) return null;
        showNotification(`Could not load phase stats for run ${run_id}`, err);
        return null;
    }
};

const fetchRunMeta = async (run_id) => {
    try {
        const response = await makeAPICall(`/v2/run/${encodeURIComponent(run_id)}`);
        return response?.data || null;
    } catch (err) {
        showNotification(`Could not load run info for ${run_id}`, err);
        return null;
    }
};

const buildRunLabel = (run_id, meta) => {
    if (!meta) return run_id.slice(0, 8);
    const parts = [];
    if (meta.name) parts.push(escapeString(meta.name));
    if (meta.commit_hash) parts.push(`<code>${escapeString(String(meta.commit_hash).slice(0, 7))}</code>`);
    return parts.join('<br>') || run_id.slice(0, 8);
};

const extractMetricRowsForPhase = (phaseStatsObject, phase, run_id) => {
    const rows = [];
    const phase_data = phaseStatsObject?.data?.[phase]?.data;
    if (!phase_data) return rows;

    for (const metric_name in phase_data) {
        const metric_data = phase_data[metric_name];
        const unit = metric_data.unit;
        for (const detail_name in metric_data.data) {
            const detail = metric_data.data[detail_name];
            // For a single run the key in detail.data is the run_id itself.
            const value_entry = detail.data?.[run_id] || Object.values(detail.data || {})[0];
            if (value_entry == null) continue;
            const [converted_value, converted_unit] = convertValue(value_entry.mean, unit);
            rows.push({
                metric_name,
                detail_name,
                source: getPretty(metric_name, 'source'),
                clean_name: getPretty(metric_name, 'clean_name'),
                unit: converted_unit,
                mean: converted_value,
            });
        }
    }
    return rows;
};

const buildMetricKeys = (phase) => {
    const map = new Map();
    compareSimpleState.runIds.forEach((run_id) => {
        const stats = compareSimpleState.phaseStats[run_id];
        if (!stats) return;
        const rows = extractMetricRowsForPhase(stats, phase, run_id);
        rows.forEach((row) => {
            const key = `${row.metric_name}||${row.detail_name}`;
            if (!map.has(key)) {
                map.set(key, {
                    metric_name: row.metric_name,
                    detail_name: row.detail_name,
                    source: row.source,
                    clean_name: row.clean_name,
                    unit: row.unit,
                });
            }
        });
    });
    return [...map.values()].sort((a, b) => {
        if (a.source !== b.source) return a.source.localeCompare(b.source);
        if (a.clean_name !== b.clean_name) return a.clean_name.localeCompare(b.clean_name);
        return a.detail_name.localeCompare(b.detail_name);
    });
};

const buildValueLookup = (phase) => {
    const lookup = {};
    compareSimpleState.runIds.forEach((run_id) => {
        lookup[run_id] = {};
        const stats = compareSimpleState.phaseStats[run_id];
        if (!stats) return;
        const rows = extractMetricRowsForPhase(stats, phase, run_id);
        rows.forEach((row) => {
            lookup[run_id][`${row.metric_name}||${row.detail_name}`] = { mean: row.mean, unit: row.unit };
        });
    });
    return lookup;
};

const formatValue = (value) => {
    if (value == null || Number.isNaN(value)) return '';
    return numberFormatter.format(value);
};

const populatePhaseDropdown = () => {
    const select = document.querySelector('#phase-select');
    const mainPhases = ['[BASELINE]', '[INSTALLATION]', '[BOOT]', '[IDLE]', '[RUNTIME]', '[REMOVE]'];

    // Mark hardcoded main-phase options as disabled when no run produced data for them.
    Array.from(select.options).forEach((opt) => {
        if (!compareSimpleState.availablePhases.has(opt.value)) {
            opt.disabled = true;
            opt.text = `${opt.text} (no data)`;
        }
    });

    // Append sub-phases (anything without [BRACKETS]) that exist in any run, grouped under an optgroup.
    const subPhases = [...compareSimpleState.availablePhases]
        .filter((p) => !mainPhases.includes(p))
        .sort((a, b) => a.localeCompare(b));

    if (subPhases.length > 0) {
        const group = document.createElement('optgroup');
        group.label = 'Sub-phases';
        subPhases.forEach((phase) => {
            const opt = document.createElement('option');
            opt.value = phase;
            opt.text = phase;
            group.appendChild(opt);
        });
        select.appendChild(group);
    }

    if (!compareSimpleState.availablePhases.has(compareSimpleState.selectedPhase)) {
        const fallback = mainPhases.find((p) => compareSimpleState.availablePhases.has(p))
            || subPhases[0];
        if (fallback) {
            compareSimpleState.selectedPhase = fallback;
            select.value = fallback;
        }
    } else {
        select.value = compareSimpleState.selectedPhase;
    }

    select.addEventListener('change', () => {
        compareSimpleState.selectedPhase = select.value;
        // Re-list the dropdown options for the new phase, but keep the selection — metrics that don't
        // exist in the new phase are silently dropped from view but preserved in state for if the user
        // switches back.
        populateMetricsDropdown();
        renderTable();
    });

    $(select).dropdown();
};

const populateMetricsDropdown = () => {
    const select = document.querySelector('#metrics-select');
    const allMetrics = buildMetricKeys(compareSimpleState.selectedPhase);

    if ($(select).data('moduleDropdown')) {
        $(select).dropdown('destroy');
    }
    select.innerHTML = '';
    allMetrics.forEach((m) => {
        const opt = document.createElement('option');
        opt.value = `${m.metric_name}||${m.detail_name}`;
        opt.text = `${m.clean_name} — ${m.detail_name}${m.unit ? ` (${m.unit})` : ''}`;
        if (compareSimpleState.selectedMetrics != null && compareSimpleState.selectedMetrics.has(opt.value)) {
            opt.selected = true;
        }
        select.appendChild(opt);
    });

    $(select).dropdown({
        placeholder: 'All metrics shown',
        onChange: () => {
            const selected = Array.from(select.selectedOptions).map((o) => o.value);
            compareSimpleState.selectedMetrics = selected.length === 0 ? null : new Set(selected);
            syncURLParams();
            renderTable();
        },
    });
};

const syncURLParams = () => {
    const url = new URL(window.location.href);
    const p = url.searchParams;

    if (compareSimpleState.metricsOnY) { p.set('swap_axes', 'true'); } else { p.delete('swap_axes'); }
    if (compareSimpleState.showSource)  { p.set('source', 'true'); }   else { p.delete('source'); }
    if (compareSimpleState.showDetail)  { p.set('detail', 'true'); }   else { p.delete('detail'); }

    if (compareSimpleState.selectedMetrics != null && compareSimpleState.selectedMetrics.size > 0) {
        const names = [...new Set([...compareSimpleState.selectedMetrics].map((k) => k.split('||')[0]))];
        p.set('metrics', names.join(','));
    } else {
        p.delete('metrics');
    }

    history.replaceState(null, '', url.toString());
};

const updateAxisSwitchLabel = () => {
    const label = document.querySelector('#axis-switch-label');
    label.textContent = compareSimpleState.metricsOnY
        ? 'Metrics on Y / Runs on X'
        : 'Runs on Y / Metrics on X';
};

const resetTableElement = () => {
    const tableEl = $('#compare-simple-table');
    if (compareSimpleState.dataTable) {
        compareSimpleState.dataTable.destroy();
        compareSimpleState.dataTable = null;
    }
    tableEl.empty();
};

const renderMetricsOnY = (metricKeys, lookup) => {
    const ranges = compareSimpleState.colorize ? buildMetricRanges(metricKeys, lookup) : {};
    const columns = [
        { title: 'Metric', data: 'metric' },
    ];
    if (compareSimpleState.showSource) {
        columns.push({ title: 'Source', data: 'source' });
    }
    if (compareSimpleState.showDetail) {
        columns.push({ title: 'Detail', data: 'detail' });
    }
    columns.push({ title: 'Unit', data: 'unit' });
    compareSimpleState.runIds.forEach((run_id, idx) => {
        const label = buildRunLabel(run_id, compareSimpleState.runMeta[run_id]);
        columns.push({
            title: `<a href="/stats.html?id=${encodeURIComponent(run_id)}" target="_blank">${label}</a>`,
            data: `run_${idx}`,
            className: 'dt-body-right',
            render: function (val, type) {
                if (type === 'display' || type === 'filter') return formatValue(val);
                return val == null ? null : val;
            },
            createdCell: function (td, cellData, rowData) {
                const range = ranges[rowData._key];
                if (!range || cellData == null || Number.isNaN(cellData)) return;
                const value = roundForDisplay(cellData);
                td.style.backgroundColor = colorForRatio((value - range.min) / (range.max - range.min));
            },
        });
    });

    const data = metricKeys.map((m) => {
        const key = `${m.metric_name}||${m.detail_name}`;
        const row = {
            _key: key,
            metric: escapeString(m.clean_name),
            source: escapeString(m.source),
            detail: escapeString(m.detail_name),
            unit: escapeString(m.unit || ''),
        };
        compareSimpleState.runIds.forEach((run_id, idx) => {
            row[`run_${idx}`] = lookup[run_id][key]?.mean ?? null;
        });
        return row;
    });

    return { columns, data };
};

const renderRunsOnY = (metricKeys, lookup) => {
    const ranges = compareSimpleState.colorize ? buildMetricRanges(metricKeys, lookup) : {};
    const columns = [
        {
            title: 'Run',
            data: 'run',
            render: function (val, type) {
                if (type === 'display') return val;
                return val.replace(/<[^>]*>/g, '');
            },
        },
    ];
    metricKeys.forEach((m, idx) => {
        const key = `${m.metric_name}||${m.detail_name}`;
        const nameLine = m.unit
            ? `${escapeString(m.clean_name)} <small>(${escapeString(m.unit)})</small>`
            : escapeString(m.clean_name);
        const parts = [`<div>${nameLine}</div>`];
        if (compareSimpleState.showSource) {
            parts.push(`<small class="detail-name-ellipsis" title="${escapeString(m.source)}">${escapeString(m.source)}</small>`);
        }
        if (compareSimpleState.showDetail) {
            parts.push(`<small class="detail-name-ellipsis" title="${escapeString(m.detail_name)}">${escapeString(m.detail_name)}</small>`);
        }
        const header = parts.join('');
        columns.push({
            title: header,
            data: `metric_${idx}`,
            className: 'dt-body-right',
            render: function (val, type) {
                if (type === 'display' || type === 'filter') return formatValue(val);
                return val == null ? null : val;
            },
            createdCell: function (td, cellData) {
                const range = ranges[key];
                if (!range || cellData == null || Number.isNaN(cellData)) return;
                const value = roundForDisplay(cellData);
                td.style.backgroundColor = colorForRatio((value - range.min) / (range.max - range.min));
            },
        });
    });

    const data = compareSimpleState.runIds.map((run_id) => {
        const label = buildRunLabel(run_id, compareSimpleState.runMeta[run_id]);
        const row = {
            run: `<a href="/stats.html?id=${encodeURIComponent(run_id)}" target="_blank">${label}</a>`,
        };
        metricKeys.forEach((m, idx) => {
            row[`metric_${idx}`] = lookup[run_id][`${m.metric_name}||${m.detail_name}`]?.mean ?? null;
        });
        return row;
    });

    return { columns, data };
};

const renderTable = () => {
    const phase = compareSimpleState.selectedPhase;
    const allMetricKeys = buildMetricKeys(phase);
    const noDataEl = document.querySelector('#no-data-message');

    if (allMetricKeys.length === 0) {
        resetTableElement();
        noDataEl.classList.remove('hidden');
        return;
    }
    noDataEl.classList.add('hidden');

    const metricKeys = compareSimpleState.selectedMetrics == null
        ? allMetricKeys
        : allMetricKeys.filter((m) => compareSimpleState.selectedMetrics.has(`${m.metric_name}||${m.detail_name}`));

    const lookup = buildValueLookup(phase);
    const { columns, data } = compareSimpleState.metricsOnY
        ? renderMetricsOnY(metricKeys, lookup)
        : renderRunsOnY(metricKeys, lookup);

    resetTableElement();

    compareSimpleState.dataTable = $('#compare-simple-table').DataTable({
        data: data,
        columns: columns,
        deferRender: true,
        autoWidth: false,
        lengthMenu: [[25, 50, 100, -1], [25, 50, 100, 'All']],
        pageLength: 100,
        layout: {
            topStart: 'pageLength',
            topEnd: 'search',
            bottomStart: 'info',
            bottomEnd: 'paging',
        },
        order: [],
    });
};

$(document).ready(() => {
    (async () => {
        const url_params = getURLParams();

        if (url_params['ids'] == null || url_params['ids'] === '' || url_params['ids'] === 'null') {
            showNotification('No ids', 'ids parameter in URL is empty or not present. Did you follow a correct URL?');
            document.querySelector('#loader-compare-simple').remove();
            return;
        }

        compareSimpleState.runIds = url_params['ids'].split(',').filter((s) => s.length > 0);

        if (compareSimpleState.runIds.length === 0) {
            showNotification('No ids', 'ids parameter is empty after parsing.');
            document.querySelector('#loader-compare-simple').remove();
            return;
        }

        if (url_params['swap_axes'] === 'true') compareSimpleState.metricsOnY = true;
        if (url_params['source'] === 'true') compareSimpleState.showSource = true;
        if (url_params['detail'] === 'true') compareSimpleState.showDetail = true;

        const results = await Promise.all(compareSimpleState.runIds.map(async (run_id) => {
            const [stats, meta] = await Promise.all([
                fetchSinglePhaseStats(run_id),
                fetchRunMeta(run_id),
            ]);
            return { run_id, stats, meta };
        }));

        const phaseSetsPerRun = [];
        results.forEach(({ run_id, stats, meta }) => {
            if (stats) {
                compareSimpleState.phaseStats[run_id] = stats;
                phaseSetsPerRun.push(new Set(Object.keys(stats.data || {})));
            }
            if (meta) compareSimpleState.runMeta[run_id] = meta;
        });

        // Intersection across all runs that returned stats — a phase is only "available" when every run has it.
        if (phaseSetsPerRun.length > 0) {
            compareSimpleState.availablePhases = phaseSetsPerRun.reduce(
                (acc, set) => new Set([...acc].filter((p) => set.has(p))),
            );
        }

        document.querySelector('#loader-compare-simple').remove();

        populatePhaseDropdown();

        if (url_params['metrics']) {
            const requestedMetrics = url_params['metrics'].split(',').map((s) => s.trim()).filter((s) => s.length > 0);
            const allMetricKeys = buildMetricKeys(compareSimpleState.selectedPhase);
            const matched = new Set();
            requestedMetrics.forEach((requested) => {
                allMetricKeys.forEach((m) => {
                    if (m.metric_name === requested || m.clean_name.toLowerCase() === requested.toLowerCase()) {
                        matched.add(`${m.metric_name}||${m.detail_name}`);
                    }
                });
            });
            if (matched.size === 0) {
                showNotification('Invalid deeplink', `No metrics matched the provided 'metrics' parameter: "${url_params['metrics']}". Showing all metrics.`);
            } else {
                compareSimpleState.selectedMetrics = matched;
            }
        }

        populateMetricsDropdown();
        updateAxisSwitchLabel();

        const wireToggleButton = (selector, stateKey, onAfterToggle) => {
            const btn = document.querySelector(selector);
            const syncVisual = () => {
                btn.classList.toggle('active', compareSimpleState[stateKey]);
                btn.classList.toggle('basic', !compareSimpleState[stateKey]);
            };
            syncVisual();
            btn.addEventListener('click', () => {
                compareSimpleState[stateKey] = !compareSimpleState[stateKey];
                syncVisual();
                if (onAfterToggle) onAfterToggle();
                syncURLParams();
                renderTable();
            });
        };

        wireToggleButton('#axis-switch-button', 'metricsOnY', updateAxisSwitchLabel);
        wireToggleButton('#colorize-button', 'colorize');
        wireToggleButton('#source-toggle-button', 'showSource');
        wireToggleButton('#detail-toggle-button', 'showDetail');

        renderTable();
    })();
});
