const createChartContainer = (container, el) => {
    const chart_node = document.createElement("div")
    chart_node.classList.add("card");
    chart_node.classList.add('statistics-chart-card')
    chart_node.classList.add('print-page-break')
    chart_node.classList.add('ui')

    chart_node.innerHTML = `
    <div class="content">
        <div class="description">
            <div class="statistics-chart" id=${el}-chart></div>
        </div>
    </div>`
    document.querySelector(container).appendChild(chart_node)

    return chart_node.querySelector('.statistics-chart');
}

const getEChartsOptions = () => {
    return {
        yAxis: { type: 'value', gridIndex: 0, name: "Run Energy" },

        xAxis: {type: "category", data: ["Time"]},
        series: [],
        title: { text: null },
        animation: false,
        legend: {
            data: [],
            bottom: 0,
            // type: 'scroll' // maybe active this if legends gets too long
        }
/*        toolbox: {
            itemSize: 25,
            top: 55,
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {}
            }
        },*/

    };
}


const getChartOptions = (measurements) => {
    const options = getEChartsOptions();
    options.title.text = `Workflow energy cost per run [mJ]`;

    const legend = new Set()
    const labels = []

    measurements.forEach(measurement => { // iterate over all measurements, which are in row order
        let [energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util, workflow_name, lat, lon, city, carbon_intensity_g, carbon_ug] = measurement;
        cpu_util = cpu_util ? cpu_util : '--';
        options.series.push({
            type: 'bar',
            smooth: true,
            stack: run_id,
            name: cpu,
            data: [energy_uj/1000000],
            itemStyle: {
                borderWidth: .5,
                borderColor: '#000000',
              },
        })
        legend.add(cpu)

        labels.push({
            energy_j: energy_uj/1000000,
            run_id: run_id,
            labels: [label],
            cpu_util: cpu_util,
            duration_s: duration_us/1000000,
            commit_hash: commit_hash,
            created_at: dateToYMD(new Date(created_at)),
            lat: lat,
            lon: lon,
            city: city,
            carbon_intensity_g: carbon_intensity_g,
            carbon_g: carbon_ug / 1000000
        })
    });

    options.legend.data = Array.from(legend)
    // set options.legend.selected to true for all cpus
    options.legend.selected = {}
    options.legend.data.forEach(cpu => {
        options.legend.selected[cpu] = true
    })

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${escapeString(labels[params.componentIndex].labels[params.dataIndex])}</strong><br>
                    run_id: ${escapeString(labels[params.componentIndex].run_id)}<br>
                    created_at: ${labels[params.componentIndex].created_at}<br>
                    commit_hash: ${escapeString(labels[params.componentIndex].commit_hash)}<br>
                    energy: ${escapeString(labels[params.componentIndex].energy_j)} J<br>
                    duration: ${escapeString(labels[params.componentIndex].duration_s)} seconds<br>
                    avg. cpu. utilization: ${escapeString(labels[params.componentIndex].cpu_util)}%<br>
                    location of run: ${escapeString(labels[params.componentIndex].city || 'N/A')}<br>
                    grid intensity: ${escapeString(labels[params.componentIndex].carbon_intensity_g || 'N/A')} g<br>
                    carbon: ${escapeString(labels[params.componentIndex].carbon_g || 'N/A')} g<br>
                    `;
        }
    };
    return options
}


const displayGraph = (chart_instance, measurements) => {

    const options = getChartOptions(measurements); // iterates
    chart_instance.clear();
    chart_instance.setOption(options);

    window.onresize = function () { // set callback when ever the user changes the viewport
        chart_instance.resize();
    }
}

const displayStatsTable = (stats) => {

    const total_table = document.querySelector("#label-stats-table-total");
    const avg_table = document.querySelector("#label-stats-table-avg");

    total_table.innerHTML = "";
    avg_table.innerHTML = "";

    const full_run_stats_avg_node = document.createElement("tr")
    full_run_stats_avg_node.innerHTML += `
                            <td class="bold td-index" data-tooltip="Averages for whole run" data-position="top left">Total run <i class="question circle icon small"></i> </td>
                            <td class="bold td-index">${numberFormatter.format(stats.totals[0]/1000000)} J (± ${numberFormatter.format(stats.totals[3])}%)</td>
                            <td class="bold td-index">${numberFormatter.format(stats.totals[4]/1000000)} s (± ${numberFormatter.format(stats.totals[7])}%)</td>
                            <td class="bold td-index">${numberFormatter.format(stats.totals[8])}% (± ${numberFormatter.format(stats.totals[11])}%%)</td>
                            <td class="bold td-index">${numberFormatter.format(stats.totals[12])} gCO2/kWh (± ${numberFormatter.format(stats.totals[15])}%)</td>
                            <td class="bold td-index">${numberFormatterLong.format(stats.totals[16]/1000000)} gCO2e (± ${numberFormatter.format(stats.totals[19])}%)</td>
                            <td class="bold td-index">${stats.totals[20]}</td>`;

    avg_table.appendChild(full_run_stats_avg_node);

    const full_run_stats_total_node = document.createElement("tr")
    full_run_stats_total_node.innerHTML += `
                            <td class="bold td-index" data-tooltip="Totals for whole run" data-position="top left">Per total run <i class="question circle icon small"></i> </td>
                            <td class="bold td-index">${numberFormatter.format(stats.totals[1]/1000000)} J</td>
                            <td class="bold td-index">${numberFormatter.format(stats.totals[5]/1000000)} s</td>
                            <td class="bold td-index">${numberFormatterLong.format(stats.totals[17]/1000000)} gCO2e</td>
                            <td class="bold td-index">${stats.totals[20]}</td>`;
    total_table.appendChild(full_run_stats_total_node)

    stats.per_label.forEach((row) =>{
        const label_stats_avg_node = document.createElement("tr")
        const label = row[21];
        label_stats_avg_node.innerHTML += `
                                        <td class="td-index" data-tooltip="Averages per step '${label}'"  data-position="top left">${label} <i class="question circle icon small"></i></td>
                                        <td class=" td-index">${numberFormatter.format(row[0]/1000000)} J (± ${numberFormatter.format(row[3])}%)</td>
                                        <td class=" td-index">${numberFormatter.format(row[4]/1000000)} s (± ${numberFormatter.format(row[7])}%)</td>
                                        <td class=" td-index">${numberFormatter.format(row[8])}% (± ${numberFormatter.format(row[11])}%%)</td>
                                        <td class=" td-index">${numberFormatter.format(row[12])} gCO2/kWh (± ${numberFormatter.format(row[15])}%)</td>
                                        <td class=" td-index">${numberFormatterLong.format(row[16]/1000000)} gCO2e (± ${numberFormatter.format(row[19])}%)</td>
                                        <td class="td-index">${row[20]}</td>`;

        avg_table.appendChild(label_stats_avg_node);

        const label_stats_total_node = document.createElement("tr")
        label_stats_total_node.innerHTML += `
                                        <td class="td-index" data-tooltip="Totals per step '${label}'"  data-position="top left">${label} <i class="question circle icon small"></i></td>
                                        <td class=" td-index">${numberFormatter.format(row[0]/1000000)} J (± ${numberFormatter.format(row[3])}%)</td>
                                        <td class=" td-index">${numberFormatter.format(row[4]/1000000)} s (± ${numberFormatter.format(row[7])}%)</td>
                                        <td class=" td-index">${numberFormatterLong.format(row[17]/1000000)} gCO2e (± ${numberFormatter.format(row[19])}%)</td>
                                        <td class="td-index">${row[20]}</td>`;
        total_table.appendChild(label_stats_total_node);

    }) ;

}

const displayRunDetailsTable = (measurements, repo) => {

    document.querySelector("#run-details-table").style.display = ''; // show
    document.querySelector("#ci-table").innerHTML = ''; // clear

    measurements.forEach(measurement => {
        const li_node = document.createElement("tr");

        let [energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util, workflow_name, lat, lon, city, carbon_intensity_g, carbon_ug] = measurement;

        const short_hash = commit_hash.substring(0, 7);
        const tooltip = `title="${commit_hash}"`;
        const cpu_avg = cpu_util ? cpu_util : '--';

        let run_link = '';

        const run_id_esc = escapeString(run_id)

        if(source == 'github') {
            run_link = `https://github.com/${repo}/actions/runs/${run_id_esc}`;
        }
        else if (source == 'gitlab') {
            run_link = `https://gitlab.com/${repo}/-/pipelines/${run_id_esc}`
        }

        const run_link_node = `<a href="${run_link}" target="_blank">${run_id_esc}</a>`
        let city_string = ''
        if (city){
            city_string = `${escapeString(city)} (${escapeString(lat)},${escapeString(lon)})`
        }

        li_node.innerHTML = `
                            <td class="td-index">${run_link_node}</td>\
                            <td class="td-index">${escapeString(label)}</td>\
                            <td class="td-index"><span title="${escapeString(created_at)}">${dateToYMD(new Date(created_at))}</span></td>\
                            <td class="td-index">${numberFormatter.format(energy_uj/1000000)} J</td>\
                            <td class="td-index">${escapeString(cpu)}</td>\
                            <td class="td-index">${escapeString(cpu_avg)}%</td>
                            <td class="td-index">${numberFormatter.format(duration_us/1000000)} s</td>
                            <td class="td-index" ${escapeString(tooltip)}>${escapeString(short_hash)}</td>\
                            <td class="td-index">${city_string}</td>
                            <td class="td-index">${escapeString(carbon_intensity_g)} gCO2/kWh</td>
                            <td class="td-index" title="${carbon_ug/1000000}">${escapeString(numberFormatterLong.format(carbon_ug/1000000))} gCO2e</td>
                            `;
        document.querySelector("#ci-table").appendChild(li_node);
    });
    $('table').tablesort();
}

