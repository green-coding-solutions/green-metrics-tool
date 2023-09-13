const convertValue = (value, unit) => {
    switch (unit) {
        case 'mJ':
            return [value / 1000, 'Joules'];
            break;
        default:
            return [value, unit];        // no conversion in default calse
    }

}

const calculateStats = (measurements) => {
    let energyMeasurements = measurements.map(measurement => measurement[0]);
    let energySum = energyMeasurements.reduce((a, b) => a + b, 0);
    let timeMeasurements = measurements.map(measurement => measurement[7]);
    let timeSum = timeMeasurements.reduce((a, b) => a + b, 0);
    let cpuUtilMeasurments = measurements.map(measurement => measurement[9]);

    let energyAverage = math.mean(energyMeasurements);
    let timeAverage = math.mean(timeMeasurements);
    let cpuUtilAverage = math.mean(cpuUtilMeasurments);

    let energyStdDeviation = math.std(energyMeasurements);
    let timeStdDeviation = math.std(timeMeasurements);
    let cpuUtilStdDeviation = math.std(cpuUtilMeasurments);

    let energyStdDevPercent = (energyStdDeviation / energyAverage) * 100;
    let timeStdDevPercent = (timeStdDeviation / timeAverage) * 100;
    let cpuUtilStdDevPercent = (cpuUtilStdDeviation / cpuUtilAverage) * 100;

    return {
        energy: {
            average: Math.round(energyAverage),
            stdDeviation: Math.round(energyStdDeviation),
            stdDevPercent: Math.round(energyStdDevPercent),
            total: Math.round(energySum)
        },
        time: {
            average: Math.round(timeAverage),
            stdDeviation: Math.round(timeStdDeviation),
            stdDevPercent: Math.round(timeStdDevPercent),
            total: Math.round(timeSum)
        },
        cpu_util: {
            average: Math.round(cpuUtilAverage),
            stdDeviation: Math.round(cpuUtilStdDeviation),
            stdDevPercent: Math.round(cpuUtilStdDevPercent)
        },
        count: measurements.length
    };
};

const getStatsofLabel = (measurements, label) => {
    let filteredMeasurements = measurements.filter(measurement => measurement[4] === label);

    if (filteredMeasurements.length === 0) {
        return { average: NaN, stdDeviation: NaN };
    }

    return calculateStats(filteredMeasurements);
};

const getFullRunStats = (measurements) => {
    let combinedMeasurements = [];

    let sumByRunId = {};

    measurements.forEach(measurement => {
        const runId = measurement[2];

        if (!sumByRunId[runId]) {
            sumByRunId[runId] = {
                energySum: 0,
                timeSum: 0,
                cpuUtilSum: 0,
                count: 0
            };
        }

        sumByRunId[runId].energySum += measurement[0];
        sumByRunId[runId].timeSum += measurement[7];
        sumByRunId[runId].cpuUtilSum += measurement[9];
        sumByRunId[runId].count++;
    });

    for (const runId in sumByRunId) {
        const avgCpuUtil = sumByRunId[runId].cpuUtilSum / sumByRunId[runId].count; // Calculate the average
        combinedMeasurements.push({
            0: sumByRunId[runId].energySum,
            7: sumByRunId[runId].timeSum,
            9: avgCpuUtil, // Use the calculated average
            2: runId
        });
    }

    return calculateStats(combinedMeasurements);
};

