const metrics_info = {
  cpu_utilization_cgroup_container: {
      unit: 'Ratio',
      SI_conversion_factor: 100,  // CPU comes as ratio, but since stored as integer is was multiplicated with 100
      unit_after_conversion: '%'
  },
  cpu_energy_rapl_msr_system: {
      unit: 'mJ',
      SI_conversion_factor: 1000,
      unit_after_conversion: 'J'
  },
  atx_energy_dc_channel: {
      unit: 'mJ',
      SI_conversion_factor: 1000,
      unit_after_conversion: 'J'
  },
  memory_energy_rapl_msr_system: {
      unit: 'mJ',
      SI_conversion_factor: 1000,
      unit_after_conversion: 'J'
  },
  memory_total_cgroup_container: {
      unit: 'Bytes',
      SI_conversion_factor: 1000000,
      unit_after_conversion: 'MB'
  },
  network_io_cgroup_container: {
      unit: 'Bytes',
      SI_conversion_factor: 1000000,
      unit_after_conversion: 'MB'
  },
  cpu_time_cgroup_container: {
      unit: 'us',
      SI_conversion_factor: 1,
      unit_after_conversion: 'us'
  },
  cpu_time_cgroup_system: {
      unit: 'us',
      SI_conversion_factor: 1,
      unit_after_conversion: 'us'
  },
  cpu_time_procfs_system: {
      unit: 'us',
      SI_conversion_factor: 1,
      unit_after_conversion: 'us'
  }
}

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

