
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

    const metric_set = new Set();
    const phases = []
    let component_energies = {}
    let machine_energies = {}

    for (phase in phase_stats_object) {
        let radar_chart_labels = new Set();
        let radar_chart_legend = new Set();
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
        phases.push(phase);
        createPhaseTab(phase);
        for (metric_key in phase_stats_object[phase]) {
            if (phase_stats_object[phase][metric_key].is_component_energy == true) {
                if (component_energies[metric_key] == undefined)  component_energies[metric_key] = [];
                component_energies[metric_key].push(phase_stats_object[phase][metric_key].mean)
            }
            else if (phase_stats_object[phase][metric_key].is_machine_energy == true) {
                if (machine_energies[metric_key] == undefined)  machine_energies[metric_key] = [];
                machine_energies[metric_key].push(phase_stats_object[phase][metric_key].mean)
            }

            for (detail_key in phase_stats_object[phase][metric_key].data) {
                let detail_chart_data = [];
                let detail_chart_mark = [];

                if (detail_key == '[SYSTEM]') {
                    var label_name = `${phase_stats_object[phase][metric_key].clean_name} [${phase_stats_object[phase][metric_key].unit}]`
                } else {
                    var label_name = `${phase_stats_object[phase][metric_key].clean_name} - ${detail_key} [${phase_stats_object[phase][metric_key].unit}]`
                }

                let idx = 0;
                for (compare_key in phase_stats_object[phase][metric_key].data[detail_key].data) {
                    radar_chart_legend.add(compare_key)
                    displayDetailMetricBox(
                        phase_stats_object[phase][metric_key],
                        phase_stats_object[phase][metric_key].data[detail_key].data[compare_key],
                        compare_key,
                        phase,
                        comparison_type
                    );
                    // since we use a set, values will be unique
                    let mean = phase_stats_object[phase][metric_key].data[detail_key].data[compare_key].mean;
                    let ci = phase_stats_object[phase][metric_key].data[detail_key].data[compare_key].ci;

                    phase_chart_data[idx].value.push(mean);
                    phase_chart_data[idx].name = compare_key;
                    detail_chart_data.push(phase_stats_object[phase][metric_key].data[detail_key].data[compare_key].values)
                    detail_chart_mark.push({name:'Confidence Interval', bottom: mean-ci, top: mean+ci})
                    idx++;
                }
                let graphic = null;
                if(phase_stats_object[phase][metric_key].data[detail_key].significant != null) {
                    if(phase_stats_object[phase][metric_key].data[detail_key].significant) {
                        graphic = getChartGraphic('T-Test: Significant')
                    } else {
                        graphic = getChartGraphic('T-Test: Not Significant')
                    }
                }
                radar_chart_labels.add({'name': label_name});

                var chart = displayCompareChart(
                    label_name,
                    Array.from(radar_chart_legend),
                    detail_chart_data,
                    detail_chart_mark,
                    graphic,
                    phase
                );
            }
        }
        // phase ended. Render out the chart

        displayKeyMetricsRadarChart(
            Array.from(radar_chart_legend),
            Array.from(radar_chart_labels),
            phase_chart_data,
            phase
        );

        displayKeyMetricsEmbodiedCarbonChart(phase);

    }

    displayTotalCharts(machine_energies, component_energies, phases);


    /* TODO

        createKeyMetricBox(
            phase_stats_object[phase].totals.energy,
            phase_stats_object[phase].totals.power,
            phase_stats_object[phase].totals.network_io,
            phase
        );
        */

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