const createChartContainer = (container, el) => {
    const chart_node = document.createElement("div")
    chart_node.classList.add("card");
    chart_node.classList.add('statistics-chart-card')
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

const filterMeasurements = (measurements, start_date, end_date, selectedLegends) => {
    let filteredMeasurements = [];
    let discard_measurements = [];

    measurements.forEach(measurement => {
        let run_id = measurement[2];
        let timestamp = new Date(measurement[3]);

        if (timestamp >= start_date && timestamp <= end_date && selectedLegends[measurement[5]]) {
            filteredMeasurements.push(measurement);
        } else {
            discard_measurements.push(run_id);
        }
    });

    displayStatsTable(filteredMeasurements); // Update stats table
    return filteredMeasurements;
}

const getChartOptions = (measurements, chart_element) => {
    let options = getEChartsOptions();
    options.title.text = `Workflow energy cost per run [mJ]`;

    let legend = new Set()
    let labels = []

    measurements.forEach(measurement => { // iterate over all measurements, which are in row order
        let [value, unit, run_id, timestamp, label, cpu, commit_hash, duration, source, cpu_util] = measurement;
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

        labels.push({value: value, unit: unit, run_id: run_id, labels: [label], cpu_util: cpu_util, duration: duration, commit_hash: commit_hash, timestamp: dateToYMD(new Date(timestamp))})
    });

    options.legend.data = Array.from(legend)
    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${labels[params.componentIndex].labels[params.dataIndex]}</strong><br>
                    run_id: ${labels[params.componentIndex].run_id}<br>
                    timestamp: ${labels[params.componentIndex].timestamp}<br>
                    commit_hash: ${labels[params.componentIndex].commit_hash}<br>
                    value: ${labels[params.componentIndex].value} ${labels[params.componentIndex].unit}<br>
                    duration: ${labels[params.componentIndex].duration} seconds<br>
                    avg. cpu. utilization: ${labels[params.componentIndex].cpu_util}%<br>
                    `;
        }
    };
    return options
}


const displayGraph = (measurements) => {
    const element = createChartContainer("#chart-container", "run-energy");

    const options = getChartOptions(measurements, element);

    const chart_instance = echarts.init(element);
    chart_instance.setOption(options);

    // we want to listen for the zoom event to display a line or a icon with the grand total in the chart
    // => Look at what cool stuff can be display!

    // trigger the dataZoom event manually when this function. Similar how we do resize

    // the dataZoom callback needs to walk the dataset.source everytime on zoom and only add up all values that
    // are >= startValue <=  endValue
    // either copying element or reducing it by checking if int or not

    chart_instance.on('dataZoom', function (evt) {
        let sum = 0;
        if (!('startValue' in evt.batch[0])) return
        for (var i = evt.batch[0].startValue; i <= evt.batch[0].endValue; i++) {
            sum = sum + options.dataset.source[i].slice(1).reduce((partialSum, a) => partialSum + a, 0);
        }
    })
    window.onresize = function () { // set callback when ever the user changes the viewport
        chart_instance.resize();
    }

    chart_instance.on('legendselectchanged', function (params) {
        const selectedLegends = params.selected;
        const filteredMeasurements = measurements.filter(measurement => selectedLegends[measurement[5]]);

        displayStatsTable(filteredMeasurements);
    });

    return chart_instance;
}

const displayStatsTable = (measurements) => {
    let labels = new Set()
    measurements.forEach(measurement => {
        labels.add(measurement[4])
    });

    const tableBody = document.querySelector("#label-stats-table");
    tableBody.innerHTML = "";

    const label_full_stats_node = document.createElement("tr")
    full_stats = getFullRunStats(measurements)
    label_full_stats_node.innerHTML += `
                            <td class="td-index" data-tooltip="Stats for the series of runs (labels aggregated for each pipeline run)"> <i class="question circle icon small"></i> Full Run</td>
                            <td class="td-index">${full_stats.energy.average} mJ</td>
                            <td class="td-index">${full_stats.energy.stdDeviation} mJ</td>
                            <td class="td-index">${full_stats.energy.stdDevPercent}%</td>
                            <td class="td-index">${full_stats.time.average}s</td>
                            <td class="td-index">${full_stats.time.stdDeviation}s</td>
                            <td class="td-index">${full_stats.time.stdDevPercent}%</td>
                            <td class="td-index">${full_stats.cpu_util.average}%</td>
                            <td class="td-index">${full_stats.energy.total} mJ</td>
                            <td class="td-index">${full_stats.time.total}s</td>
                            <td class="td-index">${full_stats.count}</td>
                            `
    tableBody.appendChild(label_full_stats_node);

    labels.forEach(label => {
        const label_stats_node = document.createElement("tr")
        let stats = getStatsofLabel(measurements, label);
        label_stats_node.innerHTML += `
                                        <td class="td-index" data-tooltip="Stats for the series of steps represented by the ${label} label">${label}</td>
                                        <td class="td-index">${stats.energy.average} mJ</td>
                                        <td class="td-index">${stats.energy.stdDeviation} mJ</td>
                                        <td class="td-index">${stats.energy.stdDevPercent}%</td>
                                        <td class="td-index">${stats.time.average}s</td>
                                        <td class="td-index">${stats.time.stdDeviation}s</td>
                                        <td class="td-index">${stats.time.stdDevPercent}%</td>
                                        <td class="td-index">${stats.cpu_util.average}%</td>
                                        <td class="td-index">${stats.energy.total} mJ</td>
                                        <td class="td-index">${stats.time.total}s</td>
                                        <td class="td-index">${stats.count}</td>
                                        `
    document.querySelector("#label-stats-table").appendChild(label_stats_node);
    });
}

const displayCITable = (measurements, url_params) => {
    measurements.forEach(el => {
        const li_node = document.createElement("tr");

        [energy_value, energy_unit] = convertValue(el[0], el[1])
        const value = `${energy_value} ${energy_unit}`;

        const run_id = el[2];
        const cpu = el[5];
        const commit_hash = el[6];
        const short_hash = commit_hash.substring(0, 7);
        const tooltip = `title="${commit_hash}"`;
        const source = el[8];
        const cpu_avg = el[9];

        var run_link = ''
        if(source == 'github') {
            run_link = `https://github.com/${escapeString(url_params.get('repo'))}/actions/runs/${escapeString(run_id)}`;
        }
        else if (source == 'gitlab') {
            run_link = `https://gitlab.com/${escapeString(url_params.get('repo'))}/-/pipelines/${escapeString(run_id)}`
        }

        const run_link_node = `<a href="${run_link}" target="_blank">${escapeString(run_id)}</a>`

        const created_at = el[3]

        const label = el[4]
        const duration = el[7]

        li_node.innerHTML = `
                            <td class="td-index">${run_link_node}</td>\
                            <td class="td-index">${escapeString(label)}</td>\
                            <td class="td-index"><span title="${escapeString(created_at)}">${dateToYMD(new Date(created_at))}</span></td>\
                            <td class="td-index">${escapeString(value)}</td>\
                            <td class="td-index">${escapeString(cpu)}</td>\
                            <td class="td-index">${cpu_avg}%</td>
                            <td class="td-index">${duration} seconds</td>
                            <td class="td-index" ${escapeString(tooltip)}>${escapeString(short_hash)}</td>\
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

$(document).ready((e) => {
    (async () => {
        const query_string = window.location.search;
        const url_params = (new URLSearchParams(query_string))

        if (url_params.get('repo') == null || url_params.get('repo') == '' || url_params.get('repo') == 'null') {
            showNotification('No Repo', 'Repo parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }
        if (url_params.get('branch') == null || url_params.get('branch') == '' || url_params.get('branch') == 'null') {
            showNotification('No Branch', 'Branch parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }
        if (url_params.get('workflow') == null || url_params.get('workflow') == '' || url_params.get('workflow') == 'null') {
            showNotification('No Workflow', 'Workflow parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }

        try {
            const link_node = document.createElement("a")
            const img_node = document.createElement("img")
            img_node.src = `${API_URL}/v1/ci/badge/get?repo=${url_params.get('repo')}&branch=${url_params.get('branch')}&workflow=${url_params.get('workflow')}`
            link_node.href = window.location.href
            link_node.appendChild(img_node)
            document.querySelector("span.energy-badge-container").appendChild(link_node)
            document.querySelector(".copy-badge").addEventListener('click', copyToClipboard)
        } catch (err) {
            showNotification('Could not get badge data from API', err);
        }

        try {
            api_string=`/v1/ci/measurements?repo=${url_params.get('repo')}&branch=${url_params.get('branch')}&workflow=${url_params.get('workflow')}`;
            var measurements = await makeAPICall(api_string);
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }

        let repo_link = ''
        let source = measurements.data[0][8]

        if(source == 'github') {
            repo_link = `https://github.com/${escapeString(url_params.get('repo'))}`;
        }
        else if(source == 'gitlab') {
            repo_link = `https://gitlab.com/${escapeString(url_params.get('repo'))}`;
        }
        //${repo_link}
        const repo_link_node = `<a href="${repo_link}" target="_blank">${escapeString(url_params.get('repo'))}</a>`
        document.querySelector('#ci-data').insertAdjacentHTML('afterbegin', `<tr><td><strong>Repository:</strong></td><td>${repo_link_node}</td></tr>`)
        document.querySelector('#ci-data').insertAdjacentHTML('afterbegin', `<tr><td><strong>Branch:</strong></td><td>${escapeString(url_params.get('branch'))}</td></tr>`)
        document.querySelector('#ci-data').insertAdjacentHTML('afterbegin', `<tr><td><strong>Workflow:</strong></td><td>${escapeString(url_params.get('workflow'))}</td></tr>`)

        displayCITable(measurements.data, url_params);
        
        chart_instance = displayGraph(measurements.data)
        displayStatsTable(measurements.data)
        dateTimePicker();

        $('#submit').on('click', function () {
            var startDate = new Date($('#rangestart input').val());
            var endDate = new Date($('#rangeend input').val());

            const selectedLegends = chart_instance.getOption().legend[0].selected;
            const filteredMeasurements = filterMeasurements(measurements.data, startDate, endDate, selectedLegends);

            options = getChartOptions(filteredMeasurements);
            chart_instance.clear();
            chart_instance.setOption(options);
        });

        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
    })();
});