const getBadges = async (repo, branch, workflow_id) => {
    try {
        const link_node = document.createElement("a")
        const img_node = document.createElement("img")
        img_node.src = `${API_URL}/v1/ci/badge/get?repo=${repo}&branch=${branch}&workflow=${workflow_id}`
        img_node.onerror = function() {this.src='/images/no-data-badge.webp'}
        link_node.href = '#'

        const energy_last = link_node.cloneNode(true)
        const energy_last_image = img_node.cloneNode(true)
        energy_last_image.onerror = function() {this.src='/images/no-data-badge.webp'}
        energy_last.appendChild(energy_last_image)

        const carbon_last = link_node.cloneNode(true)
        const carbon_last_image = img_node.cloneNode(true)
        carbon_last_image.src = `${carbon_last_image.src}&metric=carbon`
        carbon_last_image.onerror = function() {this.src='/images/no-data-badge.webp'}
        carbon_last.appendChild(carbon_last_image)

        const energy_totals = link_node.cloneNode(true)
        const energy_totals_image = img_node.cloneNode(true)
        energy_totals_image.src = `${energy_totals_image.src}&mode=totals`
        energy_totals_image.onerror = function() {this.src='/images/no-data-badge.webp'}
        energy_totals.appendChild(energy_totals_image)

        const carbon_totals = link_node.cloneNode(true)
        const carbon_totals_image = img_node.cloneNode(true)
        carbon_totals_image.src = `${carbon_totals_image.src}&mode=totals&metric=carbon`
        carbon_totals_image.onerror = function() {this.src='/images/no-data-badge.webp'}
        carbon_totals.appendChild(carbon_totals_image)

        const carbon_totals_monthly = link_node.cloneNode(true)
        const carbon_totals_monthly_image = img_node.cloneNode(true)
        carbon_totals_monthly_image.src = `${carbon_totals_monthly_image.src}&mode=totals&metric=carbon&duration_days=30`
        carbon_totals_monthly_image.onerror = function() {this.src='/images/no-data-badge.webp'}
        carbon_totals_monthly.appendChild(carbon_totals_monthly_image)

        const energy_totals_monthly = link_node.cloneNode(true)
        const energy_totals_monthly_image = img_node.cloneNode(true)
        energy_totals_monthly_image.src = `${energy_totals_monthly_image.src}&mode=totals&duration_days=30`
        energy_totals_monthly_image.onerror = function() {this.src='/images/no-data-badge.webp'}
        energy_totals_monthly.appendChild(energy_totals_monthly_image)


        document.querySelector("#energy-badge-container-last").appendChild(energy_last)
        document.querySelector("#energy-badge-container-totals").appendChild(energy_totals)
        document.querySelector("#carbon-badge-container-last").appendChild(carbon_last)
        document.querySelector("#carbon-badge-container-totals").appendChild(carbon_totals)

        document.querySelector("#energy-badge-container-totals-monthly").appendChild(energy_totals_monthly)
        document.querySelector("#carbon-badge-container-totals-monthly").appendChild(carbon_totals_monthly)

        document.querySelectorAll(".copy-badge").forEach(el => {el.addEventListener('click', copyToClipboard)})
    } catch (err) {
        showNotification('Could not get badge data from API', err);
    }
}

