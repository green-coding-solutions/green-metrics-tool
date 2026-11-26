"use strict";
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


// NULL means unknown and is never shown as 0: no value is '--', no deviation (e.g. a single run) shows no ±
const formatStat = (value, unit, stddev = null, formatter = numberFormatter) => (value == null) ? '--' : `${formatter.format(value)}${unit}${(stddev == null) ? '' : ` (± ${numberFormatter.format(stddev)}%)`}`;
const fromMicro = (value) => (value == null) ? null : value/1000000; // null must stay null, so that formatStat shows '--' instead of 0
const formatCarbonUg = (ug, stddev = null) => formatStat((ug == null) ? null : ug/1000000, ' gCO2e', stddev, numberFormatterLong);
const carbonTitle = (ug) => (ug == null) ? 'data missing' : ug/1000000; // exact value in g for cell tooltips

const getChartOptions = (measurements) => {
    const options = getEChartsOptions();
    options.title.text = `Workflow energy cost per run [J]`;

    const legend = new Set()
    const labels = []

    measurements.forEach(measurement => { // iterate over all measurements, which are in row order
        let [energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util, workflow_name, lat, lon, city, carbon_intensity_g, operational_carbon_ug, embodied_carbon_ug, _note, total_carbon_ug] = measurement;
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
            duration_s: fromMicro(duration_us) ?? '--',
            commit_hash: commit_hash,
            created_at: dateToYMD(new Date(created_at)),
            lat: lat,
            lon: lon,
            city: city,
            carbon_intensity_g: carbon_intensity_g,
            operational_carbon: formatCarbonUg(operational_carbon_ug),
            embodied_carbon: formatCarbonUg(embodied_carbon_ug),
            total_carbon: formatCarbonUg(total_carbon_ug),
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
                    commit_hash: ${escapeString(labels[params.componentIndex].commit_hash ?? '--')}<br>
                    energy: ${escapeString(labels[params.componentIndex].energy_j)} J<br>
                    duration: ${escapeString(labels[params.componentIndex].duration_s)} seconds<br>
                    avg. cpu. utilization: ${escapeString(labels[params.componentIndex].cpu_util)}%<br>
                    location of run: ${escapeString(labels[params.componentIndex].city || 'N/A')}<br>
                    grid intensity: ${escapeString(labels[params.componentIndex].carbon_intensity_g || 'N/A')} g<br>
                    operational carbon: ${escapeString(labels[params.componentIndex].operational_carbon)}<br>
                    embodied carbon: ${escapeString(labels[params.componentIndex].embodied_carbon)}<br>
                    total carbon: ${escapeString(labels[params.componentIndex].total_carbon)}<br>
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
                            <td class="bold td-index">${formatStat(fromMicro(stats.totals[0]), ' J', stats.totals[3])}</td>
                            <td class="bold td-index">${formatStat(fromMicro(stats.totals[4]), ' s', stats.totals[7])}</td>
                            <td class="bold td-index">${formatStat(stats.totals[8], '%', stats.totals[11])}</td>
                            <td class="bold td-index">${formatStat(stats.totals[12], ' gCO2/kWh', stats.totals[15])}</td>
                            <td class="bold td-index">${formatCarbonUg(stats.totals[16], stats.totals[19])}</td>
                            <td class="bold td-index">${formatCarbonUg(stats.totals[20], stats.totals[23])}</td>
                            <td class="bold td-index">${formatCarbonUg(stats.totals[24], stats.totals[27])}</td>
                            <td class="bold td-index">${stats.totals[28]}</td>`;

    avg_table.appendChild(full_run_stats_avg_node);

    const full_run_stats_total_node = document.createElement("tr")
    full_run_stats_total_node.innerHTML += `
                            <td class="bold td-index" data-tooltip="Totals for whole run" data-position="top left">Per total run <i class="question circle icon small"></i> </td>
                            <td class="bold td-index">${formatStat(fromMicro(stats.totals[1]), ' J')}</td>
                            <td class="bold td-index">${formatStat(fromMicro(stats.totals[5]), ' s')}</td>
                            <td class="bold td-index">${formatCarbonUg(stats.totals[17])}</td>
                            <td class="bold td-index">${formatCarbonUg(stats.totals[21])}</td>
                            <td class="bold td-index">${formatCarbonUg(stats.totals[25])}</td>
                            <td class="bold td-index">${stats.totals[28]}</td>`;
    total_table.appendChild(full_run_stats_total_node)

    stats.per_label.forEach((row) =>{
        const label_stats_avg_node = document.createElement("tr")
        const label = row[29];
        label_stats_avg_node.innerHTML += `
                                        <td class="td-index" data-tooltip="Averages per step '${escapeString(label)}'"  data-position="top left">${escapeString(label)} <i class="question circle icon small"></i></td>
                                        <td class=" td-index">${formatStat(fromMicro(row[0]), ' J', row[3])}</td>
                                        <td class=" td-index">${formatStat(fromMicro(row[4]), ' s', row[7])}</td>
                                        <td class=" td-index">${formatStat(row[8], '%', row[11])}</td>
                                        <td class=" td-index">${formatStat(row[12], ' gCO2/kWh', row[15])}</td>
                                        <td class=" td-index">${formatCarbonUg(row[16], row[19])}</td>
                                        <td class=" td-index">${formatCarbonUg(row[20], row[23])}</td>
                                        <td class=" td-index">${formatCarbonUg(row[24], row[27])}</td>
                                        <td class="td-index">${row[28]}</td>`;

        avg_table.appendChild(label_stats_avg_node);

        const label_stats_total_node = document.createElement("tr")
        label_stats_total_node.innerHTML += `
                                        <td class="td-index" data-tooltip="Totals per step '${escapeString(label)}'"  data-position="top left">${escapeString(label)} <i class="question circle icon small"></i></td>
                                        <td class=" td-index">${formatStat(fromMicro(row[1]), ' J')}</td>
                                        <td class=" td-index">${formatStat(fromMicro(row[5]), ' s')}</td>
                                        <td class=" td-index">${formatCarbonUg(row[17])}</td>
                                        <td class=" td-index">${formatCarbonUg(row[21])}</td>
                                        <td class=" td-index">${formatCarbonUg(row[25])}</td>
                                        <td class="td-index">${row[28]}</td>`;
        total_table.appendChild(label_stats_total_node);

    }) ;
    $('#stats-container table').tablesort();
    $('#stats-container table thead th[data-sort="numeric"]').data('sortBy', function(th, td, tablesort) {
        return parseFloat(td.text().replace(',', ''));
    });


}

const displayRunDetailsTable = (measurements, repo) => {

    document.querySelector("#run-details-table").style.display = ''; // show
    document.querySelector("#ci-table").innerHTML = ''; // clear

    measurements.forEach(measurement => {
        const li_node = document.createElement("tr");

        let [energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util, workflow_name, lat, lon, city, carbon_intensity_g, operational_carbon_ug, embodied_carbon_ug, note, total_carbon_ug] = measurement;

        const short_hash = (commit_hash == null) ? '--' : commit_hash.substring(0, 7); // commit_hash is nullable in ci_measurements
        const cpu_avg = cpu_util ? cpu_util : '--';

        let run_link = '';

        const run_id_esc = encodeURIComponent(run_id)
        const repo_encoded = repo.split('/').map(encodeURIComponent).join('/');

        if(source == 'github') {
            run_link = `https://github.com/${repo_encoded}/actions/runs/${run_id_esc}`;
        }
        else if (source == 'gitlab') {
            run_link = `https://gitlab.com/${repo_encoded}/-/pipelines/${run_id_esc}`;
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
                            <td class="td-index">${formatStat(fromMicro(duration_us), ' s')}</td>
                            <td class="td-index" title="${escapeString(commit_hash ?? '--')}">${escapeString(short_hash)}</td>\
                            <td class="td-index">${city_string}</td>
                            <td class="td-index">${escapeString(carbon_intensity_g)} gCO2/kWh</td>
                            <td class="td-index" title="${carbonTitle(operational_carbon_ug)}">${escapeString(formatCarbonUg(operational_carbon_ug))}</td>
                            <td class="td-index" title="${carbonTitle(embodied_carbon_ug)}">${escapeString(formatCarbonUg(embodied_carbon_ug))}</td>
                            <td class="td-index" title="${carbonTitle(total_carbon_ug)}">${escapeString(formatCarbonUg(total_carbon_ug))}</td>
                            <td class="td-index">${ (note == null) ? '' : `<span class="ui icon" data-position="top right" data-inverted="" data-tooltip="${escapeString(note)}"><i class="ui question circle icon fluid"></i></span>` }</td>

                            `;
        document.querySelector("#ci-table").appendChild(li_node);
    });
    $('#run-details-table table').tablesort();
    $('#run-details-table table thead th[data-sort="numeric"]').data('sortBy', function(th, td, tablesort) {
        return parseFloat(td.text().replace(',', ''));
    });

}

const getBadges = async (repo, branch, workflow_id) => {
    try {
        const link_node = document.createElement("a")
        const img_node = document.createElement("img")
        img_node.src = `${API_URL}/v1/ci/badge/get?repo=${encodeURIComponent(repo)}&branch=${encodeURIComponent(branch)}&workflow=${encodeURIComponent(workflow_id)}`
        img_node.onerror = function() {this.src='/images/no-data-badge.webp'}
        link_node.href = `${METRICS_URL}/ci.html?repo=${encodeURIComponent(repo)}&branch=${encodeURIComponent(branch)}&workflow=${encodeURIComponent(workflow_id)}`
        link_node.rel = 'noopener'
        link_node.target = '_blank'

        const appendBadge = (container_id, query_params) => {
            const link = link_node.cloneNode(true)
            const image = img_node.cloneNode(true)
            image.src = `${image.src}${query_params}`
            image.onerror = function() {this.src='/images/no-data-badge.webp'}
            link.appendChild(image)
            document.querySelector(`#${container_id}`).appendChild(link)
        }

        appendBadge('energy-badge-container-last', '')
        appendBadge('energy-badge-container-totals', '&mode=totals')
        appendBadge('energy-badge-container-totals-monthly', '&mode=totals&duration_days=30')

        for (const [prefix, metric] of [['carbon', 'carbon'], ['operational-carbon', 'operational_carbon'], ['embodied-carbon', 'embodied_carbon']]) {
            appendBadge(`${prefix}-badge-container-last`, `&metric=${metric}`)
            appendBadge(`${prefix}-badge-container-totals`, `&mode=totals&metric=${metric}`)
            appendBadge(`${prefix}-badge-container-totals-monthly`, `&mode=totals&metric=${metric}&duration_days=30`)
        }

        document.querySelectorAll(".copy-badge").forEach(el => {el.addEventListener('click', copyToClipboard)})
    } catch (err) {
        showNotification('Could not get badge data from API', err);
    }
}

