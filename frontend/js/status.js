async function cancelJob(e){
    e.preventDefault()
    const job_id = this.getAttribute('data-job-id');
    try {
        await makeAPICall('/v1/job', {job_id: job_id, action: 'cancel'}, null, true)
    } catch (err) {
        if (err == 'No data to display. API returned empty response (HTTP 204)') {
            const row = this.closest('tr');
            row.querySelector('.job-state').innerText = 'CANCELLED'
            row.querySelector('.job-action').innerHTML = '<i class="ui large icon grey minus"></i>'
            showNotification('Job cancelled', 'Job has been cancelled successfully');
        } else {
            showNotification('Could not cancel job', err);
        }
    }
    return false; // bc link click
};

$(document).ready(function () {
    (async () => {

        let machines_data = null;
        let jobs_data = null;

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

        $('#machines-table').DataTable({
            data: machines_data?.data,
            searching: false,
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Name'},
                { data: 2, title: 'Available', render: function(el) {
                    return (el == true) ? '<i class="ui label mini empty green circular"></i>': '<i class="ui label mini empty red circular"></i>';
                }},
                { data: 5, title: 'Jobs processing'},
                { data: 3, title: 'State', render: function(el) {
                    switch (el) {
                            case 'job_no': return `${el} <span data-inverted data-tooltip="No job currently in queue"><i class="ui question circle icon fluid"></i></span>`;
                            case 'job_start': return `${el} <span data-inverted data-tooltip="Current Job has started running"><i class="ui question circle icon fluid"></i></span>`;
                            case 'job_error': return `${el} <span data-inverted data-tooltip="Last job failed"></i></span>`;
                            case 'job_end': return `${el} <span data-inverted data-tooltip="Current job ended"></i></span>`;
                            case 'maintenance_start': return `${el} <span data-inverted data-tooltip="Maintenance after job has started"><i class="ui question circle icon fluid"></i></span>`;
                            case 'maintenance_end': return `${el} <span data-inverted data-tooltip="Maintenance after job has finished"><i class="ui question circle icon fluid"></i></span>`;
                            case 'measurement_control_start': return `${el} <span data-inverted data-tooltip="Periodic Measurement Control job has started"><i class="ui question circle icon fluid"></i></span>`;
                            case 'cooldown': return `${el} <span data-inverted data-tooltip="Machine is currently cooling down to base temperature"><i class="ui question circle icon fluid"></i></span>`;
                            case 'measurement_control_error': return `${el} <span data-inverted data-tooltip="Last periodic Measurement Control job has failed"><i class="ui question circle icon fluid"></i></span>`;
                            case 'measurement_control_end': return `${el} <span data-inverted data-tooltip="Periodic Measurement Control job has finished"><i class="ui question circle icon fluid"></i></span>`;
                            case undefined: // fallthrough
                            case null: return '-';
                    }
                    return el;
                }},
                { data: 6, title: 'GMT version', render: function(el, type, row) {
                    if (el == null) return '-';

                    return `<a href="https://github.com/green-coding-solutions/green-metrics-tool/commit/${el}" title="${dateToYMD(new Date(row[7]))}">${`${el.substr(0,3)}...${el.substr(-3,3)}`}</a>`;

                }},
                { data: 13, title: 'Details', render: function(el, type, row) {
                    return `<button class="ui icon button show-machine-configuration">
                              <i class="ui info icon"></i>
                              <span class="machine-configuration-details" style="display:none; ">${JSON.stringify(el, undefined, 2)}</span>
                            </button>`;
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
            //order: [[7, 'desc']] // API also orders, but we need to indicate order for the user
        });

        $('#jobs-table').DataTable({
            data: jobs_data?.data,
            columns: [
                { data: 0, title: 'ID'},
                { data: 2, title: 'Name', render: (name, type, row) => row[1] == null ? name : `<a href="/stats.html?id=${row[1]}">${name}</a>`  },
                { data: 3, title: 'Url'},
                {
                    data: 4,
                    title: 'Filename',
                    render: function(el, type, row) {
                        const usage_scenario_variables = Object.entries(row[5]).map(([k, v]) => `<span class="ui label">${k}=${v}</span>`);
                        return `${el} ${usage_scenario_variables.join(' ')}`
                    }},
                { data: 6, title: 'Branch'},
                { data: 7, title: 'Machine'},
                { data: 8, title: 'State', class: "job-state"},
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

    })();
});
