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

      xAxis: [],
      yAxis: {
        type: 'value'
      },
      series: []
    };
}

const fillAvgContainers = (project) => {
    document.querySelector("#project-last-run").innerText = project.last_run;
    document.querySelector("#project-name").innerText = project.name;
    document.querySelector("#project-uri").innerText = project.uri;
    document.querySelector("#project-cpu").innerText = project.cpu;
    document.querySelector("#project-memtotal").innerText = project.memtotal;
  // document.querySelector("#project-idle-time-start").innerText = project.idle_time_start;
  // document.querySelector("#project-idle-time-end").innerText = project.idle_time_end;
  document.querySelector("#project-flow-process-runtime").innerText = project.flow_process_runtime;

}

const getMetrics = (my_json, style='apex') => {
    const metrics = {cpu_load: [], mem_load: [], series: {}, total_energy: 0}

    let accumulate = 0;


    my_json.data.forEach(el => {
        /* Spec for data
        el[0] // container_id
        el[1] // time -> in nanoseconds
        el[2] // metric name
        el[3] // value -> This value might need to be rescaled
        '*/
        accumulate = 0; // default
        if (el[1] > my_json.project.start_measurement && el[1] < my_json.project.end_measurement) {
            accumulate = 1;
        }

        let time_in_ms = el[1] / 1000; // divide nanoseconds timestamp to ms to be handled by charting lib
        let value = el[3]; // default

        if (el[2] == 'cpu_cgroup_container') {
            if (accumulate === 1) metrics.cpu_load.push(el[3]);
            value = el[3] / 100; // CPU comes as ratio, but since stored as integer is was multiplicated with 100
        } else if (el[2] == 'energy_RAPL_MSR_system') {
            if (accumulate === 1) metrics.total_energy += el[3];
            value = el[3];
        } else if (el[2] == 'memory_cgroup_container') {
            metrics.mem_load.push(el[3]);
            value = el[3] / 1000000; // make memory in MB
        }

        // Depending on the charting library the object has to be reformatted
        // First we check if structure is initialized
        if (metrics.series[el[2]] == undefined)  metrics.series[el[2]] = {};
        if (metrics.series[el[2]][el[0]] == undefined) {
            metrics.series[el[2]][el[0]] = { name: el[0], time: [], data: [] }
        }

        // now we handle the library specific formatting
        if(style=='apex') {
            metrics.series[el[2]][el[0]]['data'].push({ x: time_in_ms, y: value })
        } else if(style=='echarts') {
            metrics.series[el[2]][el[0]]['time'].push(time_in_ms)
            metrics.series[el[2]][el[0]]['data'].push(value)
        } else throw "Unknown chart style"
    })
    return metrics;
}

const displayGraphs = (my_series, style='apex') => {

  let counter = 0; // for automatically creating pair of <div>s


    for ( metric_name in my_series) {

        const element = createChartContainer("#chart-container", metric_name, counter);

        if(style=='apex') {
            charts = [];
            let options = getApexOptions();
            options.title.text = metric_name;
            options.series = Object.values(my_series[metric_name]);
            (new ApexCharts(element, options)).render();
        } else if(style == 'echarts') {
            var options = getEChartsOptions();
            for (container in my_series[metric_name]) {
                options.xAxis.push({data: my_series[metric_name][container].time});
                options.series.push({data: my_series[metric_name][container].data, type: 'line', areaStyle: {color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          {
            offset: 0,
            color: 'rgb(55, 162, 255)'
          },
          {
            offset: 1,
            color: 'rgb(116, 21, 219)'
          }
        ])}});
            }
            echarts.init(element).setOption(options);
        } else {
            throw "Unknown chart style";
        }
        counter++;

    }
}


const createChartContainer = (container, el, counter) => {
    const chart_node = document.createElement("div")
    chart_node.classList.add("card");
    chart_node.innerHTML = `<div class="content">
    <div class="description">
    <div class="statistics-chart" id=${el}-chart></div>
    ${counter === 0 ? `<div>
        <label>
        <input type="checkbox" checked="" onchange="toggleNotes()"><span
        id="toggle-notes-spam">Show notes</span>
        </label>
        </div>` : ``}
        </div>
        </div>
        `

    if (counter % 2 === 0) {
        const twoCards = document.createElement("div");
        twoCards.classList.add("ui");
        twoCards.classList.add("two");
        twoCards.classList.add("cards");
        twoCards.classList.add("stackable");
        const id = "twoCards" + counter;
        twoCards.id = id;
        document.querySelector(container).appendChild(twoCards);
        twoCards.appendChild(chart_node);
    // console.log(`counter ${counter} -> created twoCards div`)
    } else {
        const id = "#twoCards" + (counter - 1);
        // console.log(`counter ${counter} -> belongs to already created div with id ${id}`)
        document.querySelector(id).appendChild(chart_node);
    }
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

const displayStatistics = (metrics) => {
    document.querySelector("#max-cpu-load").innerText = (Math.max.apply(null, metrics.cpu_load) / 100) + " %"
    document.querySelector("#total-energy").innerText = (metrics.total_energy / 1000).toFixed(2) + " J"
    document.querySelector("#total-co2").innerText = (metrics.total_energy / 1000 / 3600000 * 0.519 * 1000000).toFixed(2) + " ug"
    document.querySelector("#avg-cpu-load").innerText = ((metrics.cpu_load.reduce((a, b) => a + b, 0) / metrics.cpu_load.length) / 100).toFixed(2) + " %"

    const total_CO2_in_tons = (metrics.total_energy / 1000 / 3600000 * 0.519 * 1000000);
    const total_CO2_in_kg = total_CO2_in_tons / 1000000000;

    document.querySelector("#trees").innerText = (total_CO2_in_kg / 0.06 / 1000).toFixed(2);
    document.querySelector("#miles-driven").innerText = (total_CO2_in_kg / 0.000403 / 1000).toFixed(2);
    document.querySelector("#gasoline").innerText = (total_CO2_in_kg / 0.008887 / 1000).toFixed(2);
    document.querySelector("#smartphones-charged").innerText = (total_CO2_in_kg / 0.00000822 / 1000).toFixed(2);
    document.querySelector("#flights").innerText = (total_CO2_in_kg / 1000).toFixed(2);
}


/* Chart starting code*/
$(document).ready((e) => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))

    // makeAPICall('/v1/notes/' + url_params.get('id'), (my_json) => getAnnotations(my_json))

    makeAPICall('/v1/stats/single/' + url_params.get('id'), (my_json) => {
        const metrics = getMetrics(my_json, 'apex');
        fillAvgContainers(my_json.project)
        displayGraphs(metrics.series, 'apex');
        displayStatistics(metrics);
    })
});
