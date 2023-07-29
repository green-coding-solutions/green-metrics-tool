const createTableHeader = (phase, comparison_keys, comparison_case, comparison_amounts) => {
    let tr = document.querySelector(`div.tab[data-tab='${phase}'] .compare-metrics-table thead`).insertRow();

    if (comparison_amounts >= 2) {
        tr.innerHTML = `
            <th>Metric</th>
            <th>Source</th>
            <th>Scope</th>
            <th>Detail Name</th>
            <th>Type</th>
            <th><span class="overflow-ellipsis" style="width: 100px; display:block;" title="${comparison_keys[0]}">${replaceRepoIcon(comparison_keys[0])}</span></th>
            <th><span class="overflow-ellipsis" style="width: 100px; display:block;" title="${comparison_keys[1]}">${replaceRepoIcon(comparison_keys[1])}</span></th>
            <th>Unit</th>
            <th>Change</th>
            <th>Significant (T-Test)</th>`;
    } else if(comparison_case !== null) {
        tr.innerHTML = `
            <th>Metric</th>
            <th>Source</th>
            <th>Scope</th>
            <th>Detail Name</th>
            <th>Type</th>
            <th>Value</th>
            <th>Unit</th>
            <th>StdDev</th>
            <th>Max.</th>
            <th>Min.</th>
            <th>Max. (of means)</th>
            <th>Min. (of means)</th>`;
    } else {
        tr.innerHTML = `
            <th>Metric</th>
            <th>Source</th>
            <th>Scope</th>
            <th>Detail Name</th>
            <th>Type</th>
            <th>Value</th>
            <th>Unit</th>
            <th>Max.</th>
            <th>Min.</th>`;
    }
}

