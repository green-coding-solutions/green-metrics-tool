const getCompareChartOptions = (legend, series, mark_area=null, x_axis='time', chart_type='line', graphic=null) => {
    let tooltip_trigger = (chart_type=='line') ? 'axis' : 'item';
    if (series.length > 1) {
       let max = Math.max(...series[0],...series[1])*1.2
       let options =  {
            tooltip: {trigger: tooltip_trigger},
            xAxis: [
                {
                    gridIndex: 0,
                    type: x_axis,
                    splitLine: {show: false},
                    name: [legend[0]],
                    axisLabel: {
                        show: true,
                        interval: 0,
                        rotate: 45,
                   },
                },
                {
                    gridIndex: 1,
                    splitLine: {show: false},
                    type: x_axis,
                    name: [legend[1]],
                    axisLabel: {
                        show: true,
                        interval: 0,
                        rotate: 45,
                   },
                }
              ],
            yAxis: [
                {
                  gridIndex: 0,
                  splitLine: {show: true},
                  max: max
                },
                {
                  gridIndex: 1,
                  splitLine: {show: true},
                  max: max
                },
            ],
            areaStyle: {},
            grid: [
                {
                  right: '60%',
                  type: 'value',
                  containLabel: false,
                },
                {
                  left: '60%',
                  type: 'value',
                  containLabel: false,
                }
            ],
            series: [
                {
                    type: chart_type,
                    data: series[0],
                    xAxisIndex: 0,
                    yAxisIndex:0,
                    markLine: {
                        precision: 4, // generally annoying that precision is by default 2. Wrong AVG if values are smaller than 0.001 and no autoscaling!
                        data: [ {type: "average",label: {formatter: "Mean:\n{c}"}}]
                    }

                },
                {
                    type: chart_type,
                    data: series[1],
                    xAxisIndex: 1,
                    yAxisIndex:1,
                    markLine: {
                        precision: 4, // generally annoying that precision is by default 2. Wrong AVG if values are smaller than 0.001 and no autoscaling!
                        data: [ {type: "average",label: {formatter: "Mean:\n{c}"}}]
                    }
                }
            ],
            animation: false,
            graphic: graphic,
            legend: [
              {
                  data: legend[0],
                  bottom: 0,
              },
              {
                  data: legend[0],
                  bottom: 0,
              }
            ],
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
        if (mark_area != null) {
            options['series'][0]['markArea'] = {
                data: [
                    [
                        { name: mark_area[0].name, yAxis: mark_area[0].top }, // a name in one item is apprently enough ...
                        { yAxis: mark_area[0].bottom }
                    ]
                ]
            };
            options['series'][1]['markArea'] = {
                data: [
                    [
                        { name: mark_area[1].name, yAxis: mark_area[1].top }, // a name in one item is apprently enough ...
                        { yAxis: mark_area[1].bottom }
                    ]
                ]
            };
        }
        return options;
    } else {
       let max = Math.max(...series[0])*1.2
       let options =  {
            tooltip: {trigger: tooltip_trigger},
            grid: {
                left: '0%',
                right: '0%',
                bottom: '0%',
                containLabel: true
            },
            xAxis: {
                type: x_axis,
                splitLine: {show: false},
                axisLabel: {
                        show: true,
                        interval: 0,
                        rotate: 45,
                   },
            },
            yAxis: {
                type: 'value',
                splitLine: {show: true}
            },
            series: [{
                data:series[0],
                type: chart_type,
                markLine: { data: [ {type: "average",label: {formatter: "Mean:\n{c}"}}]}
            }],
            animation: false,
            graphic: graphic,
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
        if (mark_area != null) {
            options['series'][0]['markArea'] = {
                data: [
                    [
                        { name: mark_area[0].name, yAxis: mark_area[0].top }, // a name in one item is apprently enough ...
                        { yAxis: mark_area[0].bottom }
                    ]
                ]
            }
        }
        return options;
    }
}

const getLineBarChartOptions = (legend, series, mark_area=null, x_axis='time', no_toolbox = false, graphic=null) => {

    if(Object.keys(series).length == 0) {
        return {graphic: getChartGraphic("No energy reporter active")};
    }

   let tooltip_trigger = (series[0].type=='line') ? 'axis' : 'item';

   let options =  {
        tooltip: { trigger: tooltip_trigger },
        grid: {
                left: '0%',
                right: 70,
                bottom: '0%',
                containLabel: true
        },
        xAxis: {
            type: x_axis,
            splitLine: {show: false},
            data: legend,
            axisLabel: {
                show: true,
                interval: 0,
                rotate: -15,
            },
        },
        yAxis: {
            type: 'value',
            splitLine: {show: true}
        },
        series: series,
        animation: false,
        graphic: graphic,
        legend: {
            data: legend,
            bottom: 0,
            // type: 'scroll' // maybe active this if legends gets too long
        }
    };
    if (mark_area != null) {
        options['series']['markArea'] = {
            data: [
                [
                    { name: mark_area[0].name, yAxis: mark_area[0].top }, // a name in one item is apprently enough ...
                    { yAxis: mark_area[0].bottom }
                ]
            ]
        }
    }
    if (no_toolbox == false) {
        options['toolbox'] = {
            itemSize: 25,
            top: 55,
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {}
            }
        }
    }
    return options;
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

const getChartGraphic = (text, top = 'center', left= 'center') => {
    return graphic = {
        type: 'group',
        top: top,
        left: left,
        draggable: true,
        children: [
          {
            type: 'rect',
            top: 'center',
            left: 'center',
            z: 100,
            shape: {
              height: 20,
              width: 250,

            },
            style: {
                fill: 'white',
                stroke: '#999',
                lineWidth: 2,
                shadowBlur: 8,
                shadowOffsetX: 3,
                shadowOffsetY: 3,
                shadowColor: 'rgba(0,0,0,0.3)',

              },
          },
          {
            type: 'text',
            top: 'center',
            left: 'center',
            z: 101,
            style: {
                  text: text,
                  fontSize: 14,
                  fontWeight: 'bold',
                  lineDash: [0, 200],
                  lineDashOffset: 0,
                  fill: 'black',
                  stroke: '#000',
                  lineWidth: 1
            }
          }
        ]
      }
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
            <div class="ui left floated chart-title">
                ${el}
            </div>
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
                <div class="statistics-chart"></div>
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

const displayKeyMetricsRadarChart = (legend, labels, data, phase) => {

    let chartDom = document.querySelector(`.ui.tab[data-tab='${phase}'] .radar-chart .statistics-chart`);
    document.querySelector(`.ui.tab[data-tab='${phase}'] .radar-chart .chart-title`).innerText = RADAR_CHART_TITLE;
    let myChart = echarts.init(chartDom);
    labels = labels.map((el) => { return {name: el}})
    let series = data.map((el, idx) => { return {name: legend[idx], value: el}})

    let options = {
      grid: {
        left: '0%',
        right: '0%',
        bottom: '0%',
        containLabel: true
      },
      legend: {
        data: legend,
        bottom: 0
      },
      radar: {
        shape: 'circle',
        indicator: labels
      },
      series: [
        {
          name: 'TODO',
          type: 'radar',
          areaStyle: {},
          data: series
        }
      ]
    };

    options && myChart.setOption(options);

    // set callback when ever the user changes the viewport
    // we need to use jQuery here and not Vanilla JS to not overwrite but add multiple resize callbacks
    $(window).on('resize', () =>  {
        myChart.resize();
    });
}

const displayKeyMetricsBarChart = (legend, labels, data, phase) => {

    let series = data.map((el, idx) => { return {type: "bar", name: legend[idx], data: el}})
    let chartDom = document.querySelector(`.ui.tab[data-tab='${phase}'] .bar-chart .statistics-chart`);
    document.querySelector(`.ui.tab[data-tab='${phase}'] .bar-chart .chart-title`).innerText = TOP_BAR_CHART_TITLE;

    let myChart = echarts.init(chartDom);
    let options = getLineBarChartOptions(labels, series, null, 'category', true);
    myChart.setOption(options);

    // set callback when ever the user changes the viewport
    // we need to use jQuery here and not Vanilla JS to not overwrite but add multiple resize callbacks
    $(window).on('resize', () =>  {
        myChart.resize();
    });
}


/*
    Currently broken and unused, cause pie chart is misleading in suggesting a hidden "total"
*/
const displayKeyMetricsPieChart = () => {
    let chartDom = document.querySelector(`.ui.tab[data-tab='${phase}'] .pie-chart`);
    let myChart = echarts.init(chartDom);
    let options = getPieChartOptions('Energy distribution of measured metrics', data);
    myChart.setOption(options);

    // set callback when ever the user changes the viewport
    // we need to use jQuery here and not Vanilla JS to not overwrite but add multiple resize callbacks
    $(window).on('resize', () =>  {
        myChart.resize();
    });
}


// TODO
const displayKeyMetricsEmbodiedCarbonChart = (phase) => {
    let chartDom = document.querySelector(`.ui.tab[data-tab='${phase}'] .embodied-chart .statistics-chart`);
    document.querySelector(`.ui.tab[data-tab='${phase}'] .embodied-chart .chart-title`).innerText = 'Embodied carbon vs. Usage Phase';

    let myChart = echarts.init(chartDom);
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
    let options = getLineBarChartOptions(['Phases'], series);
    myChart.setOption(options);

    // set callback when ever the user changes the viewport
    // we need to use jQuery here and not Vanilla JS to not overwrite but add multiple resize callbacks
    $(window).on('resize', () =>  {
        myChart.resize();
    });

}

const displayTotalChart = (legend, labels, data) => {

    let chartDom = document.querySelector(`#total-phases-data .bar-chart .statistics-chart`);
    document.querySelector(`#total-phases-data .bar-chart .chart-title`).innerText = TOTAL_CHART_BOTTOM_TITLE;

    let myChart = echarts.init(chartDom);

    let series = [];
    for (key in data) {
        series.push({
              name: key,
              type: 'bar',
              emphasis: {
                focus: 'series'
              },
              data: data[key]
        })
    }


    let options = getLineBarChartOptions(labels, series, null, 'category')
    myChart.setOption(options);
        // set callback when ever the user changes the viewport
    // we need to use jQuery here and not Vanilla JS to not overwrite but add multiple resize callbacks
    $(window).on('resize', () =>  {
        myChart.resize();
    });


}


const displayCompareChart = (phase, title, legend, data, mark_area, graphic) => {

    const element = createChartContainer(`.ui.tab[data-tab='${phase}'] .compare-chart-container`, title);
    const myChart = echarts.init(element);
    let options = getCompareChartOptions(legend, data, mark_area, 'category', 'bar');
    myChart.setOption(options);
    // set callback when ever the user changes the viewport
    // we need to use jQuery here and not Vanilla JS to not overwrite but add multiple resize callbacks
    $(window).on('resize', () =>  {
        myChart.resize();
    });

}

