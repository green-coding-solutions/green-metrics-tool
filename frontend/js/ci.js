const convertValue = (value, unit) => {
    switch (unit) {
        case 'mJ':
            return [value / 1000, 'Joules'];
            break;
        default:
            return [value, unit];        // no conversion in default calse
    }

}

const getAverageOfLabel = (runs, label) => {
    let filteredRuns = runs.filter(run => run[4] == label);
    let sum = filteredRuns.reduce((acc, run) => acc + run[0], 0);
    return Math.round(sum / filteredRuns.length);
}


const getTotalAverage = (runs) => {
    let sum = runs.reduce((acc, run) => acc + run[0], 0);
    return Math.round(sum / runs.length);
}

const createChartContainer = (container, el, runs) => {
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

const filterRuns = (runs, start_date, end_date) => {
    let filtered_runs = [];
    let discard_runs = [];
    runs.forEach(run => {
        let run_id = run[2];
        let timestamp = new Date(run[3]);
        if (timestamp >= start_date && timestamp <= end_date) {
            filtered_runs.push(run);
        }
        else
            discard_runs.push(run_id);
    });
    // This was intended to catch the case where a run has dates that start before midnight and end after midngiht
    // but it is not working correctly at the moment
    //filtered_runs = filtered_runs.filter(run => !discard_runs.includes(run[2]));
    return filtered_runs;
}

// This is not in use at the moment, keeping it as I believe it will be useful in the next iteration of the
// chart display
function transformRuns(runs) {
    const transformedRuns = {};
    for (const run of runs) {
        const runId = run[2];
        const unit = run[1];
        const timestamp = new Date(run[3]).getTime();
        const value = run[0];
        const label = run[4];
        const cpu = run[5];
        const commitHash = run[6];
        const duration = run[7]

        if (!transformedRuns[runId]) {
            transformedRuns[runId] = {
                run_id: runId,
                unit: unit,
                timestamps: [],
                values: [],
                labels: [],
                cpu: cpu,
                commit_hash: commitHash,
                duration: duration,
                earliest_timestamp: timestamp,
                earliest_timestamp_readable: dateToYMD(new Date(timestamp),short=true)
            };
        } else if (timestamp < transformedRuns[runId].earliest_timestamp) {
            transformedRuns[runId].earliest_timestamp = timestamp;
            transformedRuns[runId].earliest_timestamp_readable = dateToYMD(new Date(timestamp));
        }

        transformedRuns[runId].timestamps.push(timestamp);
        transformedRuns[runId].values.push(value);
        transformedRuns[runId].labels.push(label);
  }

  return Object.values(transformedRuns);
}

// Also not in use at the moment, keeping it in case we need to pad the array later
const createPaddedArray = (index, value) => {
  return [...Array(index).fill(0), value];
};

const getChartOptions = (runs, chart_element) => {
    let options = getEChartsOptions();
    options.title.text = `Workflow energy cost per run [mJ]`;

    let legend = new Set()
    let labels = []

    runs.forEach(run => { // iterate over all runs, which are in row order
        let [value, unit, run_id, timestamp, label, cpu, commit_hash, duration] = run;
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

        labels.push({value: value, unit: unit, run_id: run_id, labels: [label], duration: duration, commit_hash: commit_hash, timestamp: dateToYMD(new Date(timestamp))})
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
                    `;
        }
    };
    return options
}

const displayGraph = (runs) => {
    const element = createChartContainer("#chart-container", "run-energy", runs);
    
    const options = getChartOptions(runs, element);

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

    return chart_instance;
}

const displayAveragesTable = (runs) => {
    let labels = new Set()
    runs.forEach(run => {
        labels.add(run[4])
    });

    const tableBody = document.querySelector("#label-avg-table");
    tableBody.innerHTML = "";

    const label_total_avg_node = document.createElement("tr")
    label_total_avg_node.innerHTML += `
                            <td class="td-index">${getTotalAverage(runs)} mJ</td>
                            <td class="td-index">Total</td>`
    tableBody.appendChild(label_total_avg_node);

    labels.forEach(label => {
        const label_avgs_node = document.createElement("tr")
        let avg = getAverageOfLabel(runs, label);
        label_avgs_node.innerHTML += `
                                        <td class="td-index">${avg} mJ</td>
                                        <td class="td-index">${label}</td>`
    document.querySelector("#label-avg-table").appendChild(label_avgs_node);
    });
}

const displayCITable = (runs, url_params) => {
    runs.forEach(el => {
        const li_node = document.createElement("tr");

        [badge_value, badge_unit] = convertValue(el[0], el[1])
        const value = `${badge_value} ${badge_unit}`;

        const run_id = el[2];
        const cpu = el[5];
        const commit_hash = el[6];
        const short_hash = commit_hash.substring(0, 7);
        const tooltip = `title="${commit_hash}"`;

        const run_link = `https://github.com/${url_params.get('repo')}/actions/runs/${run_id}`;
        const run_link_node = `<a href="${run_link}" target="_blank">${run_id}</a>`

        const created_at = el[3]

        const label = el[4]
        const duration = el[7]

        li_node.innerHTML = `<td class="td-index">${value}</td>\
                            <td class="td-index">${label}</td>\
                            <td class="td-index">${run_link_node}</td>\
                            <td class="td-index"><span title="${created_at}">${dateToYMD(new Date(created_at))}</span></td>\
                            <td class="td-index" ${tooltip}>${short_hash}</td>\
                            <td class="td-index">${cpu}</td>\
                            <td class="td-index">${duration} seconds</td>`;
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

        const repo_link = `https://github.com/${url_params.get('repo')}`;
        const repo_link_node = `<a href="${repo_link}" target="_blank">${url_params.get('repo')}</a>`
        document.querySelector('#ci-data').insertAdjacentHTML('afterbegin', `<tr><td><strong>Repository:</strong></td><td>${repo_link_node}</td></tr>`)
        document.querySelector('#ci-data').insertAdjacentHTML('afterbegin', `<tr><td><strong>Branch:</strong></td><td>${url_params.get('branch')}</td></tr>`)
        document.querySelector('#ci-data').insertAdjacentHTML('afterbegin', `<tr><td><strong>Workflow:</strong></td><td>${url_params.get('workflow')}</td></tr>`)

        try {
            const link_node = document.createElement("a")
            const img_node = document.createElement("img")
            img_node.src = `${API_URL}/v1/ci/badge/get?repo=${url_params.get('repo')}&branch=${url_params.get('branch')}&workflow=${url_params.get('workflow')}`
            link_node.appendChild(img_node)
            document.querySelector("span.energy-badge-container").appendChild(link_node)
            document.querySelector(".copy-badge").addEventListener('click', copyToClipboard)
        } catch (err) {
            showNotification('Could not get badge data from API', err);
        }

        try {
            api_string=`/v1/ci/measurements?repo=${url_params.get('repo')}&branch=${url_params.get('branch')}&workflow=${url_params.get('workflow')}`;
            var badges_data = await makeAPICall(api_string);
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }

        displayCITable(badges_data.data, url_params);
        chart_instance = displayGraph(badges_data.data)
        displayAveragesTable(badges_data.data)
        dateTimePicker();
        $('#submit').on('click', function() {
            var startDate = new Date($('#rangestart input').val());
            var endDate = new Date($('#rangeend input').val());
            new_runs = filterRuns(badges_data.data, startDate, endDate)
            options = getChartOptions(new_runs)
            chart_instance.clear()
            chart_instance.setOption(options);
            displayAveragesTable(new_runs);
        });
    })();
});