const getMeasurementsAndStats = async (repo, branch, workflow_id) => {
    const start_date = dateToYMD(new Date($('#rangestart input').val()), short=true);
    const end_date = dateToYMD(new Date($('#rangeend input').val()), short=true);

    const query_string=`repo=${repo}&branch=${branch}&workflow=${workflow_id}&start_date=${start_date}&end_date=${end_date}`;
    const [measurements, stats] = await Promise.all([
        makeAPICall(`/v1/ci/measurements?${query_string}`),
        makeAPICall(`/v1/ci/stats?${query_string}`)
    ]);

    history.pushState(null, '', `${window.location.origin}${window.location.pathname}?repo=${repo}&branch=${branch}&workflow=${workflow_id}&start_date=${start_date}&end_date=${end_date}`); // replace URL to bookmark!

    return [measurements, stats];
}

const bindRefreshButton = (repo, branch, workflow_id, chart_instance) => {
    // When the user selects a subset of the measurement data via the date-picker
    $('#submit').on('click', async function () {

        let measurements = null;
        let stats = null;
        try {
            [measurements, stats] = await getMeasurementsAndStats(repo, branch, workflow_id); // iterates I

        } catch (err) {
            showNotification('Could not get data from API', err);
            return; // abort
        }

        if (document.querySelector('#run-details-table').style.display != 'none') {
            displayRunDetailsTable(measurements.data, repo);
        }

        displayStatsTable(stats.data); //iterates II

        displayGraph(chart_instance, measurements.data)

        chart_instance.off('legendselectchanged') // remove
        // we need to re-bind the handler here and can also not really refactor that
        // without using a global variable. echarts .on does not allow to pass data to the handler
        chart_instance.on('legendselectchanged', function (params) {
            // get list of all legends that are on
            const selectedLegends = params.selected;
            const filteredMeasurements = measurements.data.filter(measurement => selectedLegends[measurement[4]]);
            // displayStatsTable(filteredMeasurements); -- this does not work anymore, as we are now fetching the data from the API
            // this decision was done as the JS code was very unmaintainable and SQL was far more readable. Performance was even though. Rework this if functionality needed
        });
    });
}


