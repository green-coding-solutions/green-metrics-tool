
let system_logs_rows = []; // raw [id, title, message, level, created_at] rows as returned by the API

// Values that are unique per occurrence and must not separate two otherwise identical errors
const SYSTEM_LOG_SCRUBBERS = [
    [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '<uuid>'],
    [/\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?/g, '<timestamp>'],
    [/0x[0-9a-f]+/gi, '<hex>'],
    [/\d+/g, '<num>'],
];

// lib/error_helpers.py::format_error renders every kwarg as "Key (Type): value". Key and type
// (the exception class for Last_exception) identify the error, the value is per-run data.
const SYSTEM_LOG_KEY_VALUE_LINE = /^([A-Za-z][\w-]*) \(([\w.]+)\): /;

const systemLogSignature = (row) => {
    let signature = String(row[2] ?? '').split('\n').map((line) => {
        const match = line.match(SYSTEM_LOG_KEY_VALUE_LINE);
        return match ? `${match[1]} (${match[2]}):` : line;
    }).join('\n');

    for (const [pattern, placeholder] of SYSTEM_LOG_SCRUBBERS) signature = signature.replace(pattern, placeholder);

    return `${row[1]}\n${row[3]}\n${signature.replace(/\s+/g, ' ').trim()}`;
};

// Every table row carries its group members in index 5, so grouped and ungrouped rows render alike
const systemLogTableRows = (rows, grouped) => {
    if (!grouped) return rows.map((row) => [...row, [row]]);

    const groups = new Map();
    rows.forEach((row) => {
        const signature = systemLogSignature(row);
        if (!groups.has(signature)) groups.set(signature, []);
        groups.get(signature).push(row);
    });

    return Array.from(groups.values()).map((members) => {
        members.sort((a, b) => new Date(b[4]) - new Date(a[4]));
        return [...members[0], members]; // newest member represents the group
    });
};

const renderSystemLogs = () => {
    const grouped = document.getElementById('system-logs-group-toggle').checked;
    $('#system-logs-table').DataTable().clear().rows.add(systemLogTableRows(system_logs_rows, grouped)).draw();
};

const renderSystemLogGroupMembers = (members) => members.map((member) => `
    <div class="ui segment">
        <div style="margin-bottom: 0.5em;">
            <b>#${member[0]}</b> - ${member[4] == null ? '-' : dateToYMD(new Date(member[4]))}
            <a class="delete-log" data-log-ids="${member[0]}" title="Delete this entry"><i class="ui icon red times circle"></i></a>
        </div>
        <pre style="white-space:pre-wrap;max-height:500px; max-width:80vw;overflow:auto;margin:0">${escapeString(member[2])}</pre>
    </div>`).join('');

function toggleSystemLogGroup(e) {
    e.preventDefault()
    const row = $('#system-logs-table').DataTable().row($(this).closest('tr'));
    const caret = this.querySelector('i');

    if (row.child.isShown()) {
        row.child.hide();
        caret.classList.replace('down', 'right');
    } else {
        row.child(`<div class="ui segments">${renderSystemLogGroupMembers(row.data()[5])}</div>`).show();
        caret.classList.replace('right', 'down');
    }
    return false;
};

async function deleteSystemLog(e){
    e.preventDefault()
    const log_ids = this.getAttribute('data-log-ids').split(',').map((log_id) => parseInt(log_id, 10));

    if (log_ids.length > 1 && !confirm(`Delete all ${log_ids.length} log entries in this group?`)) return false;

    const deleted = [];
    try {
        for (const log_id of log_ids) {
            await makeAPICall('/v1/system-log', {log_id: log_id, action: 'delete'}, null, true)
            deleted.push(log_id);
        }
        showNotification('Log deleted', `${deleted.length} system log ${deleted.length == 1 ? 'entry' : 'entries'} deleted successfully`, 'success');
    } catch (err) {
        showNotification('Could not delete log', err);
    } finally {
        // rebuild from source so a partial failure still leaves the table consistent with the DB
        system_logs_rows = system_logs_rows.filter((row) => !deleted.includes(row[0]));
        renderSystemLogs();
    }
    return false;
};

async function cancelJob(e){
    e.preventDefault()
    const job_id = this.getAttribute('data-job-id');
    try {
        await makeAPICall('/v1/job', {job_id: job_id, action: 'cancel'}, null, true)
        const row = this.closest('tr');
        row.querySelector('.job-state').innerText = 'CANCELLED'
        row.querySelector('.job-action').innerHTML = '<i class="ui large icon grey minus"></i>'
        showNotification('Job cancelled', 'Job has been cancelled successfully', 'success');
    } catch (err) {
        showNotification('Could not cancel job', err);
    }
    return false; // bc link click
};

