const getURLParams = () => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))
    return url_params;
}

let chart_instances = [];

window.onresize = function() { // set callback when ever the user changes the viewport
    chart_instances.forEach(chart_instance => {
        chart_instance.resize();
    })
}

function* colorIterator() {
    colors = [
        '#88a788',
        '#e5786d',
        '#baa5c3',
        '#f2efe3',
        '#3d704d',
    ]
    let currentIndex = 0;

    function getNextItem(colors) {
      const currentItem = colors[currentIndex];
      currentIndex = (currentIndex + 1) % colors.length;
      return currentItem;
    }
    while (true) {
        yield(getNextItem(colors))
    }
}

const generateColoredValues = (values) => {
    const color_iterator = colorIterator()
    let last_commit_hash = null
    let color = null;
    return values.map((value) => {
        if(last_commit_hash != value.commit_hash) {
            last_commit_hash = value.commit_hash
            color = color_iterator.next().value
        }
        return {value: value.value, itemStyle: {color: color}}
    })
}

const populateMachines = async () => {

    try {
        const machines_select = document.querySelector('select[name="machine_id"]');

        machines_data = (await makeAPICall('/v1/machines/'))
        machines_data.data.forEach(machine => {
            let newOption = new Option(machine[1],machine[0]);
            machines_select.add(newOption,undefined);
        })
    } catch (err) {
        showNotification('Could not get machines', err);
    }


}

const fillInputsFromURL = () => {
    let url_params = getURLParams();

    if(url_params.get('uri') == null
        || url_params.get('uri') == ''
        || url_params.get('uri') == 'null') {
        showNotification('No uri', 'uri parameter in URL is empty or not present. Did you follow a correct URL?');
        throw "Error";
    }
    $('input[name="uri"]').val(escapeString(url_params.get('uri')));

    // all variables can be set via URL initially
    if(url_params.get('branch') != null) $('input[name="branch"]').val(escapeString(url_params.get('branch')));
    if(url_params.get('filename') != null) $('input[name="filename"]').val(escapeString(url_params.get('filename')));
    if(url_params.get('phase') != null) $(`#phase-${url_params.get('phase')}`).prop('checked', true);
    if(url_params.get('metrics') != null) $(`#metrics-${url_params.get('metrics')}`).prop('checked', true);
    if(url_params.get('machine_id') != null) $('select[name="machine_id"]').val(escapeString(url_params.get('machine_id')));

    // these two need no escaping, as the date library will always produce a result
    // it might fail parsing the date however
    try {
        if(url_params.get('start_date') != null) $('#rangestart').calendar({initialDate: url_params.get('start_date')});
        if(url_params.get('end_date') != null) $('#rangeend').calendar({initialDate: url_params.get('end_date')});
    } catch (err) {
        console.log("Date parsing failed")
    }
}

const buildQueryParams = (skip_dates=false,metric_override=null,detail_name=null) => {
    let api_url = `uri=${$('input[name="uri"]').val()}`;

    // however, the form takes precendence
    if($('input[name="branch"]').val() !== '') api_url = `${api_url}&branch=${$('input[name="branch"]').val()}`
    if($('input[name="phase"]:checked').val() !== '') api_url = `${api_url}&phase=${$('input[name="phase"]:checked').val()}`
    if($('select[name="machine_id"]').val() !== '') api_url = `${api_url}&machine_id=${$('select[name="machine_id"]').val()}`
    if($('input[name="filename"]').val() !== '') api_url = `${api_url}&filename=${$('input[name="filename"]').val()}`

    if(metric_override != null) api_url = `${api_url}&metrics=${metric_override}`
    else if($('input[name="metrics"]:checked').val() !== '') api_url = `${api_url}&metrics=${$('input[name="metrics"]:checked').val()}`

    if(detail_name != null) api_url = `${api_url}&detail_name=${detail_name}`

    if (skip_dates) return api_url;

    if ($('input[name="start_date"]').val() != '') {
        let start_date = dateToYMD(new Date($('input[name="start_date"]').val()), short=true, sane=true);
        api_url = `${api_url}&start_date=${start_date}`
    }

    if ($('input[name="end_date"]').val() != '') {
        let end_date = dateToYMD(new Date($('input[name="end_date"]').val()), short=true, sane=true);
        api_url = `${api_url}&end_date=${end_date}`
    }
    return api_url;
}