$(document).ready((e) => {
    (async () => {

        $('.ui.secondary.menu .item').tab(); // must happen very early so tab menu is not broken if return happens

        const url_params = getURLParams();

        let branch = escapeString(url_params['branch']);
        let repo = escapeString(url_params['repo']);
        let workflow_id = escapeString(url_params['workflow']);
        const ci_data_node = document.querySelector('#ci-data')

        if (repo == null || repo == '' || repo == 'null') {
            showNotification('No Repo', 'Repo parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }
        if (branch == null || branch == '' || branch == 'null') {
            showNotification('No Branch', 'Branch parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }
        if (workflow_id == null || workflow_id == '' || workflow_id == 'null') {
            showNotification('No Workflow', 'Workflow parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }

        const element = createChartContainer("#chart-container", "run-energy");
        const chart_instance = echarts.init(element);

        bindRefreshButton(repo, branch, workflow_id, chart_instance)

        ci_data_node.insertAdjacentHTML('afterbegin', `<tr><td><strong>Branch:</strong></td><td>${escapeString(url_params['branch'])}</td></tr>`)
        ci_data_node.insertAdjacentHTML('afterbegin', `<tr><td><strong>Workflow ID:</strong></td><td>${escapeString(workflow_id)}</td></tr>`)

        getBadges(repo, branch, workflow_id) // async

        dateTimePicker(7, url_params);

        let measurements = null;
        let stats = null;
        try {
            [measurements, stats] = await getMeasurementsAndStats(repo, branch, workflow_id)
        } catch (err) {
            showNotification('Could not get data from API', err);
            return; // abort
        }

        const source = measurements.data[0][8]
        let workflow_name = measurements.data[0][10]

        if (workflow_name == '' || workflow_name == null) {
            workflow_name = workflow_id ;
        }
        ci_data_node.insertAdjacentHTML('afterbegin', `<tr><td><strong>Workflow:</strong></td><td>${escapeString(workflow_name)}</td></tr>`)

        let repo_link = ''
        if(source == 'github') {
            repo_link = `https://github.com/${repo}`;
        }
        else if(source == 'gitlab') {
            repo_link = `https://gitlab.com/${repo}`;
        }

        const repo_link_node = `<a href="${repo_link}" target="_blank">${repo}</a>`
        ci_data_node.insertAdjacentHTML('afterbegin', `<tr><td><strong>Repository:</strong></td><td>${repo_link_node}</td></tr>`)


        displayGraph(chart_instance, measurements.data) // iterates I (total: 2)

        displayStatsTable(stats.data) // iterates II (total: 4)

        document.querySelector('#display-run-details-table').addEventListener('click', () => {
            document.querySelector('#api-loader').style.display = '';
            document.querySelector('#loader-question').remove();
            setTimeout(() => {displayRunDetailsTable(measurements.data, repo); document.querySelector('#api-loader').remove();}, 100); // we need to include a mini delay here, because otherwise the loader does not render, but is blocked by the hefty calculation
        });


        // On legend change, recalculate stats table
        chart_instance.on('legendselectchanged', function (params) {
            // get list of all legends that are on
            const selectedLegends = params.selected;
            const filteredMeasurements = measurements.data.filter(measurement => selectedLegends[measurement[4]]);
            // displayStatsTable(filteredMeasurements); -- this does not work anymore, as we are now fetching the data from the API
            // this decision was done as the JS code was very unmaintainable and SQL was far more readable. Performance was even though. Rework this if functionality needed
        });

        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
    })();
});
