const setupPhaseTabs = (phase_stats_object) => {
    let keys = Object.keys(phase_stats_object['data'])
    // only need to traverse one branch in case of a comparison
    // no need to display phases that do not exist in both
    for (key in phase_stats_object) {
        for (phase in phase_stats_object['data'][key]) {
            createPhaseTab(phase); // will not create already existing phase tabs
            console.log("Phase", phase);
            let tr = document.querySelector(`div.tab[data-tab='${phase}'] .compare-metrics-table thead`).insertRow();
            if (keys.length == 2) {
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
        cloned_tab_node.innerText = phase;

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
    let comparison_case = phase_stats_object.comparison_case
    console.log("comparison_case", comparison_case);
    let keys = Object.keys(phase_stats_object['data'])
    console.log(keys);
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

    let index = 0;
    let keys_length = keys.length;
    console.log("Keys length", keys_length);
    for (index in keys) {
        key = keys[index];
        console.log("Iterating", key);
        console.log(phase_stats_object['data']);
        for (phase in phase_stats_object['data'][key]) {

            // what I want to do is to:
            // - check if we have a multi comparison
            // - if not, we just set the values for the single charts
            // - if we have a multi-key comparison
            //     - just iterate over all the keys. Push all metrics and their details and the corresponding counterparts
            //     - then iterate over the next key. If the metric is already present then skip
            //     - however, if it is not present, than add it also

            let phase_data = phase_stats_object['data'][key][phase];

            let radar_chart_labels = [];
            let radar_chart_data = [...Array(keys_length)].map(e => Array(0));

            let energy_chart_labels = [];
            let energy_chart_data =  [...Array(keys_length)].map(e => Array(0));
            machine_energy_chart_labels.push(phase);
            machine_energy_chart_legend[phase]  = [];

            let has_machine_energy = false;

            for (metric in phase_data) {
                let metric_data = phase_data[metric]
                for (detail in metric_data['data']) {

                    if detail is already known, then we skip
                    let detail_data = metric_data['data'][detail]

                    radar_chart_labels.push(metric_data.clean_name);
                    if (metric.indexOf('_energy_') !== -1) {
                        energy_chart_labels.push(metric_data.clean_name);
                    }

                    if (metric.match(/^.*_energy_.*_machine$/) !== null) {
                        machine_energy_chart_legend[phase].push(metric_data.clean_name);
                        if(machine_energy_chart_data?.[`Machine Energy - ${key}`] == null) {
                            machine_energy_chart_data[`Machine Energy - ${key}`] = []
                        }
                        machine_energy_chart_data[`Machine Energy - ${key}`].push(detail_data.mean)
                        has_machine_energy = true
                    }


                    let metric_box_data = []
                    let detail_chart_data = []
                    let detail_chart_mark = []
                    let detail_chart_labels = []

                    // now we go through all the other keys and find the matching metrics.
                    // we need to do this in an inner loop, as if they do not exist, than we need to fill a NaN value

                    for (inner_index in keys) {
                        let inner_key = keys[index]
                        let metric_data_x = phase_stats_object?.['data']?.[inner_key]?.[phase]?.[metric]
                        let detail_data_x = metric_data_x?.['data']?.[detail];

                        if (detail_data_x == undefined) {
                            // the metric or phase might not be present in the other run
                            // note that this debug statement does not log when on the second branch more metrics are
                            // present that are not shown. However we also do not want to display them.
                            console.log(`${metric} ${detail} was missing from ${inner_key}. Skipping`);
                            return;
                        }

                        detail_chart_labels.push(`${comparison_case}: ${inner_key}`)
                        detail_chart_data.push(detail_data_x.values)
                        detail_chart_mark.push(
                            {name:'CI', bottom: detail_data_x.mean-detail_data_x.ci, top: detail_data_x.mean+detail_data_x.ci})

                        if (metric.indexOf('_energy_') !== -1) {
                            energy_chart_data[inner_index].push(detail_data_x.mean)
                        }
                        radar_chart_data[inner_index].push(detail_data_x.mean)
                        metric_box_data.push(detail_data_x)
                    }

                    // now we have iterated through all keys for this metric and aggregated all paired data
                    // we can now display the compare chart

                    if (keys_length > 1) {
                        displayDiffMetricBox(
                            phase, metric, metric_data, metric_box_data,
                            phase_stats_object.statistics?.[phase]?.[metric]?.[detail]?.is_significant
                        );
                    } else { // no comparison case and thus only one key. But can still be multiple items if repeated run
                        console.log("Simple metric box");
                        displaySimpleMetricBox(phase,metric, metric_data, detail_data);
                    }


                    if(comparison_case == null) {
                        if(metric.match(/^.*_co2_.*_machine$/) !== null) {
                            calculateCO2(phase, detail_data.mean);
                        }
                    } else  {
                        displayCompareChart(
                            phase,
                            `${metric_data.clean_name} (${detail}) - [${metric_data.unit}]`,
                            detail_chart_labels,
                            detail_chart_data,
                            detail_chart_mark,
                        );
                    }
                } // end detail
            } // end metric

            if (has_machine_energy == false) { // add dummy
                if(machine_energy_chart_data?.[`Machine Energy - ${key}`] == null) {
                    machine_energy_chart_data[`Machine Energy - ${key}`] = []
                }
                machine_energy_chart_data[`Machine Energy - ${key}`].push(NaN)
            }

            let radar_legend = keys.map(e => `${comparison_case}: ${e}`)

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

        } // phase end
    } // keys end

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

