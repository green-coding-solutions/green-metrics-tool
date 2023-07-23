const getURLParams = () => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))
    return url_params;
}

$(document).ready( (e) => {
    (async () => {

        let url_params = getURLParams();

        if(url_params.get('uri') == null
            || url_params.get('uri') == ''
            || url_params.get('uri') == 'null') {
            showNotification('No uri', 'uri parameter in URL is empty or not present. Did you follow a correct URL?');
            throw "Error";
        }

        let api_url = `/v1/timeline?uri=${url_params.get('uri')}`;

        if(url_params.get('branch') !== null && url_params.get('branch') !== 'null') {
            api_url = `${api_url}&branch=${url_params.get('branch')}`
        }

        if(url_params.get('filename') !== null && url_params.get('filename') !== 'null') {
            api_url = `${api_url}&filename=${url_params.get('filename')}`
        }

        try {
            var phase_stats_data = (await makeAPICall(api_url)).data
        } catch (err) {
            showNotification('Could not get compare in-repo data from API', err);
        }

        if (phase_stats_data == undefined) return;

        let legends = {};
        let series = {};

        phase_stats_data.forEach( (data) => {
            let [metric_name, detail_name, phase, value, commit_hash, commit_timestamp] = data


            if (series[`${metric_name} - ${detail_name}`] == undefined) {
                series[`${metric_name} - ${detail_name}`] = {labels: [], values: [], notes: []}
            }

            series[`${metric_name} - ${detail_name}`].labels.push(commit_timestamp)
            series[`${metric_name} - ${detail_name}`].values.push(value)
            series[`${metric_name} - ${detail_name}`].notes.push({
                commit_timestamp: commit_timestamp,
                commit_hash: commit_hash,
                phase: phase

            })






        })

        const chart_instances = [];

        for(my_series in series) {
            const element = createChartContainer("#chart-container", `${my_series} [UNIT]`);

            const chart_instance = echarts.init(element);

            let data_series = [{
                name: my_series,
                type: 'bar',
                smooth: true,
                symbol: 'none',
                areaStyle: {},
                data: series[my_series].values,
                markLine: {
                    precision: 4, // generally annoying that precision is by default 2. Wrong AVG if values are smaller than 0.001 and no autoscaling!
                    data: [ {type: "average",label: {formatter: "AVG:\n{c}"}}]
                }
            }]


            let options = getLineBarChartOptions(series[my_series].labels, data_series, null, 'category');
            options.tooltip = {
                trigger: 'item',
                formatter: function (params, ticket, callback) {
                    console.log(params);
                    return `<strong>${series[params.seriesName].notes[params.dataIndex]}</strong><br>
                            timestamp: ${series[params.seriesName].notes[params.dataIndex].commit_timestamp}<br>
                            commit_hash: ${series[params.seriesName].notes[params.dataIndex].commit_hash}<br>
                            `;
                }
            };

            chart_instance.setOption(options);
            chart_instances.push(chart_instance);

        }



        window.onresize = function() { // set callback when ever the user changes the viewport
            chart_instances.forEach(chart_instance => {
                chart_instance.resize();
            })
        }

        document.querySelector('#api-loader').remove();

    })();
});

