$(document).ready(function () {

    (async () => {
        let measurements = null;
        try {
            measurements = await makeAPICall('/v1/watchlist');
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }
        measurements.data.forEach(measurement => {
            let [id, name, image_url, repo_url, categories, branch, filename, machine_id, machine_description, schedule_mode, last_scheduled, created_at, updated_at, last_run, metrics] = measurement
            filename = filename == null ? '': filename
            branch = branch == null ? '': branch
            image_url = image_url == null ? '' : image_url;

            const chart_node = document.createElement("div")
            chart_node.classList.add('ui')
            chart_node.classList.add("card");

            const url_link = `${replaceRepoIcon(repo_url)} <a href="${repo_url}" target="_blank"><i class="icon external alternate"></i></a>`;
            let chart_node_html = `
                <div class="image">
                    <img src="${escapeString(image_url)}" onerror="this.src='/images/placeholder.webp'" loading="lazy">
                </div>
                <div class="content">
                    <div class="header">${name}</div>
                    <div class="meta">
                        <span>${url_link}</span>
                    </div>
                </div>
                <div class="content">
                    <p title="${created_at}"><b>Monitoring since: </b>${dateToYMD(new Date(created_at), true)}</p>
                    <p title="${branch}"><b>Branch: </b> ${branch == '' ? '-': branch}</p>
                    <p title="${filename}"><b>Filename: </b> ${filename == '' ? '-': filename}</p>
                    <p title="${machine_description}"><b>Machine: </b>${machine_description}</p>
                    <p title="${schedule_mode}"><b>Schedule Mode: </b>${schedule_mode}</p>
                    <p title="${last_run}"><b>Last Run: </b>${last_run == '' ? '-' : dateToYMD(new Date(last_run), false, true)}</p>

                    `

            DEFAULT_ENERGY_TIMELINE_BADGE_METRICS.forEach(metric => {
                const [metric_name, detail_name] = metric
                chart_node_html = `${chart_node_html}
                        <div class="field">
                            <strong>${getPretty(metric_name, 'clean_name')}</strong>
                            <i data-tooltip="${getPretty(metric_name, 'explanation')}" data-position="bottom center" data-inverted>
                                <i class="question circle icon link"></i>
                            </i><br>
                            <span class="energy-badge-container"><a href="${METRICS_URL}/timeline.html?uri=${repo_url}&branch=${branch}&filename=${filename}&machine_id=${machine_id}" target="_blank"><img src="${API_URL}/v1/badge/timeline?uri=${repo_url}&branch=${branch}&filename=${filename}&machine_id=${machine_id}&metric=${metric_name}&detail_name=${detail_name}&unit=joules" alt="${metric_name} badge" onerror="this.closest('.field').style.display='none'" loading="lazy"></a></span>
                        </div>`
            })

            chart_node_html = `${chart_node_html}
                </div>
                <a class="ui button blue" href="/timeline.html?uri=${repo_url}&filename=${filename}&branch=${branch}&machine_id=${machine_id}" target="_blank">
                    Show Timeline <i class="external alternate icon"></i>
                </a>
                <hr>
                <a class="ui button grey" href="/runs.html?uri=${repo_url}&filename=${filename}&branch=${branch}&machine_id=${machine_id}" target="_blank">
                    Show All Measurements <i class="external alternate icon"></i>
                </a>`
            chart_node.innerHTML = chart_node_html;
            document.querySelector('#scenario-runner-watchlist').appendChild(chart_node)
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
                                <strong>${getPretty('cores_energy_powermetrics_component', 'clean_name')}</strong> via
                                <strong>${getPretty('cores_energy_powermetrics_component', 'source')}</strong>
                                 - ${`[COMPONENT]`}
                                <i data-tooltip="${getPretty('cores_energy_powermetrics_component', 'explanation')}" data-position="bottom center" data-inverted>
                                    <i class="question circle icon link"></i>
                                </i>
                            </div>
                            <span class="energy-badge-container"><a href="/timeline.html?uri=${row[1]}&branch=${row[3] == null ? '': row[3]}&filename=${row[4] == null ? '': row[4]}&machine_id=${row[5]}"><img src="${API_URL}/v1/badge/timeline?uri=${row[1]}&branch=${row[3] == null ? '': row[3]}&filename=${row[4] == null ? '': row[4]}&machine_id=${row[5]}&metrics=${`cores_energy_powermetrics_component`}&detail_name=${`[COMPONENT]`}"></a></span>
                            <a class="copy-badge"><i class="copy icon"></i></a>
                        </div>
                        <p></p>`

                },
            },


        ],
        deferRender: true,
        order: [] // API determines order
    });

*/

