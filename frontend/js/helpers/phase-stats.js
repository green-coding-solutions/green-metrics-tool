
const createPhaseTab = (phase) => {
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
}

/*
    We traverse the multi-dimensional metrics object only once and fill data
    in the appropriate variables for metric-boxes and charts
*/
const displayComparisonMetrics = (phase_stats_object, comparison_type) => {

    let chart_instances = []
    for (phase in phase_stats_object) {
        let phase_chart_labels = new Set();
        let phase_chart_data =
            [
                {
                  value: [],
                  name: null
                },
                {
                  value: [],
                  name: null
                }
          ];


        createPhaseTab(phase);
        for (metric_key in phase_stats_object[phase]) {
            for (detail_key in phase_stats_object[phase][metric_key].data) {
                let detail_chart_data = [];

                if (detail_key == '[SYSTEM]') {
                    var label_name = `${phase_stats_object[phase][metric_key].clean_name} [${phase_stats_object[phase][metric_key].unit}]`
                } else {
                    var label_name = `${phase_stats_object[phase][metric_key].clean_name} - ${detail_key} [${phase_stats_object[phase][metric_key].unit}]`
                }

                let idx = 0;
                for (compare_key in phase_stats_object[phase][metric_key].data[detail_key].data) {
                    displayDetailMetricBox(
                        phase_stats_object[phase][metric_key],
                        phase_stats_object[phase][metric_key].data[detail_key].data[compare_key],
                        compare_key,
                        phase,
                        comparison_type
                    );
                    // since we use a set, values will be unique
                    phase_chart_data[idx].value.push(phase_stats_object[phase][metric_key].data[detail_key].data[compare_key].mean);
                    phase_chart_data[idx].name = compare_key;
                    let mean = phase_stats_object[phase][metric_key].data[detail_key].data[compare_key].mean;
                    let ci = phase_stats_object[phase][metric_key].data[detail_key].data[compare_key].ci;
                    detail_chart_data.push(
                        {
                            type: 'bar',
                            smooth: true,
                            symbol: 'none',
                            areaStyle: {},
                            data: phase_stats_object[phase][metric_key].data[detail_key].data[compare_key].values,
                            markArea: { data: [
                                [
                                    { name: 'Confidence Interval', yAxis: mean-ci }, // a name in one item is apprently enough ...
                                    { yAxis: mean+ci }
                                ]
                            ]},
                        }
                    )
                    idx++;
                }
                let graphic = null;
                console.log(phase_stats_object[phase][metric_key].data[detail_key]);
                if(phase_stats_object[phase][metric_key].data[detail_key].significant != null) {
                    if(phase_stats_object[phase][metric_key].data[detail_key].significant) {
                        graphic = getChartGraphic('T-Test: Significant')
                    } else {
                        graphic = getChartGraphic('T-Test: Not Significant')
                    }
                }
                phase_chart_labels.add({'name': label_name});
                var chart = displayCompareChart(
                    label_name,
                    phase_chart_labels,
                    detail_chart_data,
                    graphic,
                    phase
                );
                chart_instances.push(chart);

            }
        }
        // phase ended. Render out the chart

        var chart = displayKeyMetricsRadarChart(phase_chart_labels, phase_chart_data, phase);
        chart_instances.push(chart);
        var chart = displayKeyMetricsEmbodiedCarbonChart(phase);
        chart_instances.push(chart);

    }



    // displayTotalCharts(phase_stats_object);


    /* TODO

        createKeyMetricBox(
            phase_stats_object[phase].totals.energy,
            phase_stats_object[phase].totals.power,
            phase_stats_object[phase].totals.network_io,
            phase
        );
        */

    window.onresize = function() { // set callback when ever the user changes the viewport
        chart_instances.forEach(chart_instance => {
            chart_instance.resize();
        })
    }



    /*
        Display all boxes and charts
    */
    $('.ui.steps.phases .step').tab();
    $('.ui.accordion').accordion();

    // although there are multiple .step.runtime-step containers the first one
    // marks the first runtime step and is shown by default
    document.querySelector('.step.runtime-step').dispatchEvent(new Event('click'));

    window.dispatchEvent(new Event('resize'));
}

