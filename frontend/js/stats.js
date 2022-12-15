var display_in_watts = localStorage.getItem('display_in_watts');
if(display_in_watts == 'true') display_in_watts = true;
else display_in_watts = false;

const getApexOptions = () => {
    return {
        series: null,
        chart: {
            type: 'area',
            animations: {
              enabled: false
            }
        },
        dataLabels: {
            enabled: false
        },
        stroke: {
            curve: 'smooth'
        },
        title: {
          text: '',
        },
        xaxis: {
          tickAmount: 6,
          type: "datetime"
        },
        annotations: {
            xaxis: []
        },
        tooltip: {
            enabled: true,
            shared: true,
            followCursor: true,
            x: {
              show: true,
              format: 'HH:mm:ss',
          },

        },
    };
}


const getEChartsOptions = () => {
    return {
        tooltip: {
            trigger: 'axis'
        },
        xAxis: {
           type: 'time',
           splitLine: {show: true}
        },

        yAxis: {
            type: 'value',
           splitLine: {show: true}
        },
        series: [],
        title: {text: null},
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

const fillProjectData = (project, key = null) => {
    for (item in project) {
        if (item == 'machine_specs') {
            fillProjectTab('#machine-specs', project[item])
        } else if(item == 'usage_scenario') {
            document.querySelector("#usage-scenario").insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td><pre>${JSON.stringify(project?.[item], null, 2)}</pre></td>`)

        } else if(item == 'measurement_config') {
            fillProjectTab('#measurement-config', project[item])
        }  else {

            document.querySelector('#project-data').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${project?.[item]}</td></tr>`)
        }
    }
}

const fillProjectTab = (selector, data, parent = '') => {
    for (item in data) {
        if(typeof data[item] == 'object')
            fillProjectTab(selector, data[item], `${item}.`)
        else
            document.querySelector(selector).insertAdjacentHTML('beforeend', `<tr><td><strong>${parent}${item}</strong></td><td>${data?.[item]}</td></tr>`)

    }
}

const convertValue = (metric_name, value, unit) => {
    switch (unit) {
      case 'mJ':
        return [value / 1000, 'J'];
        break;
      case 'mW':
        return [value / 1000, 'W'];
        break;
      case 'Ratio':
        return [value / 100, '%'];
        break;
      case 'centi°C':
        return [value / 100, '°C'];
        break;

      case 'Bytes':
        return [value / 1000000, 'MB'];
        break;
      default:
        return [value, unit];        // no conversion in default calse
    }

}

const getMetrics = (stats_data, style='apex') => {
    const metrics = {}
    let accumulate = 0;
    const t0 = performance.now();

   try {
         // define here as var (not let!), so we can alert it later in error case.
         // this was done, because we apparently often forget to add new metrics here and this helps debugging quickly with the alert later :)
        var metric_name = null

        // this can be let
        let time_before = 0;
        let detail_name = null;

        stats_data.data.forEach(el => {
            const time_after = el[1] / 1000000;
            const time_in_ms = el[1] / 1000; // divide microseconds timestamp to ms to be handled by charting lib
            let value = el[3];
            let metric_changed = false;
            let unit = el[4];

            if(metric_name !== el[2] || detail_name !== el[0]) {
                // metric changed -> reset time counter and update variables
                metric_name = el[2];
                detail_name = el[0];
                time_before = time_after;
                metric_changed = true;
            }

            accumulate = 0; // default

            // here we use the undivided time on purpose
            if (el[1] > stats_data.project.start_measurement && el[1] < stats_data.project.end_measurement) {
                accumulate = 1;
            }

            [value, unit] = convertValue(metric_name, value, unit);
            if (metrics[metric_name] == undefined) {
                metrics[metric_name] = {
                    series: {},
                    unit: unit,
                    sum: [],
                    converted_unit: unit
                }
            }

            if(accumulate) metrics[metric_name].sum.push(value); // we want the converted value, but not the Watts display. Adding only with Joules!

            if(display_in_watts && metrics[metric_name].unit == 'J') {
                value = value/(time_after-time_before); // convert Joules to Watts by dividing through the time difference of two measurements
                metrics[metric_name].converted_unit = 'W';
            } else if(!display_in_watts && metrics[metric_name].unit == 'W') {
                value = value*(time_after-time_before); // convert Joules to Watts by dividing through the time difference of two measurements
                metrics[metric_name].converted_unit = 'J';
            }
            time_before = time_after;

            if(metric_changed && display_in_watts) return; // if watts display then the first graph value will be zero. We skip that.

            // Depending on the charting library the object has to be reformatted
            // First we check if structure is initialized
            if (metrics[metric_name].series[detail_name] == undefined) {
                metrics[metric_name].series[detail_name] = { name: detail_name, data: [] }
            }

            // now we handle the library specific formatting
            if(style=='apex') {
                metrics[metric_name].series[detail_name]['data'].push({ x: time_in_ms, y: value})
            } else if(style=='echarts') {
                metrics[metric_name].series[detail_name]['data'].push([time_in_ms, value]);
            } else throw "Unknown chart style"

        })
    } catch (err) {
        alert(err)
        alert(metric_name)
    }

    const t1 = performance.now();
    console.log(`getMetrics Took ${t1 - t0} milliseconds.`);
    return metrics;
}

const displayGraphs = (metrics, notes, style='apex') => {

    let counter = 0; // for automatically creating pair of <div>s
    const note_positions = [
      'insideStartTop',
      'insideEndBottom'
    ];
    const chart_instances = [];
    const t0 = performance.now();

    for ( metric_name in metrics) {

        const element = createChartContainer("#chart-container", metric_name, counter);

        if(style=='apex') {
            charts = [];
            let options = getApexOptions();
            options.title.text = `${metric_name} ${metrics[metric_name].converted_unit}`;
            options.series = Object.values(metrics[metric_name].series);
            (new ApexCharts(element, options)).render();
        } else if(style == 'echarts') {
            var options = getEChartsOptions();
            options.title.text = `${metric_name} [${metrics[metric_name].converted_unit}]`;
            for (detail_name in metrics[metric_name].series) {
                options.legend.data.push(detail_name)
                options.series.push({
                    name: detail_name,
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    areaStyle: {},
                    data: metrics[metric_name].series[detail_name].data,
                    markLine: { data: [ {type: "average",label: {formatter: "AVG_ii:\n{c}"}}]}
                });
            }
            // now we add all notes to every chart
            options.legend.data.push('Notes')
            let notes_labels = [];
            let inner_counter = 0;
            notes.forEach(note => {
                notes_labels.push({xAxis: note[3]/1000, label: {formatter: note[2], position: note_positions[inner_counter%2]}})
                inner_counter++;
            })
            options.series.push({
                name: "Notes",
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: {},
                data: [],
                markLine: { data: notes_labels}
            });
            const chart_instance = echarts.init(element);
            chart_instance.setOption(options);
            chart_instances.push(chart_instance);

        } else {
            throw "Unknown chart style";
        }
        counter++;

    }

    const t1 = performance.now();
    console.log(`DisplayGraphs took ${t1 - t0} milliseconds.`);

    window.onresize = function() { // set callback when ever the user changes the viewport
        chart_instances.forEach(chart_instance => {
            chart_instance.resize();
        })
    }
}


const createChartContainer = (container, el, counter) => {
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
    //document.querySelector(container).parentNode.insertBefore(chart_node, null);
    return chart_node.querySelector('.statistics-chart');
}

const createAvgContainer = (metric_name, value, unit) => {

    const node = document.createElement("div")
    node.classList.add("card");
    node.classList.add('ui')

    let color = 'grey';
    let icon = 'circle'
    let explaination = '';

    if(metric_name.indexOf('_container') !== -1) explaination = 'all containers';

    if(metric_name.indexOf('_energy_') !== -1) {
        color = 'orange';
        icon = 'power off';
        if (unit == 'W') explaination = 'system (avg.)';
        else explaination = 'system';
    } else if(metric_name.indexOf('memory_total_') !== -1) {
        color = 'purple';
        icon = 'memory';
        explaination = 'max. load - all containers'

    } else if(metric_name.indexOf('network_io') !== -1) {
        color = 'blue';
        icon = 'exchange alternate';
        explaination = '<a href="https://docs.green-coding.org/docs/measuring/metric-providers/network-io-cgroup-container/"><i class="question circle icon"></i></a>'
    } else if(metric_name.indexOf('cpu_utilization') !== -1) {
        if(metric_name.indexOf('_system') !== -1) explaination = 'system';
        color = 'yellow';
        icon = 'memory';
    }

    node.innerHTML = `
        <div class="ui content">
            <div class="ui top attached ${color} label overflow-ellipsis">${metric_name}</div>
            <div class="description">
                <div class="ui mini statistic">
                    <div class="value">
                        <i class="${icon} icon"></i> ${value.toFixed(2)} ${unit}
                    </div>
                </div>
                <div class="ui bottom right attached label">${explaination}</div>
            </div>
        </div>`;

    if(metric_name.indexOf('_container') !== -1) document.querySelector('#container-level-metrics').appendChild(node)
    else if(metric_name.indexOf('_system') !== -1) document.querySelector('#system-level-metrics').appendChild(node)
    else document.querySelector('#extra-metrics').appendChild(node)

    return node;
}


const createGraph = (element, data, labels, title) => {
  // console.log('labels', labels)
  return new Dygraph(element, data, {
      labels,
      fillGraph: true,
      rollPeriod: 10,
      showRoller: true,
      title,
      legend: "always",
      labelsSeparateLines: true,
      highlightSeriesOpts: { strokeWidth: 2 },
    // showLabelsOnHighlight: false,
    axes: {
        x: {
            axisLabelFormatter: Dygraph.dateAxisLabelFormatter,
            ticker: Dygraph.dateTicker,
        },
    },
    drawCallback: function (g) {
        const notes = document.getElementsByClassName('dygraph-annotation');
        for (let i = 0; i < notes.length; i++) {
            if (notes[i].style.top === "") notes[i].style.display = "none";
        }
    },
    annotationMouseOverHandler: function (ann, point, dg, event) {
        $(ann.div)
        .popup({
            title   : 'Note',
            content : ann.text,
            variation: 'mini',
            inline: true
        }).popup("show")
    },
    annotationMouseOutHandler: function (ann, point, dg, event) {
        $(ann.div)
        .popup("hide")
    },
});
};

const fillAvgContainers = (stats_data, metrics) => {

    // let total_energy_in_mWh = 0;
    let component_energy_in_mWh = 0;
    let network_io = 0;
    for (metric_name in metrics) {
        let acc = metrics[metric_name].sum.reduce((a, b) => a + b, 0)
        let max = (Math.max.apply(null, metrics[metric_name].sum))

        switch(metrics[metric_name].unit) {
            case 'J':
                if(display_in_watts) createAvgContainer(metric_name, (acc / 3600) * 1000, 'mWh');
                else createAvgContainer(metric_name, acc, 'J');
                createAvgContainer(metric_name, acc / stats_data.project.measurement_duration_in_s, 'W');
                break;
            case 'W':
                createAvgContainer(metric_name, acc / metrics[metric_name].sum.length, 'W');
                createAvgContainer(metric_name, ((acc / metrics[metric_name].sum.length)*stats_data.project.measurement_duration_in_s)/3.6, ' mWh (approx!)');
                break;
            case '%':
                createAvgContainer(metric_name, acc / metrics[metric_name].sum.length, '%');
                createAvgContainer(metric_name, max, '% (Max)');
                break;
            case 'MB':
                createAvgContainer(metric_name, max, 'MB');
                break;
            case 'us':
                // createAvgContainer(metric_name, max, 'seconds'); // no avg needed for now
                break;
            case '°C':
                // no avg needed for now
                break;
            case 'RPM':
                createAvgContainer(metric_name, acc / metrics[metric_name].sum.length, 'RPM (approx.)');
                break;

            default:
                alert(`Unknown unit encountered in ${metric_name}: ${metrics[metric_name].unit}`);
        }

        // handle compound metrics
        if(metric_name == 'cpu_energy_rapl_msr_system' || metric_name == 'memory_energy_rapl_msr_system') {
            component_energy_in_mWh += acc;
        }
        if(metric_name == 'network_io_cgroup_container') {
            network_io += max;
        }

    }

    if(display_in_watts) {
        document.querySelector("#component-energy").innerHTML = `${(component_energy_in_mWh / 3.6).toFixed(2)} mWh`
    } else {
        document.querySelector("#component-energy").innerHTML = `${(component_energy_in_mWh).toFixed(2)} J`
    }
    document.querySelector("#component-power").innerHTML = `${(component_energy_in_mWh / stats_data.project.measurement_duration_in_s).toFixed(2)} W`

    // network via formula: https://www.green-coding.org/co2-formulas/
    const network_io_in_mWh = (network_io * 0.00006) * 1000000;
    if(network_io_in_mWh) document.querySelector("#network-energy").innerHTML = `${network_io_in_mWh.toFixed(2)} mWh`
    const network_io_co2_in_kg = ( (network_io_in_mWh / 1000000) * 519) / 1000;
    if(network_io_co2_in_kg) document.querySelector("#network-co2").innerHTML = `${network_io_co2_in_kg.toFixed(2)} kg`

    // co2 calculations
    let total_CO2_in_kg = ( ((component_energy_in_mWh + network_io_co2_in_kg) / 1000000) * 519) / 1000;
    const daily_co2_budget_in_kg_per_day = 1.739; // (12.7 * 1000 * 0.05) / 365 from https://www.pawprint.eco/eco-blog/average-carbon-footprint-uk and https://www.pawprint.eco/eco-blog/average-carbon-footprint-globally
    let co2_budget_utilization = total_CO2_in_kg*100 / daily_co2_budget_in_kg_per_day;
    let co2_display = { value: total_CO2_in_kg, unit: 'kg'};
    if     (total_CO2_in_kg < 0.0000000001) co2_display = { value: total_CO2_in_kg*(10**12), unit: 'ng'};
    else if(total_CO2_in_kg < 0.0000001) co2_display = { value: total_CO2_in_kg*(10**9), unit: 'ug'};
    else if(total_CO2_in_kg < 0.0001) co2_display = { value: total_CO2_in_kg*(10**6), unit: 'mg'};
    else if(total_CO2_in_kg < 0.1) co2_display = { value: total_CO2_in_kg*(10**3), unit: 'g'};

    if (co2_display.value) document.querySelector("#component-co2").innerHTML = `${(co2_display.value).toFixed(2)} ${co2_display.unit}`
    if (co2_budget_utilization) document.querySelector("#co2-budget-utilization").innerHTML = (co2_budget_utilization).toFixed(2) + " %"

    upscaled_CO2_in_kg = total_CO2_in_kg * 100 * 30 ; // upscaled by 30 days for 10.000 requests (or runs) per day

    if(upscaled_CO2_in_kg) {
        document.querySelector("#trees").innerText = (upscaled_CO2_in_kg / 0.06 / 1000).toFixed(2);
        document.querySelector("#miles-driven").innerText = (upscaled_CO2_in_kg / 0.000403 / 1000).toFixed(2);
        document.querySelector("#gasoline").innerText = (upscaled_CO2_in_kg / 0.008887 / 1000).toFixed(2);
        // document.querySelector("#smartphones-charged").innerText = (upscaled_CO2_in_kg / 0.00000822 / 1000).toFixed(2);
        document.querySelector("#flights").innerText = (upscaled_CO2_in_kg / 1000).toFixed(2);
    }


}


/* Chart starting code*/
$(document).ready( (e) => {
    (async () => {
        const query_string = window.location.search;
        const url_params = (new URLSearchParams(query_string))

        try {
            var project_data = await makeAPICall('/v1/project/' + url_params.get('id'))
        } catch (err) {
            showNotification('Could not get project data from API', err);
        }
        try {
            var stats_data = await makeAPICall('/v1/stats/single/' + url_params.get('id'))
        } catch (err) {
            showNotification('Could not get stats data from API', err);
        }
        try {
            var notes_json = await makeAPICall('/v1/notes/' + url_params.get('id'))
        } catch (err) {
            showNotification('Could not get notes data from API', err);
        }

        $('.ui.secondary.menu .item').tab();

        if (typeof project_data === 'undefined') {
            return;
        }
        fillProjectData(project_data)

        if (stats_data.success == false) {
            return;
        }

        const metrics = getMetrics(stats_data, 'echarts');

        // create new custom field
        // timestamp is in microseconds, therefore divide by 10**6
        stats_data.project['measurement_duration_in_s'] = (stats_data.project?.end_measurement - stats_data.project?.start_measurement) / 1000000

        fillAvgContainers(stats_data, metrics);

        if (notes_json.success == false) {
            return;
        }
        displayGraphs(metrics, notes_json.data, 'echarts');
        document.querySelector('#api-loader').remove();

        // after all instances have been placed the flexboxes might have rearranged. We need to trigger resize
        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500); // needed for the graphs to resize

    })();
});
