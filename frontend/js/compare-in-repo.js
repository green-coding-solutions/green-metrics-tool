const createCompareChart = (metrics, phase) => {

    let legend = [];
    let series = [];
    let title = '';

    const element = createChartContainer(`.ui.tab[data-tab='${phase}'] .chart-container`, metric_name);

    for (detail_name in metrics) {
        legend.push(detail_name);
        let data = []
        metrics[detail_name].forEach( (metric) => {
            data.push(metric.value)
        });
        series.push({
            type: 'bar',
            smooth: true,
            symbol: 'none',
            areaStyle: {},
            data: data,
            markLine: { data: [
                {type: 'average',label: {formatter: 'Mean:\n{c}'}}
            ]},
            markArea: { data: [
                [
                    { name: 'Confidence Interval (T-Test)', yAxis: 8 }, // a name in one item is apprently enough ...
                    { yAxis: 11 }
                ]
            ]}
        });
        title = `${metrics[detail_name][0].clean_name} [${metrics[detail_name][0].unit}]`;
    };

    const chart_instance = echarts.init(element);
    let options = getLineChartOptions(title, legend, series, 'category');
    chart_instance.setOption(options);
    document.querySelector(`.ui.tab[data-tab='${phase}'] .api-loader`)?.remove();

    return chart_instance;

}





const createCompareCharts = (phase_stats_object) => {
    /*  Object structure
        {
            [BASELINE]: {
                metrics: {
                    ane_energy_powermetrics_system: {
                        [SYSTEM]: [...],
                        container_1: [...]
                        container_2 [...]
                    },
                    ane_power_powermetrics_system: {...},
                    ...
                }
                totals: {...}
            }
        }
    */


    const chart_instances = [];

    const t0 = performance.now();

    for (phase in phase_stats_object) {
        for (metric_name in phase_stats_object[phase].metrics) {
            chart_instances.push(
                createCompareChart(phase_stats_object[phase].metrics[metric_name], phase)
            );
        }
    }
    const t1 = performance.now();
    console.log(`createCompareCharts took ${t1 - t0} milliseconds.`);

    window.onresize = function() { // set callback when ever the user changes the viewport
        chart_instances.forEach(chart_instance => {
            console.log("RESIZE");
            chart_instance.resize();
        })
    }
    window.dispatchEvent(new Event('resize'));

}



const getURLParams = () => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))
    return url_params;
}


/* Chart starting code*/
$(document).ready( (e) => {
    (async () => {

        let url_params = getURLParams();
        if(url_params.get('ids') == null
            || url_params.get('ids') == ''
            || url_params.get('ids') == 'null') {
            showNotification('No ids', 'ids parameter in URL is empty or not present. Did you follow a correct URL?');
            throw "Error";
        }

        try {
            params = url_params.getAll('ids');
            let api_url = '/v1/compare?ids=';
            params.forEach( id => {
                api_url = `${api_url}${id}`
            });
            var phase_stats_data = await makeAPICall(api_url)
            phase_stats_data = phase_stats_data.data;
        } catch (err) {
            showNotification('Could not get compare in-repo data from API', err);
        }

        if (phase_stats_data == undefined) return;

        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>URI</strong></td><td><a href="${url_params.get('uri')}" target="_blank">${url_params.get('uri')}</a></td></tr>`)
        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Machine-ID</strong></td><td>${url_params.get('machine_id')}</td></tr>`)

        console.log(phase_stats_data);
        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Type</strong></td><td>${phase_stats_data.comparison_type}</a></td></tr>`)
        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Details</strong></td><td id="comparing-details">${phase_stats_data.comparison_details.join(' vs. ')}</td></tr>`)

        displayMetricBoxes(phase_stats_data.data, phase_stats_data.comparison_type);

        createCompareCharts(phase_stats_data.data);



    })();
});