const fillProjectTab = (selector, data) => {
    for (item in data) {
        if(typeof data[item] == 'object')
            fillProjectTab(selector, data[item])
        else
            document.querySelector(selector).insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${data?.[item]}</td></tr>`)

    }
}

const getMetrics = (stats_data, style='apex') => {
    const metrics = {cpu_load: [], mem_total: [], network_io: {}, series: {}, atx_energy: 0, cpu_energy: 0, memory_energy: 0}

    let accumulate = 0;


    const t0 = performance.now();

    stats_data.data.forEach(el => {
        const container_name = el[0];
        const time_in_ms = el[1] / 1000; // divide microseconds timestamp to ms to be handled by charting lib
        const metric_name = el[2];
        let value = el[3];

        accumulate = 0; // default

        // here we use the undivided time on purpose
        if (el[1] > stats_data.project.start_measurement && el[1] < stats_data.project.end_measurement) {
            accumulate = 1;
        }


        value = value / metrics_info[metric_name].SI_conversion_factor;

        if (metric_name == 'cpu_utilization_cgroup_container') {
            if (accumulate === 1) metrics.cpu_load.push(value);
        } else if (metric_name == 'cpu_energy_rapl_msr_system') {
            if (accumulate === 1) metrics.cpu_energy += value;
        } else if (metric_name == 'atx_energy_dc_channel') {
            if (accumulate === 1) metrics.atx_energy += value;
        } else if (metric_name == 'memory_energy_rapl_msr_system') {
            if (accumulate === 1) metrics.memory_energy += value;
        } else if (metric_name == 'memory_total_cgroup_container') {
            if (accumulate === 1) metrics.mem_total.push(value);
        } else if (metric_name == 'network_io_cgroup_container') {
            if (accumulate === 1) metrics.network_io[container_name] = value; // save only the last value per container (overwrite)
        }

        // Depending on the charting library the object has to be reformatted
        // First we check if structure is initialized
        if (metrics.series[metric_name] == undefined)  metrics.series[metric_name] = {};
        if (metrics.series[metric_name][container_name] == undefined) {
            metrics.series[metric_name][container_name] = { name: container_name, data: [] }
        }

        // now we handle the library specific formatting
        if(style=='apex') {
            metrics.series[metric_name][container_name]['data'].push({ x: time_in_ms, y: value })
        } else if(style=='echarts') {
            metrics.series[metric_name][container_name]['data'].push([time_in_ms, value])
        } else throw "Unknown chart style"
    })

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
            options.title.text = `${metric_name} ${metrics_info[metric_name].unit_after_conversion}`;
            options.series = Object.values(metrics[metric_name]);
            (new ApexCharts(element, options)).render();
        } else if(style == 'echarts') {
            var options = getEChartsOptions();
            options.title.text = `${metric_name} [${metrics_info[metric_name].unit_after_conversion}]`;
            for (container in metrics[metric_name]) {
                options.legend.data.push(container)
                options.series.push({
                    name: container,
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    areaStyle: {},
                    data: metrics[metric_name][container].data,
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

    // timestamp is in microseconds, therefore divide by 10**6
    const measurement_duration_in_s = (stats_data.project.end_measurement - stats_data.project.start_measurement) / 1000000;

    const atx_energy_in_mWh = ((metrics.atx_energy) / 3600) * 1000;
    const cpu_energy_in_mWh = ((metrics.cpu_energy) / 3600) * 1000;
    const memory_energy_in_mWh = ((metrics.memory_energy) / 3600) * 1000;
    let network_io = 0;
    for (item in metrics.network_io) {
        network_io +=  metrics.network_io[item];
    }
    const network_io_in_mWh = (network_io * 0.00006) * 1000000;
    const total_energy_in_mWh = cpu_energy_in_mWh + memory_energy_in_mWh + network_io_in_mWh;
    let total_CO2_in_kg = ( (total_energy_in_mWh / 1000000) * 519) / 1000;
    const daily_co2_budget_in_kg_per_day = 1.739; // (12.7 * 1000 * 0.05) / 365 from https://www.pawprint.eco/eco-blog/average-carbon-footprint-uk and https://www.pawprint.eco/eco-blog/average-carbon-footprint-globally
    let co2_budget_utilization = total_CO2_in_kg*100 / daily_co2_budget_in_kg_per_day;


    let co2_display = { value: total_CO2_in_kg, unit: 'kg'};
    if     (total_CO2_in_kg < 0.0000000001) co2_display = { value: total_CO2_in_kg*(10**12), unit: 'ng'};
    else if(total_CO2_in_kg < 0.0000001) co2_display = { value: total_CO2_in_kg*(10**9), unit: 'ug'};
    else if(total_CO2_in_kg < 0.0001) co2_display = { value: total_CO2_in_kg*(10**6), unit: 'mg'};
    else if(total_CO2_in_kg < 0.1) co2_display = { value: total_CO2_in_kg*(10**3), unit: 'g'};

    if(atx_energy_in_mWh) document.querySelector("#atx-energy").innerText = atx_energy_in_mWh.toFixed(2) + " mWh"
    if(cpu_energy_in_mWh) document.querySelector("#cpu-energy").innerText = cpu_energy_in_mWh.toFixed(2) + " mWh"
    if(cpu_energy_in_mWh) document.querySelector("#component-energy").innerText = (cpu_energy_in_mWh+memory_energy_in_mWh).toFixed(2) + " mWh"
    if(memory_energy_in_mWh) document.querySelector("#memory-energy").innerText = memory_energy_in_mWh.toFixed(2) + " mWh"
    if(cpu_energy_in_mWh) document.querySelector("#total-energy").innerText = (cpu_energy_in_mWh+memory_energy_in_mWh+network_io_in_mWh).toFixed(2) + " mWh"

    if(cpu_energy_in_mWh) document.querySelector("#component-power").innerText = ((metrics.cpu_energy+metrics.memory_energy)/measurement_duration_in_s).toFixed(2) + " W"
    if(atx_energy_in_mWh) document.querySelector("#atx-power").innerText = (metrics.atx_energy / measurement_duration_in_s).toFixed(2) + " W"


    if(network_io) document.querySelector("#network-io").innerText = network_io.toFixed(2) + " MB"
    if(network_io_in_mWh) document.querySelector("#network-energy").innerHTML = network_io_in_mWh.toFixed(2) + " mWh"

    if(co2_display.value) document.querySelector("#total-co2-internal").innerHTML = `${(co2_display.value).toFixed(2)} ${co2_display.unit}`
    if(co2_budget_utilization) document.querySelector("#co2-budget-utilization").innerHTML = (co2_budget_utilization).toFixed(2) + " %"

    if(metrics.cpu_load.length) {
        document.querySelector("#max-cpu-load").innerText = (Math.max.apply(null, metrics.cpu_load)) + " %"
        document.querySelector("#avg-cpu-load").innerText = ((metrics.cpu_load.reduce((a, b) => a + b, 0) / metrics.cpu_load.length)).toFixed(2) + " %"
    }
    if(metrics.mem_total.length) document.querySelector("#avg-mem-load").innerText = ((metrics.mem_total.reduce((a, b) => a + b, 0) / metrics.mem_total.length)).toFixed(2) + " MB"

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
            var notes_json = await makeAPICall('/v1/notes/' + url_params.get('id'))
            var stats_data = await makeAPICall('/v1/stats/single/' + url_params.get('id'))
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }
        $('.ui.secondary.menu .item').tab();

        const metrics = getMetrics(stats_data, 'echarts');
        fillProjectData(stats_data.project)
        displayGraphs(metrics.series, notes_json.data, 'echarts');
        fillAvgContainers(stats_data, metrics);
        document.querySelector('#api-loader').remove();

        // after all instances have been placed the flexboxes might have rearranged. We need to trigger resize
        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500); // needed for the graphs to resize

    })();
});
