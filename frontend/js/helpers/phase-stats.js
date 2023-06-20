const setupPhaseTabs = (phase_stats_object, multi_comparison, include_detail_phases = false) => {
    let keys = Object.keys(phase_stats_object['data'])
    // only need to traverse one branch in case of a comparison
    // no need to display phases that do not exist in both
    for (phase in phase_stats_object['data'][keys[0]]) {
        if (include_detail_phases == false && phase.indexOf('[') == -1) continue;
        createPhaseTab(phase);
        let tr = document.querySelector(`div.tab[data-tab='${phase}'] .compare-metrics-table thead`).insertRow();
        if (multi_comparison) {
            tr.innerHTML = `
                <th>Metric</th>
                <th>Source</th>
                <th>Scope</th>
                <th>Detail Name</th>
                <th><span class="overflow-ellipsis" style="width: 100px; display:block;" title="${keys[0]}">${replaceRepoIcon(keys[0])}</span></th>
                <th><span class="overflow-ellipsis" style="width: 100px; display:block;" title="${keys[1]}">${replaceRepoIcon(keys[1])}</span></th>
                <th>Unit</th>
                <th>Change</th>
                <th>Significant (T-Test)</th>`;
        } else {
            tr.innerHTML = `
                <th>Metric</th>
                <th>Source</th>
                <th>Scope</th>
                <th>Detail Name</th>
                <th>Value</th>
                <th>Unit</th>
                <th class="hide-for-single-stats">StdDev</th>
                <th>MAX</th>`;
        }
    }
}

const determineMultiComparison = (comparison_case) => {
    switch (comparison_case) {
        case null: // single value
        case 'Repeated Run':
            return false;
            break;
        case 'Branch':
        case 'Usage Scenario':
        case 'Commit':
        case 'Machine':
        case 'Repository':
            return true;
            break;
        default:
            throw `Unknown comparison case: ${comparison_case}`
    }
}