const showWarning = (phase, warning) => {
    if (phase == '[RUNTIME]' ) phase == '[[RUNTIME]]';
    document.querySelector(`div.tab[data-tab='${phase}'] .ui.warning.message`).classList.remove('hidden');
    const newListItem = document.createElement("li");
    newListItem.textContent = warning;
    document.querySelector(`div.tab[data-tab='${phase}'] .ui.warning.message ul`).appendChild(newListItem);
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

    if(phase_tab_node == null) {
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
const displayComparisonMetrics = (phase_stats_object) => {
    // we now traverse all branches of the tree
    // the tree is sparese, so although we see all metrics that are throughout all phases and comparison_keys
    // not every branch has a leaf with the metric for the corresponding comparsion_key ... it might be missing
    // we must fill this value than with a NaN in the charts

    // if we have a comparison case between the two we just display the difference between them
    // if we have a repetition case we display the STDDEV
    // otherwise we just display the value

    // unsure atm what to do in a Diff scenario ... filling with 0 can be misleading

    let total_chart_bottom_data =  {};
    let total_chart_bottom_legend =  {};
    let total_chart_bottom_labels = [];

    for (phase in phase_stats_object['data']) {
        createPhaseTab(phase); // will not create already existing phase tabs
        createTableHeader(
            phase,
            phase_stats_object.comparison_details,
            phase_stats_object.comparison_case,
            phase_stats_object.comparison_details.length
        )

        let phase_data = phase_stats_object['data'][phase];

        let radar_chart_labels = [];
        let radar_chart_data = [...Array(phase_stats_object.comparison_details.length)].map(e => Array(0));

        let top_bar_chart_labels = [];
        let top_bar_chart_data =  [[],[]];
        total_chart_bottom_labels.push(phase);
        total_chart_bottom_legend[phase]  = [];

        let co2_calculated = false;
        let found_bottom_chart_metric = false;
        const bottom_chart_present_keys = phase_stats_object.comparison_details.reduce((acc, value) => {
          acc[value] = false;
          return acc;
        }, {});


        for (metric in phase_data) {
            let metric_data = phase_data[metric]
            let found_radar_chart_item = false;

            for (detail in metric_data['data']) {
                let detail_data = metric_data['data'][detail]

                /*
                    BLOCK LABELS
                    This block must be done outside of the key loop and cannot use a Set() datastructure
                    as we can have the same metric multiple times just with different detail names
                */
                if(radar_chart_condition(metric) && phase_stats_object.comparison_details.length >= 2) {
                    radar_chart_labels.push(metric_data.clean_name);
                }

                if (top_bar_chart_condition(metric)) {
                    top_bar_chart_labels.push(`${metric_data.clean_name} (${metric_data.source})`);
                }

                if (total_chart_bottom_condition(metric)) {
                    if(found_bottom_chart_metric) {
                        showWarning(phase, `Another metric for the bottom chart was already set (${found_bottom_chart_metric}), skipping ${metric} and only first one will be shown.`);
                    } else {
                        total_chart_bottom_legend[phase].push(metric_data.clean_name);
                        found_bottom_chart_metric = metric;
                    }
                }
                /* END BLOCK LABELS*/

                if (Object.keys(detail_data['data']).length != phase_stats_object.comparison_details.length) {
                    showWarning(phase, `${metric} ${detail} was missing from at least one comparison.`);
                }

                let compare_chart_data = []
                let compare_chart_mark = []
                let compare_chart_labels = []
                let metric_box_data = [...Array(phase_stats_object.comparison_details.length)].map(e => null)


                let found_radar_chart_item_key = null;

                // we loop over all keys that exist, not over the one that are present in detail_data['data']
                phase_stats_object.comparison_details.forEach((key,key_index) => {
                    if(radar_chart_condition(metric) && phase_stats_object.comparison_details.length >= 2) {
                        radar_chart_data[key_index].push(detail_data['data'][key]?.mean)
                    }

                    if (top_bar_chart_condition(metric)) {
                        top_bar_chart_data[key_index].push(detail_data['data'][key]?.mean)
                    }
                    if (total_chart_bottom_condition(metric) && metric == found_bottom_chart_metric) {
                        if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] == null) {
                            total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] = []
                        }
                        total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`].push(detail_data['data'][key]?.mean)
                        bottom_chart_present_keys[key] = true
                    }

                    if (phase_stats_object.comparison_case == null && co2_metrics_condition(metric)) {
                        if(co2_calculated) {
                            showWarning(phase, 'CO2 was already calculated! Do you have CO2 Machine reporters set');
                        }
                        // mean will always be present, as we only have one key and thus we need no ?.
                        calculateCO2(phase, detail_data['data'][key].mean);
                        co2_calculated = true;
                    }
                    metric_box_data[key_index] = detail_data['data'][key]?.mean
                    compare_chart_data.push(detail_data['data'][key]?.values)
                    compare_chart_labels.push(`${phase_stats_object.comparison_case}: ${key}`)
                    compare_chart_mark.push({
                        name:'Confidence Interval',
                        bottom: detail_data['data'][key]?.mean-detail_data['data'][key]?.ci,
                        top: detail_data['data'][key]?.mean+detail_data['data'][key]?.ci
                    })
                }) // end key

                if (phase_stats_object.comparison_details.length == 1) {
                    // Note: key is still the set variable from the for loop earlier
                    displaySimpleMetricBox(phase,metric, metric_data, detail_data['name'], detail_data['data'][phase_stats_object.comparison_details[0]]);
                } else {
                    displayDiffMetricBox(
                        phase, metric, metric_data, detail_data['name'], metric_box_data,
                        detail_data.is_significant
                    );
                }
                if(phase_stats_object.comparison_case !== null) { // compare charts will display for everything apart stats.html
                    displayCompareChart(
                        phase,
                        `${metric_data.clean_name} (${detail}) - [${metric_data.unit}]`,
                        compare_chart_labels,
                        compare_chart_data,
                        compare_chart_mark,
                    );
                }
            } // end detail
        } // end metric

        // a phase had no bottom chart metric and must be null-filled
        // this can for instance happen if a phase is too short and no metric was reported in the timespan
        for (key in bottom_chart_present_keys) {
            if(bottom_chart_present_keys[key] == false) {
                if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] == null) {
                    total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] = []
                }
                total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`].push(NaN)
            }
        }

        let radar_legend = phase_stats_object.comparison_details.map(e => `${phase_stats_object.comparison_case}: ${e}`)

        if(phase_stats_object.comparison_details.length >= 2) {
            displayKeyMetricsRadarChart(
                radar_legend,
                radar_chart_labels,
                radar_chart_data,
                phase
            );
        } else if(phase_stats_object.comparison_case != null) {
            // stats.html does not even have it. so only remove for Repeated Run etc.
            removeKeyMetricsRadarChart(phase)
        }

        displayKeyMetricsBarChart(
            radar_legend,
            top_bar_chart_labels,
            top_bar_chart_data,
            phase
        )

        // displayKeyMetricsEmbodiedCarbonChart(phase);

    } // phase end

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
