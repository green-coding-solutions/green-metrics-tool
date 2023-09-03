$(document).ready(function () {
    $('#timeline-projects-table').DataTable({
        ajax: `${API_URL}/v1/timeline-projects`,
        columns: [
            { data: 0, title: 'ID'},
            { data: 1, title: 'Url'},
//            { data: 2, title: 'Categories'},
            { data: 3, title: 'Branch'},
            { data: 4, title: 'Filename'},
            { data: 6, title: 'Machine'},
            { data: 7, title: 'Schedule Mode'},
            { data: 8, title: 'Last Scheduled', render: (data) => data == null ? '-' : dateToYMD(new Date(data)) },
            { data: 9, title: 'Created At', render: (data) => data == null ? '-' : dateToYMD(new Date(data)) },
            { data: 10, title: 'Updated At', render: (data) => data == null ? '-' : dateToYMD(new Date(data)) },
            {
                data: 0,
                title: 'Timeline Link',
                render: function(name, type, row) {
                    return `<a href="/timeline.html?uri=${row[1]}&filename=${row[4]}&branch=${row[3]}&machine_id=${row[5]}">Show Timeline</a>`
                },
            },
            {
                data: 0,
                title: 'Show all measurements',
                render: function(name, type, row) {
                    return `<a href="/index.html?uri=${row[1]}&filename=${row[4]}&branch=${row[3]}&machine_id=${row[5]}">Show all measurements</a>`
                },
            },
/*            {
                data: 0,
                title: 'Badges',
                render: function(name, type, row) {
                    // iterate over the key metrics that shalle be displayed as badge
                    return `<div class="field">
                            <div class="header title">
                                <strong>${METRIC_MAPPINGS['cores_energy_powermetrics_component']['clean_name']}</strong> via
                                <strong>${METRIC_MAPPINGS['cores_energy_powermetrics_component']['source']}</strong>
                                 - ${`[COMPONENT]`}
                                <i data-tooltip="${METRIC_MAPPINGS['cores_energy_powermetrics_component']['explanation']}" data-position="bottom center" data-inverted>
                                    <i class="question circle icon link"></i>
                                </i>
                            </div>
                            <span class="energy-badge-container"><a href="/timeline.html?uri=${row[1]}&branch=${row[3] == null ? '': row[3]}&filename=${row[4] == null ? '': row[4]}&machine_id=${row[5]}"><img src="${API_URL}/v1/badge/timeline?uri=${row[1]}&branch=${row[3] == null ? '': row[3]}&filename=${row[4] == null ? '': row[4]}&machine_id=${row[5]}&metrics=${`cores_energy_powermetrics_component`}&detail_name=${`[COMPONENT]`}"></a></span>
                            <a href="#" class="copy-badge"><i class="copy icon"></i></a>
                        </div>
                        <p></p>`

                },
            },
*/


        ],
        deferRender: true,
        order: [] // API determines order
    });

});