$(document).ready(function () {
    (async () => {

        let machines_data = null;
        let jobs_data = null;

        await getClusterStatus();

        try {
            machines_data = await makeAPICall('/v1/machines')
        } catch (err) {
            showNotification('Could not get machines data from API', err); // we do not return here, as empty data is an OK response
        }

        try {
            jobs_data = await makeAPICall('/v2/jobs')
        } catch (err) {
            showNotification('Could not get jobs data from API', err); // we do not return here, as empty data is an OK response
        }

        let system_logs_data = null;
        try {
            system_logs_data = await makeAPICall('/v1/system-logs')
        } catch (err) {
            if (err instanceof APIHTTPError && err.status === 401) {
                document.getElementById('system-logs-section').style.display = 'none';
                document.getElementById('system-logs-no-access').style.display = '';
            } else if (!(err instanceof APIHTTPError && err.status === 204)) {
                showNotification('Could not get system logs from API', err);
            }
        }

        $('#machines-table').DataTable({
            data: machines_data?.data,
            searching: false,
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Name', render: (el) => escapeString(el)},
                { data: 2, title: 'Available', render: function(el) {
                    return (el == true) ? '<i class="ui label mini empty green circular"></i>': '<i class="ui label mini empty red circular"></i>';
                }},
                { data: 5, title: 'Jobs processing'},
                { data: 3, title: 'State', render: function(el) {
                    switch (el) {
                            case 'job_no': return `${escapeString(el)} <span data-inverted data-tooltip="No job currently in queue"><i class="ui question circle icon fluid"></i></span>`;
                            case 'job_start': return `${escapeString(el)} <span data-inverted data-tooltip="Current Job has started running"><i class="ui question circle icon fluid"></i></span>`;
                            case 'job_error': return `${escapeString(el)} <span data-inverted data-tooltip="Last job failed"></i></span>`;
                            case 'job_end': return `${escapeString(el)} <span data-inverted data-tooltip="Current job ended"></i></span>`;
                            case 'maintenance_start': return `${escapeString(el)} <span data-inverted data-tooltip="Maintenance after job has started"><i class="ui question circle icon fluid"></i></span>`;
                            case 'maintenance_end': return `${escapeString(el)} <span data-inverted data-tooltip="Maintenance after job has finished"><i class="ui question circle icon fluid"></i></span>`;
                            case 'measurement_control_start': return `${escapeString(el)} <span data-inverted data-tooltip="Periodic Measurement Control job has started"><i class="ui question circle icon fluid"></i></span>`;
                            case 'cooldown': return `${escapeString(el)} <span data-inverted data-tooltip="Machine is currently cooling down to base temperature"><i class="ui question circle icon fluid"></i></span>`;
                            case 'measurement_control_error': return `${escapeString(el)} <span data-inverted data-tooltip="Last periodic Measurement Control job has failed"><i class="ui question circle icon fluid"></i></span>`;
                            case 'measurement_control_end': return `${escapeString(el)} <span data-inverted data-tooltip="Periodic Measurement Control job has finished"><i class="ui question circle icon fluid"></i></span>`;
                            case undefined: // fallthrough
                            case null: return '-';
                    }
                    return escapeString(el);
                }},
                { data: 6, title: 'GMT version', render: function(el, type, row) {
                    if (el == null) return '-';

                    return `<a href="https://github.com/green-coding-solutions/green-metrics-tool/commit/${el}" title="${dateToYMD(new Date(row[7]))}">${`${escapeString(el.slice(0,3))}...${escapeString(el.slice(-3))}`}</a>`;

                }},
                { data: 13, title: 'Details', render: function(el, type, row) {
                    let timeline_link = '';
                    if (el?.cluster?.client?.control_workload != null) {
                        const cw = el.cluster.client.control_workload;
                        const params = new URLSearchParams();
                        params.set('uri', cw.uri ?? '');
                        params.set('branch', cw.branch ?? '');
                        params.set('machine_id', row[0]);
                        params.set('filename', cw.filename ?? '');
                        params.set('usage_scenario_variables', 'false');
                        const href = `/timeline.html?${params.toString().replace(/&/g, '&amp;')}`;
                        timeline_link = `<a title="Timeline Analysis" href="${href}" class="ui icon button no-wrap teal" target="_blank"><i class="ui icon clock"></i></a>`;
                    }
                    return `<div class="no-wrap"><button class="ui icon button show-machine-configuration"><i class="ui info icon"></i><span class="machine-configuration-details" style="display:none; ">${escapeString(JSON.stringify(el, undefined, 2))}</span></button>${timeline_link}</div>`;
                }},
                { data: 8, title: 'Base temp (°)'},
                { data: 9, title: 'Current temp (°)', render: (el) => el == null ? '-' : el},
                { data: 10, title: 'Expected cooldown time', render: function(el) {
                    return (el == null) ? 'awaiting info': `${Math.round(el/60)} Minutes`;
                }},
                { data: 11, title: 'Waiting Jobs'},
                { data: 13, title: 'Jobs queue update freq.', render: (el) => el?.cluster?.client?.sleep_time_no_job == null ? '-' : `${Math.round(el['cluster']['client']['sleep_time_no_job'] / 60)} Minutes` },
                { data: 12, title: 'Estimated waiting time', render: function(el, type, row) {
                    return (row[10] == null || row[12] == null) ? 'awaiting info' : `${Math.round(( (row[10]+row[12]) * row[11]) / 60)} Minutes`
                }},
                { data: 4, title: 'Updated at', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
            ],
            deferRender: true,
            drawCallback: function(settings) {
                $('.show-machine-configuration').on('click', function(el) {
                        el.preventDefault();
                        $("#machine-configuration-details pre").text($(this).find('.machine-configuration-details').text())
                        $("#machine-configuration-details").removeClass("loading")
                        $('#machine-configuration').modal('show');
                    })
            },
            order: [[2, 'asc']], // API also orders, but we need to indicate order for the user
        });

        const jobs_table = $('#jobs-table').DataTable({
            data: jobs_data?.data,
            columns: [
                { data: 0, title: 'ID'},
                { data: 2, title: 'Name', render: (name, type, row) => row[1] == null ? escapeString(name) : `<a href="/stats.html?id=${row[1]}">${escapeString(name)}</a>`  },
                { data: 3, title: 'Url', render: (el) => `<span class="left-side-ellipsis long-ellipsis" title="${escapeString(el)}">${escapeString(el)}</span>`},
                {
                    data: 4,
                    title: 'Filename',
                    render: function(el, type, row) {
                        const usage_scenario_variables = Object.entries(row[5]).map(([k, v]) => `<span class="ui label">${escapeString(k)}=${escapeString(v)}</span>`);
                        return `${escapeString(el)} ${usage_scenario_variables.join(' ')}`
                    }},
                { data: 6, title: 'Branch', render: (el) => escapeString(el)},
                { data: 7, title: 'Machine', render: (el) => escapeString(el)},
                { data: 8, title: 'State', class: "job-state", render: (el) => escapeString(el)},
                { data: 10, title: 'Created at', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
                { data: 9, title: 'Updated at', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
                { data: 8,  title: '-', class: "job-action",  render: (el, type, row) => {
                    if (el == 'WAITING') {
                        return `<a class="cancel-job" data-job-id="${row[0]}"><i class="ui large icon red times circle"></i></a>`
                    } else {
                        return `<i class="ui large icon grey minus"></i>`
                    }
                } },
            ],
            deferRender: true,
            order: [[7, 'desc']], // API also orders, but we need to indicate order for the user
            drawCallback: function(settings) {
                document.querySelectorAll('.cancel-job').forEach(el => {
                    el.removeEventListener('click', cancelJob)
                    el.addEventListener('click', cancelJob)
                })
            },
        });

        // Populate the state filter dropdown with the unique states present in the jobs queue
        const jobs_state_filter = document.getElementById('jobs-state-filter');
        const states = jobs_table.column(6).data().unique().sort().toArray();
        states.forEach(state => {
            if (state == null || state === '') return;
            const option = document.createElement('option');
            option.value = state;
            option.textContent = state;
            jobs_state_filter.appendChild(option);
        });
        jobs_state_filter.addEventListener('change', function() {
            // Exact-match search on the State column (anchored regex, no smart search)
            const value = this.value ? `^${this.value}$` : '';
            jobs_table.column(6).search(value, true, false).draw();
        });

        system_logs_rows = system_logs_data?.data ?? [];

        $('#system-logs-table').DataTable({
            data: systemLogTableRows(system_logs_rows, false),
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Title', render: function(el, type, row) {
                    if (row[5].length <= 1) return escapeString(el);
                    return `${escapeString(el)} <a class="ui small blue label toggle-log-group" title="Show all ${row[5].length} entries"><i class="ui caret right icon"></i>${row[5].length}&times;</a>`;
                }},
                { data: 2, title: 'Message', render: (el) => `<pre style="white-space:pre-wrap;max-height:500px; max-width:80vw;overflow:auto;margin:0">${escapeString(el)}</pre>`},
                { data: 3, title: 'Level', render: (el) => escapeString(el)},
                { data: 4, title: 'Created at', render: function(el, type, row) {
                    if (el == null) return '-';
                    if (row[5].length <= 1) return dateToYMD(new Date(el));
                    return `${dateToYMD(new Date(el))}<br><small>oldest: ${dateToYMD(new Date(row[5][row[5].length - 1][4]))}</small>`;
                }},
                { data: 0, title: '-', class: 'log-action', render: function(el, type, row) {
                    const log_ids = row[5].map((member) => member[0]);
                    const title = log_ids.length > 1 ? `Delete all ${log_ids.length} entries in this group` : 'Delete this entry';
                    return `<a class="delete-log" data-log-ids="${log_ids.join(',')}" title="${title}"><i class="ui large icon red times circle"></i></a>`;
                }},
            ],
            deferRender: true,
            order: [[4, 'desc']],
            drawCallback: function() {
                // a redraw re-renders the title cell, so point the caret back at the child row's actual state
                this.api().rows().every(function() {
                    const shown = this.child.isShown();
                    $(this.node()).find('.toggle-log-group i').toggleClass('down', shown).toggleClass('right', !shown);
                });
            },
        });

        // delegated, as group members are rendered into child rows that no drawCallback sees
        $('#system-logs-table').on('click', '.delete-log', deleteSystemLog);
        $('#system-logs-table').on('click', '.toggle-log-group', toggleSystemLogGroup);
        document.getElementById('system-logs-group-toggle').addEventListener('change', renderSystemLogs);

    })();
});
