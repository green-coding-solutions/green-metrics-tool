
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

const getChartOptionsScaffold = (type, dimension = 'Carbon [g]') => {
    if (type == 'bar') {
        return {
            yAxis: { type: 'value', gridIndex: 0, name: dimension },

            xAxis: {type: "category", data: ["Time"]},
            series: [],
            title: { text: null },
            animation: false,
            legend: {
                data: [],
                bottom: 0,
                type: 'scroll',
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
          title: { text: null },
          tooltip: {
            trigger: 'item'
          },
          legend: {
            top: '5%',
            left: 'right',
            type: 'scroll',
            orient: 'vertical',
          },
          series: [
            {
              name: '',
              type: 'pie',
              radius: ['40%', '70%'],
              padAngle: 50,
              itemStyle: {
                borderRadius: 5
              },
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

const fillPieChart = (key, dimensions) => {
    const options = getChartOptionsScaffold('pie');
    options.title.text = `Carbon by ${key} [g]`;

    const legend = new Set()
    const labels = []

    for (let el in dimensions) {
        options.series[0].data.push({ value: dimensions[el], name: dimensions_lookup[`${key}s`][el] })
        legend.add(dimensions_lookup[`${key}s`][el])

        labels.push({
            key: dimensions_lookup[`${key}s`][el],
            value: dimensions[el],
        })

    }


    options.legend.data = Array.from(legend)

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${escapeString(labels[params.dataIndex].key)}</strong><br>
                    Carbon: ${escapeString(labels[params.dataIndex].value)} g<br>
                    `;
        }

    };

    return options;
}

const fillBarChart = (type, legend, labels, series) => {
    let options = null;
    if (type == 'Carbon') {
        options = getChartOptionsScaffold('bar');

    } else {
        options = getChartOptionsScaffold('bar', 'Energy [mJ]');
    }
    options.title.text = `${type}`;

    options.series = series;
    options.legend.data = Array.from(legend)

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${escapeString(labels[params.componentIndex].date)}</strong><br>
                    Type: ${escapeString(labels[params.componentIndex].type)}<br>
                    Value: ${escapeString(labels[params.componentIndex].value)} ${escapeString(labels[params.componentIndex].unit)}<br>

                    `;
        }

    };
    return options;
}

const buildQueryParams = () => {
    let api_url = `start_date=${$('#rangestart input').val()}`;
    api_url = `${api_url}&end_date${$('#rangeend input').val()}`;

    api_url = `${api_url}&types_include${$('#types-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&types_exclude${$('#types-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&tags_include${$('#tags-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&tags_exclude${$('#tags-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&machines_include${$('#machines-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&machines_exclude${$('#machines-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&projects_include${$('#projects-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&projects_exclude${$('#projects-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&sources_include${$('#sources-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&sources_exclude${$('#sources-exclude').dropdown('get values').join(',')}`;


    return api_url;
}

const bindRefreshButton = (repo, branch, workflow_id, chart_instance) => {
    $('#submit').on('click', async function () {
        history.pushState(null, '', `${window.location.origin}${window.location.pathname}?${buildQueryParams()}`); // replace URL to bookmark!
        refreshView();
    });
}

const processData = (measurements) => {

    const carbon_barchart_data = {legend: new Set(), labels: [], series: []};
    const energy_barchart_data = {legend: new Set(), labels: [], series: []};
    const piechart_types_data = {};
    const piechart_machines_data = {};
    const piechart_projects_data = {};
    const piechart_sources_data = {};

    let total_carbon = 0;
    let total_energy = 0;
    const carbon_intensity_list = [];

    measurements.forEach(measurement => { // iterate over all measurements, which are in row order
        let [type, project, machine, source, tags, date, energy, carbon, carbon_intensity, record_count] = measurement;

        total_carbon += carbon;
        total_energy += energy;
        carbon_intensity_list.push(carbon_intensity);

        carbon_barchart_data.series.push({
            type: 'bar',
            smooth: true,
            stack: date,
            name: dimensions_lookup['types'][type] ,
            data: [carbon],
            itemStyle: {
                borderWidth: .5,
                borderColor: '#000000',
              },
        })
        carbon_barchart_data.legend.add(dimensions_lookup['types'][type])

        carbon_barchart_data.labels.push({
            type: dimensions_lookup['types'][type],
            date: date,
            value: carbon,
            unit: 'g',
        })

        energy_barchart_data.series.push({
            type: 'bar',
            smooth: true,
            stack: date,
            name: dimensions_lookup['types'][type] ,
            data: [energy],
            itemStyle: {
                borderWidth: .5,
                borderColor: '#000000',
              },
        })
        energy_barchart_data.legend.add(dimensions_lookup['types'][type])

        energy_barchart_data.labels.push({
            type: dimensions_lookup['types'][type],
            date: date,
            value: energy,
            unit: 'mJ',
        })

        if (piechart_machines_data[machine] == undefined) piechart_machines_data[machine] = carbon;
        else piechart_machines_data[machine] += carbon;

        if (piechart_types_data[type] == undefined) piechart_types_data[type] = carbon;
        else piechart_types_data[type] += carbon;

        if (piechart_projects_data[project] == undefined) piechart_projects_data[project] = carbon;
        else piechart_projects_data[project] += carbon;

        if (piechart_sources_data[source] == undefined) piechart_sources_data[source] = carbon;
        else piechart_sources_data[source] += carbon;


    });

    const total_machines = Object.keys(piechart_machines_data).length;
    const carbon_per_machine = total_carbon / total_machines;
    const carbon_per_project = total_carbon / Object.keys(piechart_projects_data).length;

    const avg_carbon_intensity = carbon_intensity_list.reduce((sum, value) => sum + value, 0) / carbon_intensity_list.length;

    return [carbon_barchart_data, energy_barchart_data, piechart_types_data, piechart_machines_data, piechart_projects_data, piechart_sources_data, total_carbon, total_energy, total_machines, carbon_per_machine, carbon_per_project, avg_carbon_intensity];
}

const refreshView = async () => {
    $('.carbondb-data').hide();

    for (let instance in chart_instances) {
        chart_instances[instance].clear();
    }

    try {
        var measurements = await getMeasurements();
        $('#no-data-message').hide();
    } catch (err) {
        showNotification('Could not get data from API', err);
        $('#no-data-message').show();
        return;
    }


    if (measurements.data.length == 0){
        $('#no-data-message').show();
        showNotification('No data', 'We could not find any data. Please check your date and filter conditions.')
        return;
    }

    const [carbon_barchart_data, energy_barchart_data, piechart_types_data, piechart_machines_data, piechart_projects_data, piechart_sources_data, total_carbon, total_energy, total_machines, carbon_per_machine, carbon_per_project, avg_carbon_intensity] = processData(measurements.data);

    $('.carbondb-data').show();

    let options = fillBarChart('Carbon', carbon_barchart_data.legend, carbon_barchart_data.labels, carbon_barchart_data.series);
    chart_instances['carbondb-barchart-carbon-chart'].setOption(options);

    options = fillBarChart('Energy', energy_barchart_data.legend, energy_barchart_data.labels, energy_barchart_data.series);
    chart_instances['carbondb-barchart-energy-chart'].setOption(options);

    options = fillPieChart('type', piechart_types_data);
    chart_instances['carbondb-piechart-types-chart'].setOption(options);

    options = fillPieChart('machine', piechart_machines_data);
    chart_instances['carbondb-piechart-machines-chart'].setOption(options);

    options = fillPieChart('project', piechart_projects_data);
    chart_instances['carbondb-piechart-projects-chart'].setOption(options);

    options = fillPieChart('source', piechart_sources_data);
    chart_instances['carbondb-piechart-sources-chart'].setOption(options);


    $('#total-carbon').text(total_carbon);
    $('#total-energy').text(total_energy);
    $('#total-machines').text(total_machines);
    $('#carbon-per-machine').text(carbon_per_machine);
    $('#carbon-per-project').text(carbon_per_project);
    $('#avg-carbon-intensity').text(avg_carbon_intensity);

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

    const types_include = $('#types-include').dropdown('get values').join(',');
    const types_exclude = $('#types-exclude').dropdown('get values').join(',');

    const tags_include = $('#tags-include').dropdown('get values').join(',');
    const tags_exclude = $('#tags-exclude').dropdown('get values').join(',');

    const machines_include = $('#machines-include').dropdown('get values').join(',');
    const machines_exclude = $('#machines-exclude').dropdown('get values').join(',');

    const projects_include = $('#projects-include').dropdown('get values').join(',');
    const projects_exclude = $('#projects-exclude').dropdown('get values').join(',');

    const sources_include = $('#sources-include').dropdown('get values').join(',');
    const sources_exclude = $('#sources-exclude').dropdown('get values').join(',');


    return await makeAPICall(`/v2/carbondb?types_include=${types_include}&types_exclude=${types_exclude}&tags_include=${tags_include}&tags_exclude=${tags_exclude}&machines_include=${machines_include}&machines_exclude=${machines_exclude}&projects_include=${projects_include}&projects_exclude=${projects_exclude}&sources_include=${sources_include}&sources_exclude=${sources_exclude}&start_date=${start_date}&end_date=${end_date}`);
}

const populatePossibleFilters = (filters) => {
    for (dimension in filters.data) {
        for (element in filters.data[dimension]) {
            document.querySelector(`#${dimension}-include`).appendChild(new Option(filters.data[dimension][element], element));
            document.querySelector(`#${dimension}-exclude`).appendChild(new Option(filters.data[dimension][element], element));
        }
    }
}

const selectFilters = (selector, param) => {
    const query_params = getQueryParameters(param);

    if (query_params.length <= 0) return;

    const values = query_params[0].split(',');
    $(selector).dropdown('set exactly', values);
}


// variables global to file
const chart_instances = {};
let dimensions_lookup = {}

$(document).ready(function () {

    bindRefreshButton();
    dateTimePicker();

    $('.ui.accordion').accordion();

    chart_instances['carbondb-barchart-carbon-chart'] = echarts.init(document.querySelector("#carbondb-barchart-carbon-chart"));
    chart_instances['carbondb-barchart-energy-chart'] = echarts.init(document.querySelector("#carbondb-barchart-energy-chart"));
    chart_instances['carbondb-piechart-types-chart'] = echarts.init(document.querySelector("#carbondb-piechart-types-chart"));
    chart_instances['carbondb-piechart-machines-chart'] = echarts.init(document.querySelector("#carbondb-piechart-machines-chart"));
    chart_instances['carbondb-piechart-projects-chart'] = echarts.init(document.querySelector("#carbondb-piechart-projects-chart"));
    chart_instances['carbondb-piechart-sources-chart'] = echarts.init(document.querySelector("#carbondb-piechart-sources-chart"));

    window.onresize = function () { // set callback when ever the user changes the viewport
        for (let instance in chart_instances) {
            chart_instances[instance].resize();
        }
    };

    (async () => {
        try {
            var filters = await makeAPICall(`/v2/carbondb/filters`);
        } catch(err) {
            showNotification('Could not get data from API', err);
            $('#no-data-message').show();
            $('.carbondb-data').hide();
            return;
        }
        populatePossibleFilters(filters);
        dimensions_lookup = filters.data;

        $('#types-include').dropdown({keepSearchTerm: true});
        $('#types-exclude').dropdown({keepSearchTerm: true});
        $('#tags-include').dropdown({keepSearchTerm: true});
        $('#tags-exclude').dropdown({keepSearchTerm: true});
        $('#machines-include').dropdown({keepSearchTerm: true});
        $('#machines-exclude').dropdown({keepSearchTerm: true});
        $('#projects-include').dropdown({keepSearchTerm: true});
        $('#projects-exclude').dropdown({keepSearchTerm: true});
        $('#sources-include').dropdown({keepSearchTerm: true});
        $('#sources-exclude').dropdown({keepSearchTerm: true});

        selectFilters('#types-include', 'types_include');
        selectFilters('#types-exclude', 'types_exclude');
        selectFilters('#tags-include', 'tags_include');
        selectFilters('#tags-exclude', 'tags_exclude');
        selectFilters('#machines-include', 'machines_include');
        selectFilters('#machines-exclude', 'machines_exclude');
        selectFilters('#project-include', 'project_include');
        selectFilters('#project-exclude', 'project_exclude');
        selectFilters('#source-include', 'source_include');
        selectFilters('#source-exclude', 'source_exclude');

        $('#rangestart').calendar('set date', getQueryParameters('start_date'));
        $('#rangeend').calendar('set date', getQueryParameters('end_date'));

        refreshView();

        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
    })();
});
