const numberFormatter = new Intl.NumberFormat('en-US', {
  style: 'decimal',
  maximumFractionDigits: 2,
});

const numberFormatterLong = new Intl.NumberFormat('en-US', {
  style: 'decimal',
  maximumFractionDigits: 4,
});

const calculateStats = (energy_measurements, carbon_ug_measurements, carbon_intensity_g_measurements, duration_us_measurements, cpu_util_measurements) => {

    let energy_avg = energy_stddev = energy_stddev_rel = energy_sum = '--'
    let duration_us_avg = duration_us_stddev = duration_us_stddev_rel = duration_us_sum = '--'
    let carbon_ug_avg = carbon_ug_stddev = carbon_ug_stddev_rel = carbon_ug_sum ='--'
    let carbon_intensity_g_avg = carbon_intensity_g_stddev = carbon_intensity_g_stddev_rel = '--'
    let cpuUtil_stddev = cpuUtil_avg = cpuUtil_stddev_rel = '--'

    if (energy_measurements.length > 0) {
        [energy_avg, energy_stddev, energy_sum, energy_stddev_rel] = calculateStatistics(energy_measurements)
    }
    if (duration_us_measurements.length > 0) {
        [duration_us_avg, duration_us_stddev, duration_us_sum, duration_us_stddev_rel] = calculateStatistics(duration_us_measurements)
    }
    if (carbon_ug_measurements.length > 0) {
        [carbon_ug_avg, carbon_ug_stddev, carbon_ug_sum, carbon_ug_stddev_rel] = calculateStatistics(carbon_ug_measurements)
    }

    // intentially skipping carbon_intensity_g_sum
    if (carbon_intensity_g_measurements.length > 0) {
        [carbon_intensity_g_avg, carbon_intensity_g_stddev, , carbon_intensity_g_stddev_rel] = calculateStatistics(carbon_intensity_g_measurements)
    }

    // intentially skipping cpuUtil_sum
    if (cpu_util_measurements.length > 0) {
        [cpuUtil_avg, cpuUtil_stddev, , cpuUtil_stddev_rel] = calculateStatistics(cpu_util_measurements)
    }

    return {
        energy_uj: {
            avg: energy_avg,
            stddev: energy_stddev,
            stddev_rel: energy_stddev_rel,
            total: energy_sum
        },
        duration_us: {
            avg: duration_us_avg,
            stddev: duration_us_stddev,
            stddev_rel: duration_us_stddev_rel,
            total: duration_us_sum
        },
        carbon_ug: {
            avg: carbon_ug_avg,
            stddev: carbon_ug_stddev,
            stddev_rel: carbon_ug_stddev_rel,
            total: carbon_ug_sum
        },
        carbon_intensity_g: {
            avg: carbon_intensity_g_avg,
            stddev: carbon_intensity_g_stddev,
            stddev_rel: carbon_intensity_g_stddev_rel
        },
        cpu_util: {
            avg: cpuUtil_avg,
            stddev: cpuUtil_stddev,
            stddev_rel: cpuUtil_stddev_rel
        },
    };
};

const createStatsArrays = (measurements) => {  // iterates 2n times (1 full, 1 by run ID)
    const measurementsByRun = {}
    const measurementsByLabel = {}

    const measurementsForFullRun = {
        energy_uj: [],
        carbon_ug: [],
        carbon_intensity_g: [],
        duration_us: [],
        cpu_util: [],
        count: 0
    };

    measurements.forEach(measurement => {
        let [energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util, workflow_name, lat, lon, city, carbon_intensity_g, carbon_ug] = measurement;

        if (!measurementsByLabel[label]) {
            measurementsByLabel[label] = {
                energy_uj: [],
                carbon_ug: [],
                carbon_intensity_g: [],
                duration_us: [],
                cpu_util: [],
                count: 0
            };
        }
        if (!measurementsByRun[run_id]) {
            measurementsByRun[run_id] = {
                energy_uj: [],
                carbon_ug: [],
                carbon_intensity_g: [],
                duration_us: [],
                cpu_util: []
            };
        }

        if (energy_uj != null) {
            measurementsByLabel[label].energy_uj.push(energy_uj);
            measurementsByRun[run_id].energy_uj.push(energy_uj);
        }
        if (duration_us != null) {
            measurementsByLabel[label].duration_us.push(duration_us);
            measurementsByRun[run_id].duration_us.push(duration_us);
        }
        if (cpu_util != null) {
            measurementsByLabel[label].cpu_util.push(cpu_util);
            measurementsByRun[run_id].cpu_util.push(cpu_util);
        }
        if (carbon_ug != null) {
            measurementsByLabel[label].carbon_ug.push(carbon_ug);
            measurementsByRun[run_id].carbon_ug.push(carbon_ug);
        }
        if (carbon_intensity_g != null) {
            measurementsByLabel[label].carbon_intensity_g.push(carbon_intensity_g);
            measurementsByRun[run_id].carbon_intensity_g.push(carbon_intensity_g);
        }
        measurementsByLabel[label].count += 1;
        measurementsForFullRun.count += 1;
    });



   for (const run_id in measurementsByRun) {
        if (measurementsByRun[run_id].energy_uj) measurementsForFullRun.energy_uj.push(measurementsByRun[run_id].energy_uj);
        if (measurementsByRun[run_id].carbon_ug) measurementsForFullRun.carbon_ug.push(measurementsByRun[run_id].carbon_ug);
        if (measurementsByRun[run_id].duration_us) measurementsForFullRun.duration_us.push(measurementsByRun[run_id].duration_us);
        if (measurementsByRun[run_id].cpu_util) measurementsForFullRun.cpu_util.push(measurementsByRun[run_id].cpu_util);
        if (measurementsByRun[run_id].carbon_intensity_g) measurementsForFullRun.carbon_intensity_g.push(measurementsByRun[run_id].carbon_intensity_g);
    }

    return [measurementsForFullRun, measurementsByLabel];

}

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
    chart_instance.setOption(options);

    window.onresize = function () { // set callback when ever the user changes the viewport
        chart_instance.resize();
    }
}