const loadCharts = async () => {
    chart_instances = []; // reset
    document.querySelector("#chart-container").innerHTML = ''; // reset

    const api_url = `/v1/timeline?${buildQueryParams()}`;

    try {
        var phase_stats_data = (await makeAPICall(api_url)).data
    } catch (err) {
        showNotification('Could not get compare in-repo data from API', err);
    }

    if (phase_stats_data == undefined) return;

    let legends = {};
    let series = {};

    let pproject_id = null

    phase_stats_data.forEach( (data) => {
        let [project_id, metric_name, detail_name, phase, value, unit, commit_hash, commit_timestamp] = data


        if (series[`${metric_name} - ${detail_name}`] == undefined) {
            series[`${metric_name} - ${detail_name}`] = {labels: [], values: [], notes: [], unit: unit, metric_name: metric_name, detail_name, detail_name}
        }

        series[`${metric_name} - ${detail_name}`].labels.push(commit_timestamp)
        series[`${metric_name} - ${detail_name}`].values.push({value: value, commit_hash: commit_hash})
        series[`${metric_name} - ${detail_name}`].notes.push({
            commit_timestamp: commit_timestamp,
            commit_hash: commit_hash,
            phase: phase,
            project_id: project_id,
            pproject_id: pproject_id,
        })

        pproject_id = project_id
    })

    for(my_series in series) {
        let badge = `<div class="description">
                <h4>Badges to share</h4>
                <div class="inline field">
                    <span class="energy-badge-container"><a href="/timeline.html?${buildQueryParams()}"><img src="${API_URL}/v1/badge/timeline?${buildQueryParams(skip_dates=false,metric_override=series[my_series].metric_name,detail_name=series[my_series].detail_name)}"></a></span>
                    <a href="#" class="copy-badge"><i class="copy icon"></i></a>
                </div>
            </div>`
        const element = createChartContainer("#chart-container", my_series, extra=badge);

        const chart_instance = echarts.init(element);

        const my_values = generateColoredValues(series[my_series].values);

        let data_series = [{
            name: my_series,
            type: 'bar',
            smooth: true,
            symbol: 'none',
            areaStyle: {},
            data: my_values,
            markLine: {
                precision: 4, // generally annoying that precision is by default 2. Wrong AVG if values are smaller than 0.001 and no autoscaling!
                data: [ {type: "average",label: {formatter: "AVG:\n{c}"}}]
            }
        }]

        let options = getLineBarChartOptions([], series[my_series].labels, data_series, 'Time', series[my_series].unit,  'category', null, false, null, true, false);

        options.tooltip = {
            trigger: 'item',
            formatter: function (params, ticket, callback) {
                if(params.componentType != 'series') return; // no notes for the MovingAverage
                return `<strong>${params.seriesName}</strong><br>
                        phase: ${series[params.seriesName].notes[params.dataIndex].phase}<br>
                        value: ${series[params.seriesName].values[params.dataIndex].value}<br>
                        timestamp: ${series[params.seriesName].notes[params.dataIndex].commit_timestamp}<br>
                        commit_hash: ${series[params.seriesName].notes[params.dataIndex].commit_hash}<br>
                        <br>
                        <i>Click to diff measurement with previous</i>
                        `;
            }
        };

        chart_instance.on('click', function (params) {
            if(params.componentType != 'series') return; // no notes for the MovingAverage
            window.open(`/compare.html?ids=${series[params.seriesName].notes[params.dataIndex].project_id},${series[params.seriesName].notes[params.dataIndex].pproject_id}`, '_blank');

        });


        chart_instance.setOption(options);
        chart_instances.push(chart_instance);

    }

    document.querySelectorAll(".copy-badge").forEach(el => {
        el.addEventListener('click', copyToClipboard)
    })
    document.querySelector('#api-loader')?.remove();
    setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
}

$(document).ready( (e) => {
    (async () => {
        $('#rangestart').calendar({
            type: 'date',
            endCalendar: $('#rangeend'),
            initialDate: new Date((new Date()).setDate((new Date).getDate() -30)),
        });
        $('#rangeend').calendar({
            type: 'date',
            startCalendar: $('#rangestart'),
            initialDate: new Date(),
        });

        await populateMachines();

        $('#submit').on('click', function() {
            loadCharts()
        });
        fillInputsFromURL();
        loadCharts()
    })();
});

