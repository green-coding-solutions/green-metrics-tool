const numberFormatter = new Intl.NumberFormat('en-US', {
  style: 'decimal',
  maximumFractionDigits: 2,
});

const numberFormatterLong = new Intl.NumberFormat('en-US', {
  style: 'decimal',
  maximumFractionDigits: 4,
});

const calculateStats = (energy_measurements, co2eq_measurements, co2i_measurements, time_measurements, cpu_util_measurements) => {

    let energyAverage = energyStdDeviation = energyStdDevPercent = energySum ='--'
    let timeAverage = timeStdDeviation = timeStdDevPercent = timeSum '--'
    let co2eqAverage = co2eqStdDeviation = co2eqStdDevPercent = co2eqSum ='--'
    let co2iAverage = co2iStdDeviation = co2iStdDevPercent ='--'
    let cpuUtilStdDeviation = cpuUtilAverage = cpuUtilStdDevPercent '--'

    if (energy_measurements.length > 0) {
        [energyAverage, energyStdDeviation, energySum, energyStdDevPercent] = calculateStatistics(energy_measurements)
    }
    if (time_measurements.length > 0) {
        [timeAverage, timeStdDeviation, timeSum, timeStdDevPercent] = calculateStatistics(time_measurements)
    }
    if (co2eq_measurements.length > 0) {
        [co2eqAverage, co2eqStdDeviation, co2eqSum, co2eqStdDevPercent] = calculateStatistics(co2eq_measurements)
    }

    // intentially skipping co2iSum
    if (co2i_measurements.length > 0) {
        [co2iAverage, co2iStdDeviation, , co2iStdDevPercent] = calculateStatistics(co2i_measurements)
    }

    // intentially skipping cpuUtilSum
    if (cpu_util_measurements.length > 0) {
        const [cpuUtilAverage, cpuUtilStdDeviation, , cpuUtilStdDevPercent] = calculateStatistics(cpu_util_measurements)
    }

    return {
        energy: {
            average: energyAverage,
            stdDeviation: energyStdDeviation,
            stdDevPercent: energyStdDevPercent,
            total: energySum
        },
        time: {
            average: timeAverage,
            stdDeviation: timeStdDeviation,
            stdDevPercent: timeStdDevPercent,
            total: timeSum
        },
        co2eq: {
            average: co2eqAverage,
            stdDeviation: co2eqStdDeviation,
            stdDevPercent: co2eqStdDevPercent,
            total: co2eqSum
        },
        co2i: {
            average: co2iAverage,
            stdDeviation: co2iStdDeviation,
            stdDevPercent: co2iStdDevPercent
        },
        cpu_util: {
            average: cpuUtilAverage,
            stdDeviation: cpuUtilStdDeviation,
            stdDevPercent: cpuUtilStdDevPercent
        },
    };
};

