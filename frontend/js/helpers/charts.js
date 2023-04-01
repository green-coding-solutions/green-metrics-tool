const getLineChartOptions = (title, legend, series, type='time') => {
    return {
        tooltip: {
            trigger: 'axis'
        },
        title: {
            text:title
        },
        xAxis: {
            type: type,
            splitLine: {show: true}
        },
        yAxis: {
            type: 'value',
            splitLine: {show: true}
        },
        series: series,
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

const getPieChartOptions = (title, data) => {
    return {
        tooltip: {
            trigger: 'item'
        },
        toolbox: {
            show: false,
        },
        title: {
          left: 'center',
          text: title
        },
        series: [
            {
                name: title,
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

const getBarChartOptions = (title, legend, series, dataset = null) => {
    return {
      tooltip: {
          trigger: 'item',
          formatter: function (params) {
              return `${params.seriesName}: ${params.data[params.componentIndex+1]}`;
            }
      },
      title: {
          left: 'center',
          text: title
      },
      legend: {
          top: "bottom",
      },
      dataset: dataset,
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

const createChartContainer = (container, el) => {
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


const displayKeyMetricCharts = (phase_stats_object) => {

    for (phase in phase_stats_object) {
        let data = []

        for (metric_name in phase_stats_object[phase].metrics) {
            for (detail_name in phase_stats_object[phase].metrics[metric_name]) {
                phase_stats_object[phase].metrics[metric_name][detail_name].forEach((metric) => {
                    if (metric.include_chart == true) {
                        data.push({
                            value: metric.value,
                            name: `${metric.clean_name} [${metric.unit}]`
                        })
                    }
                })
            }
        }

        var chartDom = document.querySelector(`.ui.tab[data-tab='${phase}'] .pie-chart`);
        var myChart = echarts.init(chartDom);
        var option = getPieChartOptions('Energy distribution of measured metrics', data);
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
                  data: ['N/A']
              },
              {
                  name: 'Usage Phase',
                  type: 'bar',
                  stack: 'total',
                  emphasis: {
                      focus: 'series'
                  },
                  data: ['N/A']
              }
          ];
        var option = getBarChartOptions('Embodied carbon vs. Usage Phase', ['Phases'], series);
        myChart.setOption(option);

    }
}

const displayTotalCharts = (phase_stats_object) => {

    let total_embodied_carbon = 0;
    let total_usage_phase = 0
    let dataset_total_phase_consumption = {source: []}
    let series_total_phase_consumption = []

    const metric_set = new Set();

    for (phase in phase_stats_object) {
        // total_usage_phase += phase_stats_object[phase].totals.energy;
        let phase_consumption_entry = [phase];
        for (metric_name in phase_stats_object[phase].metrics) {
            for (detail_name in phase_stats_object[phase].metrics[metric_name]) {
                phase_stats_object[phase].metrics[metric_name][detail_name].forEach((metric) => {
                    if (metric.include_chart == true) {
                        metric_set.add(metric.clean_name)
                        phase_consumption_entry.push(metric.value)
                    }
                });
            }
        }
        dataset_total_phase_consumption.source.push(phase_consumption_entry)
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
                  data: ['N/A']
              },
              {
                  name: 'Usage Phase',
                  type: 'bar',
                  stack: 'total',
                  emphasis: {
                      focus: 'series'
                  },
                  data: [total_usage_phase]
              }
          ];

    var option = getBarChartOptions('Embodied carbon Total vs. Usage Phase', ['Phases'], series);
    myChart.setOption(option);


    // after phase charts render total charts
    var chartDom = document.querySelector(`#total-phases-data .phases-chart`);
    var myChart = echarts.init(chartDom);
    var series = []
    metric_set.forEach((name) => {
        series.push(
            { type: 'bar', seriesLayoutBy: 'column',  name:name, emphasis: {focus: "series"}}
          )
    });

    var option = getBarChartOptions('Total Phases consumption', null, series, dataset_total_phase_consumption);
    myChart.setOption(option);

}