/*
    This function was originally written to include new phases in the "steps"

    However atm we use it to include steps only in the runtime phase as items

    Because of the CSS structure this function works identical in both places are "step" as well as "item" are
    children.

    Also [RUNTIME] is not actually a real separate step anymore atm. The
    actual step to be filled is [[RUNTIME]], which is a dummy.

    [RUNTIME] still works as a data-tab selector as the first item in there is the [[RUNTIME]] tab which will be
    "accidentally" selected by querySelector.

    Therefore this function relies on the current order of the steps and tabs and can only append new phases, but
    not prepend
*/
const createPhaseTab = (phase) => {

    let phase_tab_node = document.querySelector(`a.step[data-tab='${phase}']`);

    if(phase_tab_node == null || phase_tab_node == undefined) {
        let runtime_tab_node = document.querySelector('a.runtime-step');
        let cloned_tab_node = runtime_tab_node.cloneNode(true);
        cloned_tab_node.style.display = '';
        cloned_tab_node.setAttribute('data-tab', phase);
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
const displayComparisonMetrics = (phase_stats_object, comparison_case, multi_comparison, include_detail_phases = false) => {

    let keys = Object.keys(phase_stats_object['data'])

    // we need to traverse only one branch of the tree and copy in all other values if
    // a matching metric exists in the other branch
    // we first go through one branch until we reach the detail object
    // we identify if a metric is a key metric regarding something and handle that
    // we identify if a metric is a normal metric regarding something and handle that
    // if we have a comparison case between the two we just display the difference between them
    // if we have a repetition case we display the STDDEV
    // otherwise we just display the value

    let machine_energy_chart_data =  {};
    let machine_energy_chart_legend =  {};
    let machine_energy_chart_labels = [];
    for (phase in phase_stats_object['data'][keys[0]]) {
        if (include_detail_phases == false && phase.indexOf('[') == -1) continue;
        let phase_data = phase_stats_object['data'][keys[0]][phase];

        let radar_chart_labels = [];
        let radar_chart_data = [[],[]];

        let energy_chart_labels = [];
        let energy_chart_data =  [[],[]];
        machine_energy_chart_labels.push(phase);
        machine_energy_chart_legend[phase]  = [];

        for (metric in phase_data) {
            let metric_data = phase_data[metric]
            for (detail in metric_data['data']) {
                let detail_data = metric_data['data'][detail]

                // push data to chart that we need in any case
                radar_chart_labels.push(metric_data.clean_name);
                radar_chart_data[0].push(detail_data.mean)

                if (metric.indexOf('_energy_') !== -1) {
                    energy_chart_labels.push(metric_data.clean_name);
                    energy_chart_data[0].push(detail_data.mean)
                }
                if (metric.match(/^.*_energy_.*_machine$/) !== null) {
                    machine_energy_chart_legend[phase].push(metric_data.clean_name);
                    if(machine_energy_chart_data?.[`${metric_data.clean_name} - ${keys[0]}`] == null)
                        machine_energy_chart_data[`${metric_data.clean_name} - ${keys[0]}`] = []
                    machine_energy_chart_data[`${metric_data.clean_name} - ${keys[0]}`].push(detail_data.mean)

                }
                if (comparison_case == null && metric.match(/^.*_co2_.*_machine$/) !== null) {
                    calculateCO2(phase, detail_data.mean);
                }




                if (!multi_comparison) {
                    displaySimpleMetricBox(phase,metric, metric_data, detail_data, keys[0]);
                    if(comparison_case !== null) {
                        displayCompareChart(
                            phase,
                            `${metric_data.clean_name} (${detail}) - [${metric_data.unit}]`,
                            [`${comparison_case}: ${keys[0]}`],
                            [detail_data.values],
                            [{name:'Confidence Interval', bottom: detail_data.mean-detail_data.ci, top: detail_data.mean+detail_data.ci}],
                        );
                    }

                } else {
                    let metric_data2 = phase_stats_object?.['data']?.[keys[1]]?.[phase]?.[metric]
                    let detail_data2 = metric_data2?.['data']?.[detail]
                    if (detail_data2 == undefined) {
                        // the metric or phase might not be present in the other run
                        // note that this debug statement does not log when on the second branch more metrics are
                        // present that are not shown. However we also do not want to display them.
                        console.log(`${metric} ${detail} was missing from one comparison. Skipping`);
                        continue;
                    }
                    displayDiffMetricBox(
                        phase, metric, metric_data, [detail_data, detail_data2],
                        keys[0], phase_stats_object.statistics?.[phase]?.[metric]?.[detail]?.is_significant
                    );

                    detail_chart_data = [detail_data.values,detail_data2.values]
                    detail_chart_mark = [
                        {name:'Confidence Interval', bottom: detail_data.mean-detail_data.ci, top: detail_data.mean+detail_data.ci},
                        {name:'Confidence Interval', bottom: detail_data2.mean-detail_data2.ci, top: detail_data2.mean+detail_data2.ci},
                    ]
                    displayCompareChart(
                        phase,
                        `${metric_data.clean_name} (${detail}) - [${metric_data.unit}]`,
                        [`${comparison_case}: ${keys[0]}`, `${comparison_case}: ${keys[1]}`],
                        detail_chart_data,
                        detail_chart_mark,
                    );

                    radar_chart_data[1].push(detail_data2.mean)

                    if (metric.indexOf('_energy_') !== -1) {
                        energy_chart_data[1].push(detail_data2.mean)
                    }
                    if (metric.match(/^.*_energy.*_machine$/) !== null) {
                        if(machine_energy_chart_data?.[`${metric_data.clean_name} - ${keys[1]}`] == null)
                        machine_energy_chart_data[`${metric_data.clean_name} - ${keys[1]}`] = []

                        machine_energy_chart_data[`${metric_data.clean_name} - ${keys[1]}`].push(detail_data2.mean)
                    }
                }
            }
        }
        // phase ended. Render out the chart


        let radar_legend = []
        if (multi_comparison) {
            radar_legend = [`${comparison_case}: ${keys[0]}`, `${comparison_case}: ${keys[1]}`]
        } else {
            radar_legend = [keys[0]]
        }

        displayKeyMetricsRadarChart(
            radar_legend,
            radar_chart_labels,
            radar_chart_data,
            phase
        );

        displayKeyMetricsBarChart(
            radar_legend,
            energy_chart_labels,
            energy_chart_data,
            phase
        )

        // displayKeyMetricsEmbodiedCarbonChart(phase);

    }
    displayTotalChart(
        machine_energy_chart_legend,
        machine_energy_chart_labels,
        machine_energy_chart_data
    )

    /*
        Display all boxes and charts
    */
    $('.ui.steps.phases .step').tab({
        onLoad: function(value, text) {
            window.dispatchEvent(new Event('resize'));
        }
    }); // activate tabs for runtime sub-phases

    $('#runtime-sub-phases.menu .item').tab({
        onLoad: function(value, text) {
            window.dispatchEvent(new Event('resize'));
        }
    }); // activate tabs for runtime sub-phases


    $('.ui.accordion').accordion({ // if the accordion opens the detail charts are resized
        onOpen: function(value, text) {
            window.dispatchEvent(new Event('resize'));
        }
    });

    $('table').tablesort();

    // although there are multiple .step.runtime-step containers the first one
    // marks the first runtime step and is shown by default
    document.querySelector('a.step[data-tab="[RUNTIME]"').dispatchEvent(new Event('click'));

    window.dispatchEvent(new Event('resize'));
}

