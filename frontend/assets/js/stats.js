function createChartContainer(scaffold, container, chart) {
    const chart_node = document.querySelector(scaffold).cloneNode(true)
    chart_node.style.display = "block";
    document.querySelector(container).appendChild(chart_node);

    my_charts[el] = new ApexCharts(chart_node.querySelector(chart), options)
    my_charts[el].render()
}

function buildOptions(series, annotation, chart_title) {
    const options = {
        series: Object.values(series),
        chart: {
            type: 'area',
            animations: {
              enabled: false
            }
        },
        dataLabels: {
            enabled: false
        },
        stroke: {curve: 'smooth'},
        tooltip: {
            x: { format: 'dd/MM/yy HH:mm'},
        },
        xaxis: { tickAmount: 6, type: "datetime"},
        annotations: { xaxis: annotation },
        title: {text: chart_title}
    };
}