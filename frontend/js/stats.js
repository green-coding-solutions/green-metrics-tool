var display_in_watts = localStorage.getItem('display_in_watts');
if(display_in_watts == 'true') display_in_watts = true;
else display_in_watts = false;

const rescaleCO2Value = (total_CO2_in_kg) => {
    if     (total_CO2_in_kg < 0.0000000001) co2_display = [total_CO2_in_kg*(10**12), 'ng'];
    else if(total_CO2_in_kg < 0.0000001) co2_display = [total_CO2_in_kg*(10**9), 'ug'];
    else if(total_CO2_in_kg < 0.0001) co2_display = [total_CO2_in_kg*(10**6), 'mg'];
    else if(total_CO2_in_kg < 0.1) co2_display = [total_CO2_in_kg*(10**3), 'g'];
    return co2_display;
}

const getLineChartOptions = (title, legend, series) => {
    return {
        tooltip: {
            trigger: 'axis'
        },
        title: {
            text:title
        },
        xAxis: {
            type: 'time',
            splitLine: {show: true}
        },
        yAxis: {
            type: 'value',
            splitLine: {show: true}
        },
        series: series,
        title: {text: null},
        animation: false,
        legend: {
            data: legend,
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

const getPieChartOptions = (name, data) => {
    return {
        tooltip: {
            trigger: 'item'
        },
        toolbox: {
            show: false,
        },
        series: [
            {
                name: name,
                type: 'pie',
                radius: [30, 100],
                center: ['50%', '50%'],
                roseType: 'radius',
                itemStyle: {
                    borderRadius: 2
                },
                data: data
            }
        ]
    };
}

const getBarChartOptions = (title, legend, series) => {
    return {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
              type: 'shadow' // 'shadow' as default; can also be 'line' or 'shadow'
          }
      },
      title: {
          left: 'center',
          text: title
      },
      legend: {
          top: "bottom",
      },

      yAxis: {
          type: 'value'
      },
      xAxis: {
          type: 'category',
          data: legend,
      },
      series: series
  };
}


const fillProjectData = (project_data, key = null) => {
    for (item in project_data) {
        if (item == 'machine_specs') {
            fillProjectTab('#machine-specs', project_data[item])
        } else if(item == 'usage_scenario') {
            document.querySelector("#usage-scenario").insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td><pre>${JSON.stringify(project_data?.[item], null, 2)}</pre></td>`)

        } else if(item == 'measurement_config') {
            fillProjectTab('#measurement-config', project_data[item])
        } else if(item == 'phases') {
            // skip
        } else if(item == 'id' || item == 'name') {
            document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${project_data?.[item]}</td></tr>`)
        } else if(item == 'uri') {
            let entry = project_data?.[item];
            if(project_data?.[item].indexOf('http') === 0) entry = `<a href="${project_data?.[item]}">${project_data?.[item]}</a>`;
            document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${entry}</td></tr>`);
        } else {
            document.querySelector('#project-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${project_data?.[item]}</td></tr>`)
        }

    }

    $('.ui.secondary.menu .item').tab(); // activate tabs for project data

    if (project_data.invalid_project) {
        showNotification('Project measurement has been marked as invalid', project_data.invalid_project);
        document.body.classList.add("invalidated-measurement")
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

const convertValue = (value, unit) => {
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
    case 'Hz':
        return [value / 1000000, 'GHz'];
        break;
    case 'ns':
        return [value / 1000000000, 's'];
        break;

    case 'Bytes':
        return [value / 1000000, 'MB'];
        break;
    default:
        return [value, unit];        // no conversion in default calse
    }

}

const getMetrics = (stats_data, start_measurement, end_measurement) => {
    const metrics = {}
    const t0 = performance.now();

    try {
         // define here as var (not let!), so we can alert it later in error case.
         // this was done, because we apparently often forget to add new metrics here and this helps debugging quickly with the alert later :)
        var metric_name = null

        // this can be let
        let time_before = 0;
        let detail_name = null;

        stats_data.forEach(el => {
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

            [value, unit] = convertValue(value, unit);
            if (metrics[metric_name] == undefined) {
                metrics[metric_name] = {
                    series: {},
                    unit: unit,
                    converted_unit: unit
                }
            }

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

            metrics[metric_name].series[detail_name]['data'].push([time_in_ms, value]);

        })
    } catch (err) {
        alert(err)
        alert(metric_name)
    }

    const t1 = performance.now();
    console.log(`getMetrics Took ${t1 - t0} milliseconds.`);
    return metrics;
}