const displayStatsTable = (measurements) => {
    const [fullRunArray, labelsArray] = createStatsArrays(measurements); // iterates 2n times

    const total_table = document.querySelector("#label-stats-table-total");
    const avg_table = document.querySelector("#label-stats-table-avg");

    total_table.innerHTML = "";
    avg_table.innerHTML = "";

    const full_run_stats = calculateStats(fullRunArray.energy_uj.flat(), fullRunArray.carbon_ug.flat(), fullRunArray.carbon_intensity_g.flat(), fullRunArray.duration_us.flat(), fullRunArray.cpu_util.flat())

    const full_run_stats_avg_node = document.createElement("tr")
    full_run_stats_avg_node.innerHTML += `
                            <td class="td-index" data-tooltip="Stats for the series of runs (labels aggregated for each pipeline run)" data-position="top left">All steps <i class="question circle icon small"></i> </td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.energy_uj.avg/1000000)} J (± ${numberFormatter.format(full_run_stats.energy_uj.stddev_rel)}%)</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.duration_us.avg/1000000)} s (± ${numberFormatter.format(full_run_stats.duration_us.stddev_rel)}%)</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.cpu_util.avg)}% (± ${numberFormatter.format(full_run_stats.cpu_util.stddev_rel)}%%)</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.carbon_intensity_g.avg)} gCO2/kWh (± ${numberFormatter.format(full_run_stats.carbon_intensity_g.stddev_rel)}%)</td>
                            <td class="td-index">${numberFormatterLong.format(full_run_stats.carbon_ug.avg/1000000)} gCO2e (± ${numberFormatter.format(full_run_stats.carbon_ug.stddev_rel)}%)</td>
                            <td class="td-index">${numberFormatter.format(fullRunArray.count)}</td>`;

    avg_table.appendChild(full_run_stats_avg_node);

    const full_run_stats_total_node = document.createElement("tr")
    full_run_stats_total_node.innerHTML += `
                            <td class="td-index" data-tooltip="Stats for the series of runs (labels aggregated for each pipeline run)" data-position="top left">All steps <i class="question circle icon small"></i> </td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.energy_uj.total/1000000)} J</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.duration_us.total/1000000)} s</td>
                            <td class="td-index">${numberFormatterLong.format(full_run_stats.carbon_ug.total/1000000)} gCO2e</td>
                            <td class="td-index">${numberFormatter.format(fullRunArray.count)}</td>`;
    total_table.appendChild(full_run_stats_total_node)

    for (const label in labelsArray) {
        const label_stats = calculateStats(labelsArray[label].energy_uj, labelsArray[label].carbon_ug, labelsArray[label].carbon_intensity_g, labelsArray[label].duration_us, labelsArray[label].cpu_util)
        const label_stats_avg_node = document.createElement("tr")
        label_stats_avg_node.innerHTML += `
                                        <td class="td-index" data-tooltip="stats for the series of steps represented by the ${label} label"  data-position="top left">${label} <i class="question circle icon small"></i></td>
                                        <td class="td-index">${numberFormatter.format(label_stats.energy_uj.avg/1000000)} J (± ${numberFormatter.format(label_stats.energy_uj.stddev_rel)}%)</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.duration_us.avg/1000000)} s (± ${numberFormatter.format(label_stats.duration_us.stddev_rel)}%)</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.cpu_util.avg)}% (± ${numberFormatter.format(label_stats.cpu_util.stddev_rel)}%%)</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.carbon_intensity_g.avg)} gCO2/kWh (± ${numberFormatter.format(label_stats.carbon_intensity_g.stddev_rel)}%)</td>
                                        <td class="td-index">${numberFormatterLong.format(label_stats.carbon_ug.avg/1000000)} gCO2e (± ${numberFormatter.format(label_stats.carbon_ug.stddev_rel)}%)</td>
                                        <td class="td-index">${numberFormatter.format(labelsArray[label].count)}</td>`;

        avg_table.appendChild(label_stats_avg_node);

        const label_stats_total_node = document.createElement("tr")
        label_stats_total_node.innerHTML += `
                                        <td class="td-index" data-tooltip="stats for the series of steps represented by the ${label} label"  data-position="top left">${label} <i class="question circle icon small"></i></td>
                                        <td class="td-index">${numberFormatter.format(label_stats.energy_uj.total/1000000)} J</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.duration_us.total/1000000)} s</td>
                                        <td class="td-index">${numberFormatterLong.format(label_stats.carbon_ug.total/1000000)} gCO2e</td>
                                        <td class="td-index">${numberFormatter.format(labelsArray[label].count)}</td>`;
        total_table.appendChild(label_stats_total_node);

    };
}

