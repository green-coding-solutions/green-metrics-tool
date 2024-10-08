
const getQueryParameters = (name) => {
    const urlParams = new URLSearchParams(window.location.search);
    const allParams = urlParams.getAll(name);
    return [...new Set(allParams)];
}

const dateTimePicker = () => {
    $('#rangestart').calendar({
        type: 'date',
        endCalendar: $('#rangeend')
    });
    $('#rangeend').calendar({
        type: 'date',
        startCalendar: $('#rangestart')
    });
}

const getChartOptionsScaffold = (type) => {
    if (type == 'bar') {
        return {
            yAxis: { type: 'value', gridIndex: 0, name: "Carbon [g]" },

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
    } else if (type == 'pie') {
        return option = {
          tooltip: {
            trigger: 'item'
          },
          legend: {
            top: '5%',
            left: 'center'
          },
          series: [
            {
              name: '',
              type: 'pie',
              radius: ['40%', '70%'],
              avoidLabelOverlap: false,
              label: {
                show: false,
                position: 'center'
              },
              emphasis: {
                label: {
                  show: true,
                  fontSize: 40,
                  fontWeight: 'bold'
                }
              },
              labelLine: {
                show: false
              },
              data: []
            }
          ]
        };
    }
}

const fillPieChart = (measurements, key) => {
    const options = getChartOptionsScaffold('pie');
    options.series[0].name = `Carbon by type [tons]`;

    const legend = new Set()
    const labels = []

    const dimensions = {}

    measurements.forEach(measurement => { // iterate over all measurements, which are in row order
        let [type, project, machine, source, tags, date, energy, carbon, carbon_intensity, record_count] = measurement;

        // TODO I need to dynamicall access the variable type and machine through the key variable

        if (dimensions[type] == undefined) dimensions[type] = carbon;
        else dimensions[type] += carbon;
    });

    for (let type in dimensions) {
        options.series[0].data.push({ value: dimensions[type], name: type })
        legend.add(type)

        labels.push({
            type: type,
            value: dimensions[type],
        })

    }


    options.legend.data = Array.from(legend)

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${escapeString(labels[params.componentIndex].type)}</strong><br>
                    Carbon: ${escapeString(labels[params.componentIndex].value)} kg<br>
                    `;
        }

    };
    return options
}

const fillBarChart = (measurements) => {
    const options = getChartOptionsScaffold('bar');
    options.title.text = `Carbon by day [tons]`;

    const legend = new Set()
    const labels = []

    measurements.forEach(measurement => { // iterate over all measurements, which are in row order
        let [type, project, machine, source, tags, date, energy, carbon, carbon_intensity, record_count] = measurement;

        options.series.push({
            type: 'bar',
            smooth: true,
            stack: date,
            name: type,
            data: [carbon],
            itemStyle: {
                borderWidth: .5,
                borderColor: '#000000',
              },
        })
        legend.add(type)

        labels.push({
            type: type,
            date: date,
            carbon: carbon,
        })

    });

    options.legend.data = Array.from(legend)

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${escapeString(labels[params.componentIndex].date)}</strong><br>
                    Type: ${escapeString(labels[params.componentIndex].type)}<br>
                    Carbon: ${escapeString(labels[params.componentIndex].carbon)}<br>

                    `;
        }

    };
    return options
}


const bindRefreshButton = (repo, branch, workflow_id, chart_instance) => {
    // When the user selects a subset of the measurement data via the date-picker
    $('#submit').on('click', async function () {
        refreshView();
    });
}

const refreshView = async () => {
    $('#filter_tags_container').hide();
    $('#barchart-container').hide();

    for (let instance in chart_instances) {
        chart_instances[instance].clear();
    }

    try {
        var measurements = await getMeasurements();
    } catch (err) {
        showNotification('Could not get data from API', err);
        return;
    }
    $('#no-data-message').remove();

    console.log(measurements)


    if (measurements.data.length == 0){
        showNotification('No data', 'We could not find any data. Please check your date and filter conditions.')
        return;
    }

    $('#barchart-container').show();
    $('#piechart-types-container').show();

    let options = fillBarChart(measurements.data);
    chart_instances['carbondb-bar-chart'].setOption(options);

    options = fillPieChart(measurements.data, 'type');
    chart_instances['carbondb-piechart-types-chart'].setOption(options);

    options = fillPieChart(measurements.data, 'machine');
    chart_instances['carbondb-machines-types-chart'].setOption(options);


    const tags = getQueryParameters('tags');
    if (tags.length > 0) {
        $('#filter_tags_container').show();
        $('#filter_tags').empty();
        const tagsFilterHtml = tags[0].split(',').map(tag => `<a class="ui tag label" href="${window.location}&tag=${escapeString(tag)}">${escapeString(tag)}</a>`).join(' ');
        $('#filter_tags').append(tagsFilterHtml);
    }
}

const getMeasurements = async () => {
    let start_date = $('#rangestart input').val();
    let end_date = $('#rangeend input').val();

    if (start_date == '') {
        start_date = dateToYMD(new Date((new Date()).setDate((new Date).getDate() -30)), short=true);
    } else {
        start_date = dateToYMD(new Date(start_date), short=true);
    }
    if (end_date == '') {
        end_date = dateToYMD(new Date(), short=true);
    } else {
        end_date = dateToYMD(new Date(end_date), short=true);
    }

    const type = '';
    const tags = getQueryParameters('tags');
    return await makeAPICall(`/v2/carbondb/?type=${type}&tags_include=${tags}&tags_exclude&start_date=${start_date}&end_date=${end_date}`);
}


// variables global to file
const chart_instances = {};


$(document).ready(function () {

    bindRefreshButton();
    dateTimePicker();

    chart_instances['carbondb-bar-chart'] = echarts.init(document.querySelector("#carbondb-bar-chart"));
    chart_instances['carbondb-piechart-types-chart'] = echarts.init(document.querySelector("#carbondb-piechart-types-chart"));
    chart_instances['carbondb-piechart-machines-chart'] = echarts.init(document.querySelector("#carbondb-piechart-machines-chart"));

    // TODO add all data from URL to filters view
    window.onresize = function () { // set callback when ever the user changes the viewport
        for (let instance in chart_instances) {
            chart_instances[instance].resize();
        }
    };

    (async () => {
        refreshView();
        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
    })();
});
