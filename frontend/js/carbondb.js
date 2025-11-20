"use strict";

const getChartOptionsScaffold = (chart_type, dimension, unit) => {
    const customColors = {
        'carbon': ['#5470C6', '#91CC75', '#EE6666', '#FAC858', '#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC','#D4A5A5', '#FFD700', '#7B68EE', '#FF69B4', '#2E8B57', '#DAA520', '#CD5C5C', '#4B0082'],
        'energy': ['#5470C6', '#91CC75', '#EE6666', '#FAC858', '#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC','#D4A5A5', '#FFD700', '#7B68EE', '#FF69B4', '#2E8B57', '#DAA520', '#CD5C5C', '#4B0082'],
        'type': ['#5470C6', '#91CC75', '#EE6666', '#FAC858', '#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC','#D4A5A5', '#FFD700', '#7B68EE', '#FF69B4', '#2E8B57', '#DAA520', '#CD5C5C', '#4B0082'],
        'machine': ['#FF4500', '#6A5ACD', '#4682B4', '#D2691E', '#FF6347', '#00FA9A', '#FF1493', '#BA55D3', '#800080','#5F9EA0', '#FF8C00', '#4169E1', '#DB7093', '#B0E0E6', '#F4A460', '#8B4513', '#FF00FF'],
        'project': ['#AFEEEE', '#2F4F4F', '#FA8072', '#20B2AA', '#FFFACD', '#D3D3D3', '#40E0D0', '#C71585', '#66CDAA','#FFDAB9', '#A9A9A9', '#8A2BE2', '#B22222', '#F08080'],
        'source': ['#1ABC9C','#2ECC71','#3498DB','#9B59B6','#E74C3C','#F1C40F','#E67E22','#16A085','#27AE60','#2980B9','#8E44AD','#C0392B','#F39C12','#D35400','#34495E'],
        'user': ['#1ABC9C','#2ECC71','#3498DB','#9B59B6','#E74C3C','#F1C40F','#E67E22','#16A085','#27AE60','#2980B9','#8E44AD','#C0392B','#F39C12','#D35400','#34495E'],
    }

    if (chart_type == 'bar') {
        return {
            color: customColors[dimension],
            yAxis: { type: 'value', gridIndex: 0, name: `${dimension} ${unit}` },
            xAxis: {type: "category", data: ["Timeline (days)"]},
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
    } else if (chart_type == 'pie') {
        return {
          color: customColors[dimension],
          title: { text: null },
          tooltip: {
            trigger: 'item'
          },
          legend: {
            bottom: 0,
            type: 'scroll',
            orient: 'horizontal'
          },
          series: [
            {
              name: '',
              type: 'pie',
              radius: ['25%', '50%'],
              avoidLabelOverlap: false,
              emphasis: {
                label: {
                  show: true,
                  fontSize: 20,
                  fontWeight: 'bold'
                }
              },
              labelLine: {
                show: true
              },
              data: []
            }
          ]
        };
    }
}

const fillPieChart = (dimension, legend, labels, series) => {
    const options = getChartOptionsScaffold('pie', dimension, '[kg]');
    options.title.text = `carbon by ${dimension} [kg]`;

    options.series[0].data = series;
    options.legend.data = Array.from(legend);

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${escapeString(labels[params.dataIndex].key)}</strong><br>
                    Carbon: ${escapeString(labels[params.dataIndex].value)} kg<br>
                    `;
        }

    };

    return options;
}

const fillBarChart = (y_axis, legend, labels, series) => {
    let options = null;
    if (y_axis == 'carbon') {
        options = getChartOptionsScaffold('bar', y_axis, '[kg]');

    } else {
        options = getChartOptionsScaffold('bar', y_axis, '[kWh]');
    }
    options.title.text = `${y_axis} by day`;

    options.series = series;
    options.legend.data = Array.from(legend)

    options.tooltip = {
        trigger: 'item',
        formatter: function (params, ticket, callback) {
            return `<strong>${escapeString(labels[params.componentIndex].date)}</strong><br>
                    Type: ${escapeString(labels[params.componentIndex].type)}<br>
                    Value: ${escapeString(labels[params.componentIndex].value)} ${escapeString(labels[params.componentIndex].unit)}<br>
                    Project: ${escapeString(labels[params.componentIndex].project)}<br>
                    Machine: ${escapeString(labels[params.componentIndex].machine)}<br>
                    Source: ${escapeString(labels[params.componentIndex].source)}<br>
                    Tags: ${escapeString(labels[params.componentIndex].tags)}<br>
                    User: ${escapeString(labels[params.componentIndex].user)}<br>
                    `;
        }

    };
    return options;
}

const buildQueryParams = () => {
    let api_url = `start_date=${dateToYMD(new Date($('#rangestart input').val()), /*short= */true)}`;
    api_url = `${api_url}&end_date=${dateToYMD(new Date($('#rangeend input').val()), /*short= */true)}`;

    api_url = `${api_url}&types_include=${$('#types-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&types_exclude=${$('#types-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&tags_include=${$('#tags-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&tags_exclude=${$('#tags-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&machines_include=${$('#machines-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&machines_exclude=${$('#machines-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&projects_include=${$('#projects-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&projects_exclude=${$('#projects-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&sources_include=${$('#sources-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&sources_exclude=${$('#sources-exclude').dropdown('get values').join(',')}`;

    api_url = `${api_url}&users_include=${$('#users-include').dropdown('get values').join(',')}`;
    api_url = `${api_url}&users_exclude=${$('#users-exclude').dropdown('get values').join(',')}`;

    return api_url;
}


const processData = (measurements) => {

    const carbon_barchart_data = {legend: new Set(), labels: [], series: []};
    const energy_barchart_data = {legend: new Set(), labels: [], series: []};

    let piechart_types_data = {legend: new Set(), labels: [], series: []};
    let piechart_machines_data = {legend: new Set(), labels: [], series: []};
    let piechart_projects_data = {legend: new Set(), labels: [], series: []};
    let piechart_sources_data = {legend: new Set(), labels: [], series: []};
    let piechart_users_data = {legend: new Set(), labels: [], series: []};

    // we need these to pre-aggregate for pie-charts
    // also we need Map as otherwise the order will get skewed and we need aligned order for same colors in charts
    const piechart_types_values = new Map();
    const piechart_machines_values = new Map();
    const piechart_projects_values = new Map();
    const piechart_sources_values = new Map();
    const piechart_users_values = new Map();



    let total_carbon = 0;
    let total_energy = 0;
    const carbon_intensity_list = [];

    measurements.forEach(measurement => { // iterate over all measurements, which are in row order
        let [type, project, machine, source, tags, date, energy, carbon, carbon_intensity, record_count, user] = measurement;

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
            project: dimensions_lookup['projects'][project],
            machine: dimensions_lookup['machines'][machine],
            source: dimensions_lookup['sources'][source],
            tags: tags.map( el => dimensions_lookup['tags'][el]),
            value: carbon,
            unit: 'kg',
            user: dimensions_lookup['users'][user],
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
            project: dimensions_lookup['projects'][project],
            machine: dimensions_lookup['machines'][machine],
            source: dimensions_lookup['sources'][source],
            tags: tags.map( el => dimensions_lookup['tags'][el]),
            value: energy,
            unit: 'kWh',
            user: dimensions_lookup['users'][user],
        })

        if (piechart_machines_values.get(machine) == null) piechart_machines_values.set(machine, carbon)
        else piechart_machines_values.set(machine, piechart_machines_values.get(machine) + carbon);

        if (piechart_types_values.get(type) == null) piechart_types_values.set(type, carbon);
        else piechart_types_values.set(type, piechart_types_values.get(type) + carbon);

        if (piechart_projects_values.get(project) == null) piechart_projects_values.set(project, carbon);
        else piechart_projects_values.set(project, piechart_projects_values.get(project) + carbon);

        if (piechart_sources_values.get(source) == null) piechart_sources_values.set(source, carbon);
        else piechart_sources_values.set(source, piechart_sources_values.get(source) + carbon);

        if (piechart_users_values.get(user) == null) piechart_users_values.set(user, carbon);
        else piechart_users_values.set(user, piechart_users_values.get(user) + carbon);
    });

    piechart_machines_data = transformPieChartData(piechart_machines_data, piechart_machines_values, 'machines')
    piechart_types_data = transformPieChartData(piechart_types_data, piechart_types_values, 'types')
    piechart_projects_data = transformPieChartData(piechart_projects_data, piechart_projects_values, 'projects')
    piechart_sources_data = transformPieChartData(piechart_sources_data, piechart_sources_values, 'sources')
    piechart_users_data = transformPieChartData(piechart_users_data, piechart_users_values, 'users')


    const total_machines = piechart_machines_data.labels.length
    const carbon_per_machine = total_carbon / total_machines;
    const carbon_per_project = total_carbon / piechart_machines_data.labels.length;

    // TODO: Currently this value is false high, because it includes embodied carbon in the total carbon value. Dividing by the energy alone is thus too high
    const avg_carbon_intensity = carbon_intensity_list.reduce((sum, value) => sum + value, 0) / carbon_intensity_list.length;

    return [carbon_barchart_data, energy_barchart_data, piechart_types_data, piechart_machines_data, piechart_projects_data, piechart_sources_data, piechart_users_data, total_carbon, total_energy, total_machines, carbon_per_machine, carbon_per_project, avg_carbon_intensity];
}

const transformPieChartData = (data, values, dimension) => {
    // we might have negative values in CarbonDB, which is fine. But they cannot show in PieCharts. Thus we transform
    values.forEach((value, key) => {
        data.series.push({ value: Math.abs(value), name: dimensions_lookup[dimension][key] })
        data.legend.add(dimensions_lookup[dimension][key])

        data.labels.push({
            key: dimensions_lookup[dimension][key],
            value: value,
        })
    });

    return data;
}

const refreshView = async () => {
    $('.carbondb-data').hide();

    for (const instance in chart_instances) {
        chart_instances[instance].clear();
    }

    let measurements = null;
    try {
        measurements = await makeAPICall(`/v2/carbondb?${buildQueryParams()}`);
        $('#no-data-message').hide();
    } catch (err) {
        showNotification('Could not get data from API', err);
        $('#no-data-message').show();
        return;
    }

    history.pushState(null, '', `${window.location.origin}${window.location.pathname}?${buildQueryParams()}`); // replace URL to bookmark!



    if (measurements.data.length == 0){
        $('#no-data-message').show();
        showNotification('No data', 'We could not find any data. Please check your date and filter conditions.')
        return;
    }

    const [carbon_barchart_data, energy_barchart_data, piechart_types_data, piechart_machines_data, piechart_projects_data, piechart_sources_data, piechart_users_data, total_carbon, total_energy, total_machines, carbon_per_machine, carbon_per_project, avg_carbon_intensity] = processData(measurements.data);

    $('.carbondb-data').show();

    let options = fillBarChart('carbon', carbon_barchart_data.legend, carbon_barchart_data.labels, carbon_barchart_data.series);
    chart_instances['carbondb-barchart-carbon-chart'].setOption(options);

    options = fillBarChart('energy', energy_barchart_data.legend, energy_barchart_data.labels, energy_barchart_data.series);
    chart_instances['carbondb-barchart-energy-chart'].setOption(options);

    options = fillPieChart('type', piechart_types_data.legend, piechart_types_data.labels, piechart_types_data.series);
    chart_instances['carbondb-piechart-types-chart'].setOption(options);

    options = fillPieChart('machine', piechart_machines_data.legend, piechart_machines_data.labels, piechart_machines_data.series);
    chart_instances['carbondb-piechart-machines-chart'].setOption(options);

    options = fillPieChart('project', piechart_projects_data.legend, piechart_projects_data.labels, piechart_projects_data.series);
    chart_instances['carbondb-piechart-projects-chart'].setOption(options);

    options = fillPieChart('source', piechart_sources_data.legend, piechart_sources_data.labels, piechart_sources_data.series);
    chart_instances['carbondb-piechart-sources-chart'].setOption(options);

    options = fillPieChart('user', piechart_users_data.legend, piechart_users_data.labels, piechart_users_data.series);
    chart_instances['carbondb-piechart-users-chart'].setOption(options);

    $('#total-carbon').html(`<span title="${total_carbon}">${total_carbon.toFixed(2)}</span>`);
    $('#total-energy').html(`<span title="${total_energy}">${total_energy.toFixed(2)}</span>`);
    $('#total-machines').html(`<span title="${total_machines}">${total_machines.toFixed(2)}</span>`);
    $('#carbon-per-machine').html(`<span title="${carbon_per_machine}">${carbon_per_machine.toFixed(2)}</span>`);
    $('#carbon-per-project').html(`<span title="${carbon_per_project}">${carbon_per_project.toFixed(2)}</span>`);
    $('#avg-carbon-intensity').html(`<span title="${avg_carbon_intensity}">${avg_carbon_intensity.toFixed(2)}</span>`);

    setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
}


const populatePossibleFilters = (filters) => {
    for (const dimension in filters.data) {
        for (const element in filters.data[dimension]) {
            document.querySelector(`#${dimension}-include`).appendChild(new Option(escapeString(filters.data[dimension][element]), element));
            document.querySelector(`#${dimension}-exclude`).appendChild(new Option(escapeString(filters.data[dimension][element]), element));
        }
    }
}

const selectFilters = (selector, value) => {

    if (value == null || value.length <= 0) return;

    const values = value.split(',');
    $(selector).dropdown('set exactly', values);
}


// variables global to file
const chart_instances = {};
let dimensions_lookup = {}

$(document).ready(function () {

    $('#submit').on('click', async function () {
        refreshView();
    });

    const url_params = getURLParams();

    if (Object.keys(url_params).length) document.querySelector('#filters-active').classList.remove('hidden');

    dateTimePicker(30, url_params);

    $('.ui.accordion').accordion();

    chart_instances['carbondb-barchart-carbon-chart'] = echarts.init(document.querySelector("#carbondb-barchart-carbon-chart"));
    chart_instances['carbondb-barchart-energy-chart'] = echarts.init(document.querySelector("#carbondb-barchart-energy-chart"));
    chart_instances['carbondb-piechart-types-chart'] = echarts.init(document.querySelector("#carbondb-piechart-types-chart"));
    chart_instances['carbondb-piechart-machines-chart'] = echarts.init(document.querySelector("#carbondb-piechart-machines-chart"));
    chart_instances['carbondb-piechart-projects-chart'] = echarts.init(document.querySelector("#carbondb-piechart-projects-chart"));
    chart_instances['carbondb-piechart-sources-chart'] = echarts.init(document.querySelector("#carbondb-piechart-sources-chart"));
    chart_instances['carbondb-piechart-users-chart'] = echarts.init(document.querySelector("#carbondb-piechart-users-chart"));

    window.onresize = function () { // set callback when ever the user changes the viewport
        for (const instance in chart_instances) {
            chart_instances[instance].resize();
        }
    };

    (async () => {
        let filters = null;
        try {
            filters = await makeAPICall(`/v2/carbondb/filters`);
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
        $('#users-include').dropdown({keepSearchTerm: true});
        $('#users-exclude').dropdown({keepSearchTerm: true});


        selectFilters('#types-include', url_params['types_include']);
        selectFilters('#types-exclude', url_params['types_exclude']);
        selectFilters('#tags-include', url_params['tags_include']);
        selectFilters('#tags-exclude', url_params['tags_exclude']);
        selectFilters('#machines-include', url_params['machines_include']);
        selectFilters('#machines-exclude', url_params['machines_exclude']);
        selectFilters('#projects-include', url_params['projects_include']);
        selectFilters('#projects-exclude', url_params['projects_exclude']);
        selectFilters('#sources-include', url_params['sources_include']);
        selectFilters('#sources-exclude', url_params['sources_exclude']);
        selectFilters('#users-include', url_params['users_include']);
        selectFilters('#users-exclude', url_params['users_exclude']);

        refreshView();

    })();
});