const createStatsArrays = (measurements) => {  // iterates 2n times (1 full, 1 by run ID)
    const measurementsByRun = {}
    const measurementsByLabel = {}

    const measurementsForFullRun = {
        energy: [],
        co2eq: [],
        co2i: [],
        time: [],
        cpu_util: [],
        count: 0
    };

    measurements.forEach(measurement => {
        const run_id = measurement[2]
        const energy = measurement[0] / 1000 // will make J
        const time = measurement[7]
        const cpuUtil = measurement[9]
        const label = measurement[4]
        const co2i = parseInt(measurement[14])
        const co2eq = parseFloat(measurement[15])

        if (!measurementsByLabel[label]) {
            measurementsByLabel[label] = {
                energy: [],
                co2eq: [],
                co2i: [],
                time: [],
                cpu_util: [],
                count: 0
            };
        }
        if (!measurementsByRun[run_id]) {
            measurementsByRun[run_id] = {
                energy: [],
                co2eq: [],
                co2i: [],
                time: [],
                cpu_util: []
            };
        }

        if (energy != null) {
            measurementsByLabel[label].energy.push(energy);
            measurementsByRun[run_id].energy.push(energy);
        }
        if (time != null) {
            measurementsByLabel[label].time.push(time);
            measurementsByRun[run_id].time.push(time);
        }
        if (cpuUtil != null) {
            measurementsByLabel[label].cpu_util.push(cpuUtil);
            measurementsByRun[run_id].cpu_util.push(cpuUtil);
        }
        if (co2eq != null && !isNaN(co2eq)) {
            measurementsByLabel[label].co2eq.push(co2eq);
            measurementsByRun[run_id].co2eq.push(co2eq);
        }
        if (co2i != null && !isNaN(co2i)) {
            measurementsByLabel[label].co2i.push(co2i);
            measurementsByRun[run_id].co2i.push(co2i);
        }
        measurementsByLabel[label].count += 1;
        measurementsForFullRun.count += 1;
    });



   for (const run_id in measurementsByRun) {
        if (measurementsByRun[run_id].energy) measurementsForFullRun.energy.push(measurementsByRun[run_id].energy);
        if (measurementsByRun[run_id].co2eq) measurementsForFullRun.co2eq.push(measurementsByRun[run_id].co2eq);
        if (measurementsByRun[run_id].time) measurementsForFullRun.time.push(measurementsByRun[run_id].time);
        if (measurementsByRun[run_id].cpu_util) measurementsForFullRun.cpu_util.push(measurementsByRun[run_id].cpu_util);
        if (measurementsByRun[run_id].co2i) measurementsForFullRun.co2i.push(measurementsByRun[run_id].co2i);
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
        let [value, unit, run_id, timestamp, label, cpu, commit_hash, duration, source, cpu_util, workflow_name, lat, lon, city, co2i, co2eq] = measurement;
        cpu_util = cpu_util ? cpu_util : '--';
        options.series.push({
            type: 'bar',
            smooth: true,
            stack: run_id,
            name: cpu,
            data: [value],
            itemStyle: {
                borderWidth: .5,
                borderColor: '#000000',
              },
        })
        legend.add(cpu)

        labels.push({
            value: value,
            unit: unit,
            run_id: run_id,
            labels: [label],
            cpu_util: cpu_util,
            duration: duration,
            commit_hash: commit_hash,
            timestamp: dateToYMD(new Date(timestamp)),
            lat: lat,
            lon: lon,
            city: city,
            co2i: co2i,
            co2eq: co2eq
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
                    timestamp: ${labels[params.componentIndex].timestamp}<br>
                    commit_hash: ${escapeString(labels[params.componentIndex].commit_hash)}<br>
                    value: ${escapeString(labels[params.componentIndex].value)} ${escapeString(labels[params.componentIndex].unit)}<br>
                    duration: ${escapeString(labels[params.componentIndex].duration)} seconds<br>
                    avg. cpu. utilization: ${escapeString(labels[params.componentIndex].cpu_util)}%<br>
                    location of run: ${escapeString(labels[params.componentIndex].city || 'N/A')}<br>
                    grid intensity: ${escapeString(labels[params.componentIndex].co2i || 'N/A')}<br>
                    co2eq: ${escapeString(labels[params.componentIndex].co2eq || 'N/A')}<br>
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

    const full_run_stats = calculateStats(fullRunArray.energy, fullRunArray.co2eq, fullRunArray.co2i, fullRunArray.time, fullRunArray.cpu_util)

    const full_run_stats_avg_node = document.createElement("tr")
    full_run_stats_avg_node.innerHTML += `
                            <td class="td-index" data-tooltip="Stats for the series of runs (labels aggregated for each pipeline run)" data-position="top left">All steps <i class="question circle icon small"></i> </td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.energy.average)} J (± ${numberFormatter.format(full_run_stats.energy.stdDevPercent)}%)</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.time.average)}s (± ${numberFormatter.format(full_run_stats.time.stdDevPercent)}%)</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.cpu_util.average)}% (± ${numberFormatter.format(full_run_stats.cpu_util.stdDevPercent)}%%)</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.co2i.average)} gCO2/kWh (± ${numberFormatter.format(full_run_stats.co2i.stdDevPercent)}%)</td>
                            <td class="td-index">${numberFormatterLong.format(full_run_stats.co2eq.average)} gCO2e (± ${numberFormatter.format(full_run_stats.co2eq.stdDevPercent)}%)</td>
                            <td class="td-index">${numberFormatter.format(fullRunArray.count)}</td>`;

    avg_table.appendChild(full_run_stats_avg_node);

    const full_run_stats_total_node = document.createElement("tr")
    full_run_stats_total_node.innerHTML += `
                            <td class="td-index" data-tooltip="Stats for the series of runs (labels aggregated for each pipeline run)" data-position="top left">All steps <i class="question circle icon small"></i> </td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.energy.total)} J</td>
                            <td class="td-index">${numberFormatter.format(full_run_stats.time.total)}s</td>
                            <td class="td-index">${numberFormatterLong.format(full_run_stats.co2eq.total)} gCO2e</td>
                            <td class="td-index">${numberFormatter.format(fullRunArray.count)}</td>`;
    total_table.appendChild(full_run_stats_total_node)

    for (const label in labelsArray) {
        const label_stats = calculateStats(labelsArray[label].energy, labelsArray[label].co2eq, labelsArray[label].co2i, labelsArray[label].time, labelsArray[label].cpu_util)
        const label_stats_avg_node = document.createElement("tr")
        label_stats_avg_node.innerHTML += `
                                        <td class="td-index" data-tooltip="stats for the series of steps represented by the ${label} label"  data-position="top left">${label} <i class="question circle icon small"></i></td>
                                        <td class="td-index">${numberFormatter.format(label_stats.energy.average)} J (± ${numberFormatter.format(label_stats.energy.stdDevPercent)}%)</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.time.average)}s (± ${numberFormatter.format(label_stats.time.stdDevPercent)}%)</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.cpu_util.average)}% (± ${numberFormatter.format(label_stats.cpu_util.stdDevPercent)}%%)</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.co2i.average)} gCO2/kWh (± ${numberFormatter.format(label_stats.co2i.stdDevPercent)}%)</td>
                                        <td class="td-index">${numberFormatterLong.format(label_stats.co2eq.average)} gCO2e (± ${numberFormatter.format(label_stats.co2eq.stdDevPercent)}%)</td>
                                        <td class="td-index">${numberFormatter.format(labelsArray[label].count)}</td>`;

        avg_table.appendChild(label_stats_avg_node);

        const label_stats_total_node = document.createElement("tr")
        label_stats_total_node.innerHTML += `
                                        <td class="td-index" data-tooltip="stats for the series of steps represented by the ${label} label"  data-position="top left">${label} <i class="question circle icon small"></i></td>
                                        <td class="td-index">${numberFormatter.format(label_stats.energy.total)} J</td>
                                        <td class="td-index">${numberFormatter.format(label_stats.time.total)}s</td>
                                        <td class="td-index">${numberFormatterLong.format(label_stats.co2eq.total)} gCO2e</td>
                                        <td class="td-index">${numberFormatter.format(labelsArray[label].count)}</td>`;
        total_table.appendChild(label_stats_total_node);

    };
}

const displayCITable = (measurements, repo) => {

    document.querySelector("#ci-table").innerHTML = ''; // clear

    measurements.forEach(el => {
        const li_node = document.createElement("tr");

        const energy_value = el[0] / 1000;
        const run_id = el[2];
        const cpu = el[5];
        const commit_hash = el[6];
        const short_hash = commit_hash.substring(0, 7);
        const tooltip = `title="${commit_hash}"`;
        const source = el[8];
        const cpu_avg = el[9] ? el[9] : '--';
        const lat = el[11];
        const lon = el[12];
        const city = el[13];
        const co2i = el[14];
        const co2eq = el[15];

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
        const created_at = el[3]

        const label = el[4]
        const duration = el[7]

        li_node.innerHTML = `
                            <td class="td-index">${run_link_node}</td>\
                            <td class="td-index">${escapeString(label)}</td>\
                            <td class="td-index"><span title="${escapeString(created_at)}">${dateToYMD(new Date(created_at))}</span></td>\
                            <td class="td-index">${numberFormatter.format(energy_value)} J</td>\
                            <td class="td-index">${escapeString(cpu)}</td>\
                            <td class="td-index">${escapeString(cpu_avg)}%</td>
                            <td class="td-index">${escapeString(duration)} s</td>
                            <td class="td-index" ${escapeString(tooltip)}>${escapeString(short_hash)}</td>\
                            <td class="td-index">${city_string}</td>
                            <td class="td-index">${escapeString(co2i)} gCO2/kWh</td>
                            <td class="td-index" title="${escapeString(co2eq)}">${escapeString(numberFormatterLong.format(co2eq))} gCO2e</td>
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
    if(start_date == null) start_date = dateToYMD(new Date((new Date()).setDate((new Date).getDate() -30)), short=true);
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
            const filteredMeasurements = measurements.data.filter(measurement => selectedLegends[measurement[5]]);
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

        $('#rangestart input').val(new Date((new Date()).setDate((new Date).getDate() -30))) // set default on load
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
            const filteredMeasurements = measurements.data.filter(measurement => selectedLegends[measurement[5]]);

            displayStatsTable(filteredMeasurements);
        });

        $('.ui.secondary.menu .item').tab();

        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
    })();
});
