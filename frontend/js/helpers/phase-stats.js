const setupPhaseTabs = (phase_stats_object, multi_comparison) => {
    let keys = Object.keys(phase_stats_object['data'])
    // only need to traverse one branch in case of a comparison
    // no need to display phases that do not exist in both
    for (phase in phase_stats_object['data'][keys[0]]) {
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
                <th>MAX</th>
                <th>MIN</th>`;
        }
    }
}

const showWarning = (phase, warning) => {
    if (phase == '[RUNTIME]' ) phase == '[[RUNTIME]]';
    document.querySelector(`div.tab[data-tab='${phase}'] .ui.warning.message`).classList.remove('hidden');
    const newListItem = document.createElement("li");
    newListItem.textContent = warning;
    document.querySelector(`div.tab[data-tab='${phase}'] .ui.warning.message ul`).appendChild(newListItem);


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
        cloned_tab_node.innerText = phase;
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
const displayComparisonMetrics = (phase_stats_object, comparison_case, multi_comparison) => {

    let keys = Object.keys(phase_stats_object['data'])

    // we need to traverse only one branch of the tree and copy in all other values if
    // a matching metric exists in the other branch
    // we first go through one branch until we reach the detail object
    // we identify if a metric is a key metric regarding something and handle that
    // we identify if a metric is a normal metric regarding something and handle that
    // if we have a comparison case between the two we just display the difference between them
    // if we have a repetition case we display the STDDEV
    // otherwise we just display the value

    let total_chart_bottom_data =  {};
    let total_chart_bottom_legend =  {};
    let total_chart_bottom_labels = [];
    for (phase in phase_stats_object['data'][keys[0]]) {
        let phase_data = phase_stats_object['data'][keys[0]][phase];

        let radar_chart_labels = [];
        let radar_chart_data = [[],[]];

        let top_bar_chart_labels = [];
        let top_bar_chart_data =  [[],[]];
        total_chart_bottom_labels.push(phase);
        total_chart_bottom_legend[phase]  = [];

        let co2_calculated = false;
        let found_bottom_chart_metric = false;

        let phase_key0_has_machine_energy = false;
        let phase_key1_has_machine_energy = false;

        for (metric in phase_data) {
            let metric_data = phase_data[metric]
            for (detail in metric_data['data']) {
                let detail_data = metric_data['data'][detail]

                // push data to chart that we need in any case
                if(radar_chart_condition(metric) && multi_comparison) {
                    radar_chart_labels.push(metric_data.clean_name);
                    radar_chart_data[0].push(detail_data.mean)
                }

                if (top_bar_chart_condition(metric)) {
                    top_bar_chart_labels.push(`${metric_data.clean_name} (${metric_data.source})`);
                    top_bar_chart_data[0].push(detail_data.mean)
                }
                if (total_chart_bottom_condition(metric)) {
                    if(found_bottom_chart_metric) {
                        showWarning(phase, `Another metric for the bottom chart was already set (${found_bottom_chart_metric}), skipping ${metric} and only first one will be shown.`);
                    } else {
                        total_chart_bottom_legend[phase].push(metric_data.clean_name);

                        if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[0]}`] == null) {
                            total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[0]}`] = []
                        }
                        total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[0]}`].push(detail_data.mean)
                        phase_key0_has_machine_energy = true
                        found_bottom_chart_metric = metric;
                    }
                }

                if (comparison_case == null && co2_metrics_condition(metric)) {
                    if(co2_calculated) {
                        showWarning(phase, 'CO2 was already calculated! Do you have CO2 Machine reporters set');
                    }
                    co2_calculated = true;
                    calculateCO2(phase, detail_data.mean);
                }

                if (!multi_comparison) {
                    displaySimpleMetricBox(phase,metric, metric_data, detail_data, keys[0]);
                    if(comparison_case !== null) {
                        displayCompareChart(
                            phase,
                            `${metric_data.clean_name} (${metric_data.source} ${detail}) - [${metric_data.unit}]`,
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
                        showWarning(phase, `${metric} ${detail} was missing from one comparison. Skipping`);
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

                    if(radar_chart_condition(metric) && multi_comparison) {
                        radar_chart_data[1].push(detail_data2.mean)
                    }

                    if (top_bar_chart_condition(metric)) {
                        top_bar_chart_data[1].push(detail_data2.mean)
                    }
                    if (total_chart_bottom_condition(metric)) {
                        if(found_bottom_chart_metric && found_bottom_chart_metric !== metric) {
                            showWarning(phase, `Another metric for the bottom chart was already set (${found_bottom_chart_metric}), skipping ${metric} and only first one will be shown.`);
                        } else {
                            if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[1]}`] == null) {
                                total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[1]}`] = []
                            }

                            total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[1]}`].push(detail_data2.mean)
                            phase_key1_has_machine_energy = true
                        }
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

        if (phase_key0_has_machine_energy == false) { // add dummy
            if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[0]}`] == null) {
                total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[0]}`] = []
            }
            total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[0]}`].push(0)
        }
        if (phase_key1_has_machine_energy == false && multi_comparison == 2) { // add dummy
            if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[1]}`] == null) {
                total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[1]}`] = []
            }
            total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${keys[1]}`].push(0)
        }

        if(multi_comparison) {
            displayKeyMetricsRadarChart(
                radar_legend,
                radar_chart_labels,
                radar_chart_data,
                phase
            );
        } else if(comparison_case != null) { // stats.html does not even have it. so only remove for Repeated Run etc.
            removeKeyMetricsRadarChart(phase)
        }

        displayKeyMetricsBarChart(
            radar_legend,
            top_bar_chart_labels,
            top_bar_chart_data,
            phase
        )

        // displayKeyMetricsEmbodiedCarbonChart(phase);

    }
    displayTotalChart(
        total_chart_bottom_legend,
        total_chart_bottom_labels,
        total_chart_bottom_data
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

