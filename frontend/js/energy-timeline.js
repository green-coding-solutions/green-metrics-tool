$(document).ready(function () {

    (async () => {
        try {
            var measurements = await makeAPICall('/v1/timeline-projects');
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }
        measurements.data.forEach(measurement => {
            let [id, name, url, categories, branch, filename, machine_id, machine_description, schedule_mode, last_scheduled, created_at, updated_at, last_run, metrics] = measurement
            filename = filename == null ? '': filename
            branch = branch == null ? '': branch

            const chart_node = document.createElement("div")
            chart_node.classList.add("card");
            chart_node.classList.add('ui')
            chart_node.classList.add('wide')

            const url_link = `${replaceRepoIcon(url)} <a href="${url}" target="_blank"><i class="icon external alternate"></i></a>`;
            chart_node.innerHTML = `
                <div class="content">
                    <div class="header">${name}</div>
                    <div class="meta">
                        <span>${url_link}</span>
                    </div>
                </div>
                <div class="content">
                    <p><b>Monitoring since: </b>${dateToYMD(new Date(created_at), true)}</p>
                    <p><b>Branch: </b> ${branch == '' ? '-': branch}</p>
                    <p><b>Filename: </b> ${filename == '' ? '-': filename}</p>
                    <p><b>Machine: </b>${machine_description}</p>
                    <p><b>Schedule Mode: </b>${schedule_mode}</p>
                    <p><b>Last Run: </b>${last_run == '' ? '-' : dateToYMD(new Date(last_run))}</p>
                    `

            DEFAULT_ENERGY_TIMELINE_BADGE_METRICS.forEach(metric => {
                const [metric_name, detail_name] = metric
                chart_node.innerHTML = `${chart_node.innerHTML}
                <fieldset style="border:none;">
                        <div class="field">
                            <div class="header title">
                                <strong>${METRIC_MAPPINGS[metric_name]['clean_name']}</strong> via
                                <strong>${METRIC_MAPPINGS[metric_name]['source']}</strong>
                                 - ${detail_name}
                                <i data-tooltip="${METRIC_MAPPINGS[metric_name]['explanation']}" data-position="bottom center" data-inverted>
                                    <i class="question circle icon link"></i>
                                </i>
                            </div>
                            <span class="energy-badge-container"><a href="${METRICS_URL}/timeline.html?uri=${url}&branch=${branch}&filename=${filename}&machine_id=${machine_id}" target="_blank"><img src="${API_URL}/v1/badge/timeline?uri=${url}&branch=${branch}&filename=${filename}&machine_id=${machine_id}&metrics=${metric_name}&detail_name=${detail_name}" alt="Image Failed to Load" onerror="this.closest('.field').style.display='none'"></a></span>
                            <a href="#" class="copy-badge"><i class="copy icon"></i></a>
                        </div>
                        </div>
                        <p></p><hr>`
            })

            chart_node.innerHTML = `${chart_node.innerHTML}
                </div>
		<hr>
                <a class="ui button blue" href="/timeline.html?uri=${url}&filename=${filename}&branch=${branch}&machine_id=${machine_id}" target="_blank">
                    Show Timeline <i class="external alternate icon"></i>
                </a>
                <hr>
                <a class="ui button grey" href="/index.html?uri=${url}&filename=${filename}&branch=${branch}&machine_id=${machine_id}" target="_blank">
                    Show All Measurements <i class="external alternate icon"></i>
                </a>`

            document.querySelector('#timeline-cards').appendChild(chart_node)
        });
        document.querySelectorAll(".copy-badge").forEach(el => {
            el.addEventListener('click', copyToClipboard)
        })

    })();
});


/*
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
            { data: 8, title: 'Last Scheduled', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
            { data: 9, title: 'Created At', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
            { data: 10, title: 'Updated At', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
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
            {
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


        ],
        deferRender: true,
        order: [] // API determines order
    });

*/