const displayCITable = (measurements, repo) => {

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


function dateTimePicker() {
    $('#rangestart').calendar({
        type: 'date',
        endCalendar: $('#rangeend')
    });
    $('#rangeend').calendar({
        type: 'date',
        startCalendar: $('#rangestart')
    });
}

const getLastRunBadge = async (repo, branch, workflow_id) => {
    try {
        const link_node = document.createElement("a")
        const img_node = document.createElement("img")
        img_node.src = `${API_URL}/v1/ci/badge/get?repo=${repo}&branch=${branch}&workflow=${workflow_id}`
        link_node.href = window.location.href
        link_node.appendChild(img_node)
        document.querySelector("span.energy-badge-container").appendChild(link_node)
        document.querySelector(".copy-badge").addEventListener('click', copyToClipboard)
    } catch (err) {
        showNotification('Could not get badge data from API', err);
    }
}

const getMeasurements = async (repo, branch, workflow_id, start_date = null, end_date = null) => {
    if(end_date == null) end_date = dateToYMD(new Date(), short=true);
    if(start_date == null) start_date = dateToYMD(new Date((new Date()).setDate((new Date).getDate() -7)), short=true);
    const api_string=`/v1/ci/measurements?repo=${repo}&branch=${branch}&workflow=${workflow_id}&start_date=${start_date}&end_date=${end_date}`;
    return await makeAPICall(api_string);
}

const bindRefreshButton = (repo, branch, workflow_id, chart_instance) => {
    // When the user selects a subset of the measurement data via the date-picker
    $('#submit').on('click', async function () {
        const startDate = dateToYMD(new Date($('#rangestart input').val()), short=true);
        const endDate = dateToYMD(new Date($('#rangeend input').val()), short=true);

        let measurements = null;
        try {
            measurements = await getMeasurements(repo, branch, workflow_id, startDate, endDate); // iterates I
        } catch (err) {
            showNotification('Could not get data from API', err);
            return; // abort
        }

        displayStatsTable(measurements.data); //iterates II
        displayCITable(measurements.data, repo); // Iterates I (total: 1)

        // set new chart instance options
        const options = getChartOptions(measurements.data); //iterates I
        chart_instance.clear();
        chart_instance.setOption(options);

        chart_instance.off('legendselectchanged') // remove
        // we need to re-bind the handler here and can also not really refactor that
        // without using a global variable. echarts .on does not allow to pass data to the handler
        chart_instance.on('legendselectchanged', function (params) {
            // get list of all legends that are on
            const selectedLegends = params.selected;
            const filteredMeasurements = measurements.data.filter(measurement => selectedLegends[measurement[4]]);
            displayStatsTable(filteredMeasurements);
        });
    });
}

$(document).ready((e) => {
    (async () => {
        const query_string = window.location.search;
        const url_params = (new URLSearchParams(query_string))

        let branch = escapeString(url_params.get('branch'));
        let repo = escapeString(url_params.get('repo'));
        let workflow_id = escapeString(url_params.get('workflow'));
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

        ci_data_node.insertAdjacentHTML('afterbegin', `<tr><td><strong>Branch:</strong></td><td>${escapeString(url_params.get('branch'))}</td></tr>`)
        ci_data_node.insertAdjacentHTML('afterbegin', `<tr><td><strong>Workflow ID:</strong></td><td>${escapeString(workflow_id)}</td></tr>`)

        getLastRunBadge(repo, branch, workflow_id) // async

        $('#rangestart input').val(new Date((new Date()).setDate((new Date).getDate() -7))) // set default on load
        $('#rangeend input').val(new Date()) // set default on load
        dateTimePicker();

        let measurements = null;
        try {
            measurements = await getMeasurements(repo, branch, workflow_id)
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

        displayCITable(measurements.data, repo); // Iterates I (total: 1)

        displayGraph(chart_instance, measurements.data) // iterates I (total: 2)

        displayStatsTable(measurements.data) // iterates II (total: 4)

        // On legend change, recalculate stats table
        chart_instance.on('legendselectchanged', function (params) {
            // get list of all legends that are on
            const selectedLegends = params.selected;
            const filteredMeasurements = measurements.data.filter(measurement => selectedLegends[measurement[4]]);

            displayStatsTable(filteredMeasurements);
        });

        $('.ui.secondary.menu .item').tab();

        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
    })();
});
