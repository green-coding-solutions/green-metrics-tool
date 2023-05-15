const addZed = (num) => {
    return (num <= 9 ? '0' + num : num);
}

const formatDateTime = (date) => {
    var h = date.getHours();
    var m = date.getMinutes();
    var s = date.getSeconds();

    var timeString = '' + addZed(h) + ':' + addZed(m) + ':' + addZed(s)
    var dateString = date.toDateString();

    return '' + dateString + ' | ' + timeString
}

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
    let sum = 0;
    let count = 0;
    runs.forEach(run => {
        if (run[4] == label) {
            sum += run[0];
            count++;
        }
    });
    return Math.round(sum / count);
}

const getTotalAverage = (runs) => {
    let sum = 0;
    let count = 0;
    runs.forEach(run => {
        sum += run[0];
        count++;
    });
    return Math.round(sum / count);
}

const createChartContainer = (container, el, runs) => {
    const chart_node = document.createElement("div")
    chart_node.classList.add("card");
    chart_node.classList.add('statistics-chart-card')
    chart_node.classList.add('ui')
            /*<table class="ui sortable celled striped table" id="table">*/

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
        },
        toolbox: {
            itemSize: 25,
            top: 55,
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {}
            }
        },

    };
}

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

    if (!transformedRuns[runId]) {
      transformedRuns[runId] = {
        run_id: runId,
        unit: unit,
        timestamps: [],
        values: [],
        labels: [],
        cpu: cpu,
        commit_hash: commitHash,
        earliest_timestamp: timestamp,
        earliest_timestamp_readable: formatDateTime(new Date(timestamp))
      };
    } else if (timestamp < transformedRuns[runId].earliest_timestamp) {
      transformedRuns[runId].earliest_timestamp = timestamp;
      transformedRuns[runId].earliest_timestamp_readable = formatDateTime(new Date(timestamp));
    }

    transformedRuns[runId].timestamps.push(timestamp);
    transformedRuns[runId].values.push(value);
    transformedRuns[runId].labels.push(label);
  }

  return Object.values(transformedRuns);
}

const createValueArray = (index, value) => {
    let array = [];
    for (let i = 0; i < index; i++) {
        array.push(0);
    }
    array.push(value);
    return array;
}

const displayGraph = (runs) => {
    const element = createChartContainer("#chart-container", "run-energy", runs);
    const transformed_runs = transformRuns(runs);
    let options = getEChartsOptions();
    options.xAxis.data = transformed_runs.map(run => run.earliest_timestamp_readable);

    options.title.text = `Workflow energy cost per run [mJ]`;

    let legend = new Set()
    let labels = []

    idx = -1; // since we force an ordering from the API, we can safely assume increasing run_ids
    transformed_runs.forEach((run, run_index) => {
        run.values.forEach((value, index) => {
            options.series.push({
                type: 'bar',
                smooth: true,
                stack: run.earliest_timestamp_readable,
                name: run.cpu,
                data: createValueArray(run_index, value)
            });

            legend.add(run.cpu);

            labels.push({
                value: value,
                unit: run.unit,
                run_id: run.run_id,
                labels: createValueArray(run_index, [run.labels[index]]),
                commit_hash: run.commit_hash,
                timestamp: formatDateTime(new Date(run.timestamps[index]))
            });
        idx = run.run_id;
        });
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
                    `;
        }
    };
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
}

const displayAveragesTable = (runs) => {
    let labels = new Set()
    runs.forEach(run => {
        let [value, unit, run_id, timestamp, label, cpu, commit_hash] = run;
        labels.add(label)
    });

    const label_total_avg_node = document.createElement("tr")
    label_total_avg_node.innerHTML += `
                            <td class="td-index">${getTotalAverage(runs)} mJ</td>
                            <td class="td-index">Total</td>`
    document.querySelector("#label-avg-table").appendChild(label_total_avg_node);

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
        const value = badge_value + ' ' + badge_unit;

        const run_id = el[2];
        const cpu = el[5];
        const commit_hash = el[6];
        const short_hash = commit_hash.substring(0, 7);
        const tooltip = commit_hash.length > 7 ? `title="${commit_hash}"` : '';

        const run_link = `https://github.com/${url_params.get('repo')}/actions/runs/${run_id}`;
        const run_link_node = `<a href="${run_link}" target="_blank">${run_id}</a>`

        const created_at = el[3]

        const label = el[4]

        li_node.innerHTML = `<td class="td-index">${value}</td>\
                            <td class="td-index">${label}</td>\
                            <td class="td-index">${run_link_node}</td>\
                            <td class="td-index"><span title="${created_at}">${formatDateTime(new Date(created_at))}</span></td>\
                            <td class="td-index" ${tooltip}>${short_hash}</td>\
                            <td class="td-index">${cpu}</td>\
                            <td class="td-index">???</td>`;
        document.querySelector("#ci-table").appendChild(li_node);
    });
    $('table').tablesort();
}

function dateTimePicker() {
    const datePickerHtml = document.createElement("div");
  datePickerHtml.innerHTML = `
    <label for="date">Date:</label>
    <input type="date" id="date">
    <label for="time">Time:</label>
    <input type="time" id="time">
    <button onclick="getDateTime()">Submit</button>
  `;
  document.querySelector("#ci-date-picker").appendChild(datePickerHtml)
}

function getDateTime() {
  const dateInput = document.getElementById('date');
  const timeInput = document.getElementById('time');

  const date = dateInput.value;
  const time = timeInput.value;

  const dateTime = `${date} ${time}`;

  console.log(dateTime);
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
        displayGraph(badges_data.data)
        displayAveragesTable(badges_data.data)
        //dateTimePicker();
    })();
});