const getMeasurementsAndStats = async (repo, branch, workflow_id, start_date, end_date) => {

    const query_string=`repo=${encodeURIComponent(repo)}&branch=${encodeURIComponent(branch)}&workflow=${encodeURIComponent(workflow_id)}&start_date=${start_date}&end_date=${end_date}`;
    const [measurements, stats] = await Promise.all([
        makeAPICall(`/v2/ci/measurements?${query_string}`),
        makeAPICall(`/v2/ci/stats?${query_string}`)
    ]);

    return [measurements, stats];
}

const refreshView = async (repo, branch, workflow_id, chart_instance) => {

    const start_date = dateToYMD(new Date($('#rangestart input').val()), true);
    const end_date = dateToYMD(new Date($('#rangeend input').val()), true);

    let measurements = null;
    let stats = null;
    try {
        [measurements, stats] = await getMeasurementsAndStats(repo, branch, workflow_id, start_date, end_date); // iterates I
        document.querySelectorAll('.container-no-data').forEach(el => el.style.display = '')
        document.querySelector('#message-no-data').style.display = 'none';

    } catch (err) {
        if (err instanceof APIHTTPError && err.status === 204) {
            document.querySelectorAll('.container-no-data').forEach(el => el.style.display = 'none')
            document.querySelector('#message-no-data').style.display = '';
            return
        } else {
            showNotification('Could not get data from API', err);
            return; // abort
        }
    }

    history.pushState(null, '', `${window.location.origin}${window.location.pathname}?repo=${encodeURIComponent(repo)}&branch=${encodeURIComponent(branch)}&workflow=${encodeURIComponent(workflow_id)}&start_date=${start_date}&end_date=${end_date}`); // replace URL to bookmark!

    const source = measurements.data[0][7];
    let workflow_name = measurements.data[0][9];
    populateRunInfos(repo, branch, source, workflow_name, workflow_id)

    $('#display-run-details-table').off('click');
    $('#display-run-details-table').on('click', () => {
        document.querySelector('#api-loader').classList.remove('hidden');
        document.querySelector('#loader-question').remove();
        setTimeout(() => {displayRunDetailsTable(measurements?.data, repo); document.querySelector('#api-loader').remove();}, 100); // we need to include a mini delay here, because otherwise the loader does not render, but is blocked by the hefty calculation
    });

    if (document.querySelector('#run-details-table').style.display != 'none') {
        displayRunDetailsTable(measurements.data, repo);
    }

    displayStatsTable(stats.data); //iterates II
    displayGraph(chart_instance, measurements.data)

    chart_instance.off('legendselectchanged');

    chart_instance.on('legendselectchanged', (params) => {
        // get list of all legends that are on
        const selectedLegends = params.selected;
        const filteredMeasurements = measurements.data.filter(measurement => selectedLegends[measurement[4]]);
        // displayStatsTable(filteredMeasurements); -- this does not work anymore, as we are now fetching the data from the API
        // this decision was done as the JS code was very unmaintainable and SQL was far more readable. Performance was even though. Rework this if functionality needed
    });

    setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
}

