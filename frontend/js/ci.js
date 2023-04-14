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

        xAxis: { type: 'category' },
        dataset: {source:[]},
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

const displayGraph = (runs) => {
    console.log("Runs", runs)
    const element = createChartContainer("#chart-container", "run-energy");
    let options = getEChartsOptions();
    let run_notes = {}

    options.title.text = `Workflow energy cost per run [Joules]`;


    let tooltip = []

    idx = -1; // since we force an ordering from the API, we can safely assume increasing run_ids
    runs.forEach(run => { // iterate over all runs, which are in row order
        let [value, unit, run_id, timestamp, label] = run;

        if (run_id in run_notes) { // if run_id in notes
            run_notes[run_id].values.push(value)
            tooltip[idx].labels.push(label)
        }
        else {
            run_notes[run_id] = {
                timestamp: formatDateTime(new Date(timestamp)),
                values: [value]
            }
            tooltip.push({run_id: run_id, labels: [label]})
            idx++;
        }
    });

    let max_len = 0
    for (entry in run_notes) {
        options.dataset.source.push([run_notes[entry].timestamp].concat(run_notes[entry].values))
        if (run_notes[entry].values.length > max_len) {
            max_len = run_notes[entry].values.length
        }
    }

    for (let index = 0; index < max_len; index++) {
        options.series.push({
            type: 'bar',
            smooth: true,
            seriesLayoutBy: 'column',
            stack: 'test', // does not matter what you call it actually
        })
    }

    options.series.at(-1)["label"] = {
        normal: {
            show: true,
            distance: 5,
            position: 'top',
            formatter: (params) => {
                let total = 0;
                params.data.slice(1).forEach(value => total += value)
                return total;
            }
        }
    }

    // pad the values with zeroes so the graph doesn't add 'undefined' entries to the stacks
    for (let index = 0; index < options.dataset.source.length; index++) {
        // +1 because of the timestamp on position 0
        while (options.dataset.source[index].length < max_len + 1) {
            options.dataset.source[index].push(0)
        }
    }

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `value: ${params.data[params.componentIndex + 1]}; run: ${tooltip[params.dataIndex].run_id}; label: ${tooltip[params.dataIndex].labels[params.componentIndex]}`;
        }
    }

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

        badges_data.data.forEach(el => {
            const li_node = document.createElement("tr");

            [badge_value, badge_unit] = convertValue(el[0], el[1])
            const value = badge_value + ' ' + badge_unit;

            const run_id = el[2];
            const run_link = `https://github.com/${url_params.get('repo')}/actions/runs/${run_id}`;
            const run_link_node = `<a href="${run_link}" target="_blank">${run_id}</a>`

            const created_at = el[3]

            const label = el[4]

            li_node.innerHTML = `<td class="td-index">${value}</td>\
                                <td class="td-index">${label}</td>\
                                <td class="td-index">${run_link_node}</td>\
                                <td class="td-index"><span title="${created_at}">${formatDateTime(new Date(created_at))}</span></td>`;
            document.querySelector("#badges-table").appendChild(li_node);
        });
        $('table').tablesort();
        displayGraph(badges_data.data)

    })();
});