const displayTimelineCharts = (metrics, notes) => {

    let counter = 0; // for automatically creating pair of <div>s
    const note_positions = [
        'insideStartTop',
        'insideEndBottom'
        ];
    const chart_instances = [];
    const t0 = performance.now();

    for ( metric_name in metrics) {

        const element = createChartContainer("#chart-container", metric_name, counter);

        let legend = [];
        let series = [];

        for (detail_name in metrics[metric_name].series) {
            legend.push(detail_name)
            series.push({
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
        legend.push('Notes')
        let notes_labels = [];
        let inner_counter = 0;
        notes.forEach(note => {
            notes_labels.push({xAxis: note[3]/1000, label: {formatter: note[2], position: note_positions[inner_counter%2]}})
            inner_counter++;
        });

        series.push({
            name: "Notes",
            type: 'line',
            smooth: true,
            symbol: 'none',
            areaStyle: {},
            data: [],
            markLine: { data: notes_labels}
        });

        const chart_instance = echarts.init(element);
        let options = getLineChartOptions(`${metric_name} [${metrics[metric_name].converted_unit}]`, legend, series);
        chart_instance.setOption(options);
        chart_instances.push(chart_instance);

        counter++;

    }

    const t1 = performance.now();
    console.log(`DisplayTimelineCharts took ${t1 - t0} milliseconds.`);

    window.onresize = function() { // set callback when ever the user changes the viewport
        chart_instances.forEach(chart_instance => {
            chart_instance.resize();
        })
    }

    document.querySelector('#api-loader').remove();
}

function moveRight(e) {
    let el = e.currentTarget.closest(".statistics-chart-card")
    const next = el.nextSibling;
    if (!next) return;
    next.after(el)
    window.dispatchEvent(new Event('resize'));
}

function moveToLast(e) {
    let el = e.currentTarget.closest(".statistics-chart-card")
    const last = el.parentNode.lastChild;
    last.after(el)
    window.dispatchEvent(new Event('resize'));
}

function moveLeft(e) {
    let el = e.currentTarget.closest(".statistics-chart-card")
    const previous = el.previousElementSibling;
    if (!previous) return;
    previous.before(el)
    window.dispatchEvent(new Event('resize'));
}

function moveToFirst(e) {
    let el = e.currentTarget.closest(".statistics-chart-card")
    const first = el.parentNode.childNodes[0];
    first.before(el)
    window.dispatchEvent(new Event('resize'));
}

function toggleWidth(e) {
    let chart = e.currentTarget.closest(".statistics-chart-card")
    let icon = e.currentTarget.firstChild

    chart.classList.toggle("full-width")
    if (chart.classList.contains("full-width"))
    {
        icon.classList.remove("expand")
        icon.classList.add("compress")
    }
    else
    {
        icon.classList.remove("compress")
        icon.classList.add("expand")
    }

    window.dispatchEvent(new Event('resize'));
}

function movers(e) {
    let icons = e.currentTarget.closest(".content").querySelector('.chart-navigation-icon')
    icons.classList.toggle("hide")
}

const createChartContainer = (container, el, counter) => {
    const chart_node = document.createElement("div")
    chart_node.classList.add("card");
    chart_node.classList.add('statistics-chart-card')
    chart_node.classList.add('ui')

    chart_node.innerHTML = `
        <div class="content">
            <div class="ui right floated icon buttons">
                <button class="ui button toggle-width"><i class="expand icon toggle-icon"></i></button>
            </div>
            <div class="ui right floated icon buttons">
                <button class="ui button movers"><i class="arrows alternate icon"></i></button>
            </div>
            <div class="ui right floated icon buttons chart-navigation-icon hide">
                <button class="ui button move-first"><i class="angle double left icon"></i></button>
                <button class="ui button move-left"><i class="angle left icon"></i></button>
                <button class="ui button move-right"><i class="angle right icon"></i></button>
                <button class="ui button move-last"><i class="angle double right icon"></i></button>
            </div>
            <div class="description">
                <div class="statistics-chart" id=${el}-chart></div>
            </div>
        </div>`;
    document.querySelector(container).appendChild(chart_node)

    chart_node.querySelector('.toggle-width').addEventListener("click", toggleWidth, false);
    chart_node.querySelector('.movers').addEventListener("click", movers, false);
    chart_node.querySelector('.move-first').addEventListener("click", moveToFirst, false);
    chart_node.querySelector('.move-left').addEventListener("click", moveLeft, false);
    chart_node.querySelector('.move-right').addEventListener("click", moveRight, false);
    chart_node.querySelector('.move-last').addEventListener("click", moveToLast, false);


    return chart_node.querySelector('.statistics-chart');
}

const createDetailMetricBoxes = (metric, phase) => {

    let phase_tab_node = document.querySelector(`a.step[data-tab='${phase}']`);

    if(phase_tab_node == null || phase_tab_node == undefined) {
        let runtime_tab_node = document.querySelector('a.runtime-step');
        let cloned_tab_node = runtime_tab_node.cloneNode(true);
        cloned_tab_node.style.display = '';
        cloned_tab_node.setAttribute('data-tab', phase);
        cloned_tab_node.querySelector('.title').innerHTML = `${phase} ${cloned_tab_node.querySelector('.title').innerHTML}`;
        runtime_tab_node.parentNode.insertBefore(cloned_tab_node, runtime_tab_node)

        let phase_step_node = document.querySelector('.runtime-tab');
        let cloned_step_node = phase_step_node.cloneNode(true);
        cloned_step_node.style.display = '';
        cloned_step_node.setAttribute('data-tab', phase);
        phase_step_node.parentNode.insertBefore(cloned_step_node, phase_step_node)
    }

    const node = document.createElement("div")
    node.classList.add("card");
    node.classList.add('ui')

    let explanation = `${metric.detail_name}`

    let max_label = ''
    if (metric.max != null) {
        max_label = `<div class="ui bottom left attached label">
        ${metric.max} ${metric.unit} (MAX)
        </div>`
    }

    node.innerHTML = `
        <div class="ui content">
            <div class="ui top attached ${metric.color} label overflow-ellipsis">${metric.clean_name}</div>
            <div class="description">
                <div class="ui fluid tiny statistic">
                    <div class="value">
                        <i class="${metric.icon} icon"></i> ${metric.value.toFixed(2)} <span class="si-unit">${metric.unit}</span>
                    </div>
                </div>
                ${max_label}
                <div class="ui bottom right attached label icon rounded" data-position="bottom left" data-inverted="" data-tooltip="Detail of what this is">
                    ${explanation}
                    <i class="question circle icon"></i>
                </div>
            </div>
        </div>`;

    if(metric.name.indexOf('_container') !== -1 || metric.name.indexOf('_vm') !== -1)
        document.querySelector(`div.tab[data-tab='${phase}'] div.container-level-metrics`).appendChild(node)
    else if(metric.name.indexOf('_system') !== -1)
        document.querySelector(`div.tab[data-tab='${phase}'] div.system-level-metrics`).appendChild(node)
    else
        document.querySelector(`div.tab[data-tab='${phase}'] div.extra-metrics`).appendChild(node)
}


const createKeyMetricBoxes = (energy, power, network_io, phase) => {

    const energy_in_mWh = energy / 3.6;
    if(display_in_watts) {
        document.querySelector(`div.tab[data-tab='${phase}'] .machine-energy`).innerHTML = `${energy_in_mWh.toFixed(2)} <span class="si-unit">mWh</span>`
    } else {
        document.querySelector(`div.tab[data-tab='${phase}'] .machine-energy`).innerHTML = `${energy.toFixed(2)} <span class="si-unit">J</span>`
    }

    document.querySelector(`div.tab[data-tab='${phase}'] .machine-power`).innerHTML = `${power.toFixed(2)} <span class="si-unit">W</span>`;

    // network via formula: https://www.green-coding.berlin/co2-formulas/
    const network_io_in_mWh = network_io * 0.00006 * 1000000;
    const network_io_in_J = network_io_in_mWh * 3.6;  //  60 * 60 / 1000 => 3.6
    if(display_in_watts) {
        if(network_io_in_mWh) document.querySelector(`div.tab[data-tab='${phase}'] .network-energy`).innerHTML = `${network_io_in_mWh.toFixed(2)} <span class="si-unit">mWh</span>`
    } else {
        if(network_io_in_J) document.querySelector(`div.tab[data-tab='${phase}'] .network-energy`).innerHTML = `${network_io_in_J.toFixed(2)} <span class="si-unit">J</span>`
    }

    // co2 calculations
const network_io_co2_in_kg = ( (network_io_in_mWh / 1000000) * 519) / 1000;
const [network_co2_value, network_co2_unit] = rescaleCO2Value(network_io_co2_in_kg)
if (network_co2_value) document.querySelector(`div.tab[data-tab='${phase}'] .network-co2`).innerHTML = `${(network_co2_value).toFixed(2)} <span class="si-unit">${network_co2_unit}</span>`

    const total_CO2_in_kg = ( ((energy_in_mWh + network_io_in_mWh) / 1000000) * 519) / 1000;
const [component_co2_value, component_co2_unit] = rescaleCO2Value(total_CO2_in_kg)
if (component_co2_value) document.querySelector(`div.tab[data-tab='${phase}'] .machine-co2`).innerHTML = `${(component_co2_value).toFixed(2)} <span class="si-unit">${component_co2_unit}</span>`

    const daily_co2_budget_in_kg_per_day = 1.739; // (12.7 * 1000 * 0.05) / 365 from https://www.pawprint.eco/eco-blog/average-carbon-footprint-uk and https://www.pawprint.eco/eco-blog/average-carbon-footprint-globally
const co2_budget_utilization = total_CO2_in_kg*100 / daily_co2_budget_in_kg_per_day;
if (co2_budget_utilization) document.querySelector("#co2-budget-utilization").innerHTML = (co2_budget_utilization).toFixed(2) + ' <span class="si-unit">%</span>'

    upscaled_CO2_in_kg = total_CO2_in_kg * 1000 * 365 ; // upscaled to 365 days for 1000 runs per day

if(upscaled_CO2_in_kg) {
    document.querySelector("#trees").innerText = (upscaled_CO2_in_kg / 0.06 / 1000).toFixed(2);
    document.querySelector("#miles-driven").innerText = (upscaled_CO2_in_kg / 0.000403 / 1000).toFixed(2);
    document.querySelector("#gasoline").innerText = (upscaled_CO2_in_kg / 0.008887 / 1000).toFixed(2);
        // document.querySelector("#smartphones-charged").innerText = (upscaled_CO2_in_kg / 0.00000822 / 1000).toFixed(2);
    document.querySelector("#flights").innerText = (upscaled_CO2_in_kg / 1000).toFixed(2);
}
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

const createMetricBoxes = (phase_stats_object) => {

    for (phase in phase_stats_object) {
        let energy = 0;
        let power = 0;
        let network_io = 0;

        for (metric_name in phase_stats_object[phase]) {
            createDetailMetricBoxes(phase_stats_object[phase][metric_name], phase);
            // accumulate for key metrics
            if(metric_name == 'cpu_energy_rapl_msr_system'
                || metric_name == 'memory_energy_rapl_msr_system'
                || metric_name == 'ane_energy_powermetrics_system'
                || metric_name == 'gpu_energy_powermetrics_system'
                || metric_name == 'cores_energy_powermetrics_system' ) {
                energy += phase_stats_object[phase][metric_name].value;
        } else if (metric_name == 'ane_power_powermetrics_system'
            || metric_name == 'gpu_power_powermetrics_system'
            || metric_name == 'cores_power_powermetrics_system' ) {
            power += phase_stats_object[phase][metric_name].value;
        } else if(metric_name == 'network_io_cgroup_container') {
            network_io += phase_stats_object[phase][metric_name].value;
        }
    }
    createKeyMetricBoxes(energy, power, network_io, phase);
}



$('.ui.steps.phases .step').tab();
$('.ui.accordion').accordion();

    // although there are multiple .step.runtime-step containers the first one
    // marks the first runtime step and is shown by default
document.querySelector('.step.runtime-step').dispatchEvent(new Event('click'));
}

const walkPhaseStats = (phase_stats_data) => {
    phase_stats_object = {}
    phase_stats_data.forEach(phase_stat => {
        let [metric_name, detail_name, phase, value, unit] = phase_stat; // unpack
        [value, unit] = convertValue(value, unit);
        let metric_clean_name = metric_name;

        let icon = 'circle'; // default
        let color = 'grey'; // default

        let metric_classifier_position = metric_name.lastIndexOf("_")
        let metric_type = metric_name.substr(metric_classifier_position+1)
        let metric_key = metric_name.substr(0,metric_classifier_position)

        if (METRIC_MAPPINGS[metric_key] !== undefined) {
            metric_clean_name = METRIC_MAPPINGS[metric_key]['clean_name'];
            color = METRIC_MAPPINGS[metric_key]['color'];
            icon = METRIC_MAPPINGS[metric_key]['icon'];
        }
        if (phase_stats_object[phase] == undefined) {
            phase_stats_object[phase] = {}
        }
        if (phase_stats_object[phase][metric_key] == undefined) {

            phase_stats_object[phase][metric_key] = {
                clean_name: metric_clean_name,
                name: metric_name,
                type: metric_type,
                value: value,
                unit: unit,
                detail_name: detail_name,
                max: null,
                color: color,
                icon: icon
            }
        }

        if(metric_type == 'MAX') {
            phase_stats_object[phase][metric_key]['max'] = value
        } else {
            phase_stats_object[phase][metric_key]['value'] = value
        }
    });
    return phase_stats_object;
}

const displayKeyMetricCharts = (phase_stats_object) => {

    const pie_chart_metrics = [
        'gpu_energy_powermetrics_system',
        'ane_energy_powermetrics_system',
        'cores_energy_powermetrics_system',
        'network_io_energy_powermetrics_system',
        'cpu_energy_rapl_msr_system',
        'memory_energy_rapl_msr_system',
        'network_io_cgroup_container'
        ]

    for (phase in phase_stats_object) {
        let data = []

        pie_chart_metrics.forEach(metric => {
            if (phase_stats_object[phase]?.[metric]?.value == undefined) return;
            data.push({
                value: phase_stats_object[phase][metric].value,
                name: `${phase_stats_object[phase][metric].clean_name} [${phase_stats_object[phase][metric].unit}]`
            })
        })

        var chartDom = document.querySelector(`.ui.tab[data-tab='${phase}'] .pie-chart`);
        var myChart = echarts.init(chartDom);
        var option = getPieChartOptions('Component energy distribution', data);
        myChart.setOption(option);

        var chartDom = document.querySelector(`.ui.tab[data-tab='${phase}'] .embodied-chart`);
        var myChart = echarts.init(chartDom);
        let series = [
              {
                  name: 'Embodied carbon',
                  type: 'bar',
                  emphasis: {
                      focus: 'series'
                  },
                  data: [220]
              },
              {
                  name: 'Usage Phase',
                  type: 'bar',
                  stack: 'total',
                  emphasis: {
                      focus: 'series'
                  },
                  data: [15]
              }
          ];
        var option = getBarChartOptions('Embodied carbon vs. Usage Phase', ['Phases'], series);
        myChart.setOption(option);

    }
    // after phase charts render total charts
    var chartDom = document.querySelector(`#total-phases-data .embodied-chart`);
    var myChart = echarts.init(chartDom);
    var series = [
              {
                  name: 'Embodied carbon',
                  type: 'bar',
                  emphasis: {
                      focus: 'series'
                  },
                  data: [4420]
              },
              {
                  name: 'Usage Phase',
                  type: 'bar',
                  stack: 'total',
                  emphasis: {
                      focus: 'series'
                  },
                  data: [225]
              }
          ];
    var option = getBarChartOptions('Embodied carbon vs. Usage Phase', ['Phases'], series);
    myChart.setOption(option);


    // after phase charts render total charts
    var chartDom = document.querySelector(`#total-phases-data .phases-chart`);
    var myChart = echarts.init(chartDom);
    var series = [
            {
              name: 'CPU',
              type: 'bar',
              stack: 'total',
              emphasis: {
                focus: 'series'
              },
              data: [10, 120, 30, 10, 200, 2]
            },
            {
              name: 'HDDs+Overhead',
              type: 'bar',
              stack: 'total',
              emphasis: {
                focus: 'series'
              },
              data: [15, 100, 50, 15, 50, 2]
            },
            {
              name: 'DRAM',
              type: 'bar',
              stack: 'total',
              emphasis: {
                focus: 'series'
              },
              data: [2, 20, 20, 2, 10, 2]
            },
            {
              name: 'PSU',
              type: 'bar',
              stack: 'total',
              emphasis: {
                focus: 'series'
              },
              data: [6, 6, 6, 6, 6, 6]
            },
            {
              name: 'Network',
              type: 'bar',
              stack: 'total',
              emphasis: {
                focus: 'series'
              },
              data: [0, 800, 100, 0, 400, 5]
            }
          ];
    var legend = ['Baseline', 'Installation', 'Boot', 'Idle', 'Runtime', 'Remove'];
    var option = getBarChartOptions('Total Phases consumption', legend, series);
    myChart.setOption(option);


}


async function makeAPICalls(url_params) {

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
        var notes_data = await makeAPICall('/v1/notes/' + url_params.get('id'))
    } catch (err) {
        showNotification('Could not get notes data from API', err);
    }
    try {
        var phase_stats_data = await makeAPICall('/v1/phase_stats/single/' + url_params.get('id'))
    } catch (err) {
        showNotification('Could not get phase_stats data from API', err);
    }

    return [project_data?.data, stats_data?.data, notes_data?.data, phase_stats_data?.data];
}

const renderBadges = (url_params) => {

    document.querySelectorAll("#badges span.energy-badge-container").forEach(el => {
        const link_node = document.createElement("a")
        const img_node = document.createElement("img")
        link_node.href = `${METRICS_URL}/stats.html?id=${url_params.get('id')}`
        img_node.src = `${API_URL}/v1/badge/single/${url_params.get('id')}?metric=${el.attributes['data-metric'].value}`
        link_node.appendChild(img_node)
        el.appendChild(link_node)
    })
    document.querySelectorAll(".copy-badge").forEach(el => {
        el.addEventListener('click', copyToClipboard)
    })
}

const getURLParams = () => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))

    if(url_params.get('id') == null || url_params.get('id') == '' || url_params.get('id') == 'null') {
        showNotification('No project id', 'ID parameter in URL is empty or not present. Did you follow a correct URL?');
        throw "Error";
    }
    return url_params;
}


/* Chart starting code*/
$(document).ready( (e) => {
    (async () => {

        let url_params = getURLParams();

        let [project_data, stats_data, notes_data, phase_stats_data] = await makeAPICalls(url_params);

        if (project_data == undefined) {
            return;
        }

        renderBadges(url_params);

        // create new custom field
        // timestamp is in microseconds, therefore divide by 10**6
        const measurement_duration_in_s = (project_data.end_measurement - project_data.start_measurement) / 1000000
        project_data['duration'] = `${measurement_duration_in_s} s`

        fillProjectData(project_data);

        let phase_stats_object = walkPhaseStats(phase_stats_data)

        createMetricBoxes(phase_stats_object);

        if (stats_data == undefined) {
            return;
        }

        displayKeyMetricCharts(phase_stats_object);

        const metrics = getMetrics(stats_data, project_data.start_measurement, project_data.end_measurement);

        if (notes_data == undefined) {
            return;
        }

        displayTimelineCharts(metrics, notes_data);

        // after all instances have been placed the flexboxes might have rearranged. We need to trigger resize
        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500); // needed for the graphs to resize

    })();
});