const populateRunInfos = async (repo, branch, source, workflow_name, workflow_id) => {

    document.querySelector('#ci-data-branch').innerText =  branch;
    document.querySelector('#ci-data-workflow-id').innerText =  workflow_id;

    if (workflow_name == '' || workflow_name == null) {
        workflow_name = workflow_id ;
    }
    document.querySelector('#ci-data-workflow').innerText =  workflow_name;

    let repo_link = ''
    const repo_encoded = repo.split('/').map(encodeURIComponent).join('/');
    if(source == 'github') {
        repo_link = `https://github.com/${repo_encoded}`;
    }
    else if(source == 'gitlab') {
        repo_link = `https://gitlab.com/${repo_encoded}`;
    }

    const repo_link_node = `<a href="${repo_link}" target="_blank">${escapeString(repo)}</a>`
    document.querySelector('#ci-data-repo').innerHTML =  repo_link_node;
}


$(document).ready((e) => {
    (async () => {

        $('.ui.secondary.menu .item').tab(); // must happen very early so tab menu is not broken if return happens

        const url_params = getURLParams();

        // raw values. Escaping / encoding happens where they are used (HTML vs. URL)
        const branch = url_params['branch'];
        const repo = url_params['repo'];
        const workflow_id = url_params['workflow'];

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

        dateTimePicker(7, url_params);
        getBadges(repo, branch, workflow_id) // async

        refreshView(repo, branch, workflow_id, chart_instance)

        $('#submit').on('click', async function () {
            refreshView(repo, branch, workflow_id, chart_instance)

        });

    })();
});
