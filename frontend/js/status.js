$(document).ready(function () {
    (async () => {
        $('#jobs-table').DataTable({
            ajax: `${API_URL}/v1/jobs`,
            columns: [
                { data: 0, title: 'ID'},
                { data: 2, title: 'Name', render: (name, type, row) => row[1] == null ? name : `<a href="/stats.html?id=${row[1]}">${name}</a>`  },
                { data: 3, title: 'Url'},
                { data: 4, title: 'Filename'},
                { data: 5, title: 'Branch'},
                { data: 6, title: 'Machine'},
                { data: 7, title: 'State'},
                { data: 8, title: 'Last Update', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
                { data: 9, title: 'Created at', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
            ],
            deferRender: true,
            order: [[7, 'desc']] // API also orders, but we need to indicate order for the user
        });
        $('#machines-table').DataTable({
            ajax: `${API_URL}/v1/machines`,
            searching: false,
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Name'},
                { data: 2, title: 'Available', render: function(el) {
                    return (el == true) ? '<i class="ui label mini empty green circular"></i>': '<i class="ui label mini empty red circular"></i>';
                }},
                { data: 3, title: 'State', render: function(el) {
                    switch (el) {
                            case 'job_no': return `${el} <span data-inverted data-tooltip="No job currently in queue"><i class="ui question circle icon fluid"></i></div>`;
                            case 'job_start': return `${el} <span data-inverted data-tooltip="Current Job has started running"><i class="ui question circle icon fluid"></i></div>`;
                            case 'job_error': return `${el} <span data-inverted data-tooltip="Last job failed"></i></div>`;
                            case 'job_end': return `${el} <span data-inverted data-tooltip="Current job ended"></i></div>`;
                            case 'cleanup_start': return `${el} <span data-inverted data-tooltip="Cleanup after job has started"><i class="ui question circle icon fluid"></i></div>`;
                            case 'cleanup_end': return `${el} <span data-inverted data-tooltip="Cleanup after job has finished"><i class="ui question circle icon fluid"></i></div>`;
                            case 'measurement_control_start': return `${el} <span data-inverted data-tooltip="Periodic Measurement Control job has started"><i class="ui question circle icon fluid"></i></div>`;
                            case 'cooldown': return `${el} <span data-inverted data-tooltip="Machine is currently cooling down to base temperature"><i class="ui question circle icon fluid"></i></div>`;
                            case 'measurement_control_error': return `${el} <span data-inverted data-tooltip="Last periodic Measurement Control job has failed"><i class="ui question circle icon fluid"></i></div>`;
                            case 'measurement_control_end': return `${el} <span data-inverted data-tooltip="Periodic Measurement Control job has finished"><i class="ui question circle icon fluid"></i></div>`;
                            case undefined: // fallthrough
                            case null: return '-';
                    }
                    return el;
                }},
                { data: 4, title: 'State date', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
                { data: 5, title: 'Jobs processing'},
                { data: 6, title: 'GMT version', render: function(el, type, row) {
                    if (el == null) return '-';

                    return `<a href="https://github.com/green-coding-berlin/green-metrics-tool/commit/${el}">${`${el.substr(0,3)}...${el.substr(-3,3)}`}</a> (${dateToYMD(new Date(row[7]), true)})`;

                }},
                { data: 8, title: 'Base temp (°)'},
                { data: 9, title: 'Current temp (°)', render: (el) => el == null ? '-' : el},
                { data: 10, title: 'Cooldown time', render: function(el) {
                    return (el == null) ? 'awaiting info': `${Math.round(el/60)} Minutes`;
                }},
                { data: 11, title: 'Waiting Jobs'},
                { data: 12, title: 'Estimated waiting time', render: function(el, type, row) {
                    return (row[10] == null || row[12] == null) ? 'awaiting info' : `${Math.round(( (row[10]+row[12]) * row[11]) / 60)} Minutes`
                }},
            ],
            deferRender: true,
            //order: [[7, 'desc']] // API also orders, but we need to indicate order for the user
        });


    })();
});
