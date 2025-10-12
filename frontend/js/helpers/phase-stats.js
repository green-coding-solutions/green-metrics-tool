const createTableHeader = (phase, comparison_keys, comparison_case, comparison_amounts) => {
    let tr = document.querySelector(`div.tab[data-tab='${phase}'] .compare-metrics-table thead`).insertRow();

    if (comparison_amounts >= 2) {
        tr.innerHTML = `
            <th>Metric</th>
            <th>Source</th>
            <th>Scope</th>
            <th>Detail Name</th>
            <th>Type</th>
            <th><span class="overflow-ellipsis" style="width: 100px; display:block;" title="${escapeString(comparison_keys[0])}">${replaceRepoIcon(comparison_keys[0])}</span></th>
            <th><span class="overflow-ellipsis" style="width: 100px; display:block;" title="${escapeString(comparison_keys[1])}">${replaceRepoIcon(comparison_keys[1])}</span></th>
            <th>Unit</th>
            <th>Change</th>
            <th>Significant (T-Test)</th>
            <th><span data-position="bottom left" data-inverted="" data-tooltip="Achieved sampling rate (Mean of means, max of 95p and max of max)"><i class="question circle icon"></i> SR (Ø/95p/max)</span></th>`;
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
            <th><i class="question circle icon"></i> Max. (Ø)</th>
            <th><i class="question circle icon"></i> Min. (Ø)</th>
            <th><span data-position="bottom left" data-inverted="" data-tooltip="Achieved sampling rate (Mean of means, max of 95p and max of max)"><i class="question circle icon"></i> SR (Ø/95p/max)</span></th>`;
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
            <th>Min.</th>
            <th><span data-position="bottom left" data-inverted="" data-tooltip="Achieved sampling rate"><i class="question circle icon"></i>SR (mean/95p/max)</span></th>`;
    }
}

const getAndShowPhase = () => {
    let shown_phase = '[RUNTIME]'; // default
    let phase_to_display = decodeURIComponent(window.location.hash).split('#')[1];
    if (phase_to_display != null) {
        const allowed_phases = ['BASELINE', 'INSTALLATION', 'BOOT', 'IDLE', 'RUNTIME', 'REMOVE'];
        phase_to_display = phase_to_display.split('__');
        if (allowed_phases.includes(phase_to_display[0])) {
            document.querySelector(`a.step[data-tab="[${phase_to_display[0]}]"`).dispatchEvent(new Event('click'));
            shown_phase = `[${phase_to_display[0]}]`;
        } else {
            document.querySelector('a.step[data-tab="[RUNTIME]"]').dispatchEvent(new Event('click'));
        }
        const sub_phase_regex = /^[\.\s0-9a-zA-Z_\(\)-]+$/; // Matches strings containing only letters and digits
        if (phase_to_display[1] != null && sub_phase_regex.test(phase_to_display[1])) {
            try {
                document.querySelector(`a.runtime-step[data-tab="${phase_to_display[1]}"`).dispatchEvent(new Event('click'));
            } catch(err) {
                console.log('Could not match phase to show', err);
            }

        }
    } else {
        // although there are multiple .step.runtime-step containers the first one
        // marks the first runtime step and is shown by default
        document.querySelector('a.step[data-tab="[RUNTIME]"]').dispatchEvent(new Event('click'));
    }

    return shown_phase;
}

const showWarning = (phase, warning) => {
    if (phase == '[RUNTIME]' ) phase = '[[RUNTIME]]'; // map to "All Flows" phase

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
const createPhaseTab = (phase, hidden) => {
    let phase_tab_node = document.querySelector(`a.step[data-tab='${phase}']`);

    if(phase_tab_node == null) {

        let runtime_tab_node = document.querySelector('a.runtime-step');
        let cloned_tab_node = runtime_tab_node.cloneNode(true);
        cloned_tab_node.style.display = '';
        cloned_tab_node.innerText = phase;
        cloned_tab_node.setAttribute('data-tab', phase);
        runtime_tab_node.parentNode.appendChild(cloned_tab_node)

        if (hidden === true) {
            document.querySelector('#runtime-hidden-info').classList.remove('hidden');
            const tab = document.querySelector(`.item.runtime-step[data-tab="${phase}"]`)
            tab.innerHTML = `<i class="low vision icon"></i> <span class="hidden-phase-name">${tab.innerText}</span>`
            tab.classList.add("hidden-phase-tab")
        }

        let phase_step_node = document.querySelector('.runtime-tab');
        let cloned_step_node = phase_step_node.cloneNode(true);
        cloned_step_node.style.display = '';
        cloned_step_node.setAttribute('data-tab', phase);
        phase_step_node.parentNode.appendChild(cloned_step_node)
    }
}


const buildPhaseTabs = (phase_stats_object) => {

    for (const phase in phase_stats_object['data']) {
        createPhaseTab(phase, phase_stats_object['data'][phase].hidden); // will not create already existing phase tabs
        createTableHeader(
            phase,
            phase_stats_object.comparison_identifiers,
            phase_stats_object.comparison_case,
            phase_stats_object.comparison_identifiers.length
        )
    }

    document.querySelectorAll('#runtime-sub-phases .item').forEach(el => {
        el.addEventListener('click', showHiddenPhaseTab)
    })

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

}

/*
    We traverse the multi-dimensional metrics object only once and fill data
    in the appropriate variables for metric-boxes and charts

    render* means that build* and display* functions are mixed
*/
const renderCompareChartsForPhase = (phase_stats_object, phase='[RUNTIME]', run_count=1) => {

    // we now traverse all branches of the tree
    // the tree is sparese, so although we see all metrics that are throughout all phases and comparison_keys
    // not every branch has a leaf with the metric for the corresponding comparsion_key ... it might be missing
    // we must fill this value than with a NaN in the charts

    // if we have a comparison case between the two we just display the difference between them
    // if we have a repetition case we display the STDDEV
    // otherwise we just display the value

    // unsure atm what to do in a Diff scenario ... filling with 0 can be misleading
    if (window.__rendered_phases == null) {
        window.__rendered_phases = {};
    } else if (window.__rendered_phases[phase] != null) return; // we have already rendered this phase!

    window.__rendered_phases[phase] = true;

    let phase_data = phase_stats_object['data'][phase]['data'];

    let radar_chart_labels = [];
    let radar_chart_data = [...Array(phase_stats_object.comparison_identifiers.length)].map(e => Array(0));

    let top_bar_chart_labels = [];
    let top_bar_chart_data =  [[],[]];
    let top_bar_chart_unit = null;

    let compare_chart_unit = null;

    let co2_calculated = false;

    for (const metric_name in phase_data) {
        let metric_data = phase_data[metric_name]
        let found_radar_chart_item = false;

        for (const detail_name in metric_data['data']) {
            let detail_data = metric_data['data'][detail_name]

            /*
                BLOCK LABELS
                This block must be done outside of the key loop and cannot use a Set() datastructure
                as we can have the same metric multiple times just with different detail names
            */
            if(radar_chart_condition(metric_name) && phase_stats_object.comparison_identifiers.length >= 2) {
                radar_chart_labels.push(getPretty(metric_name, 'clean_name'));
            }

            if (top_bar_chart_condition(metric_name)) {
                top_bar_chart_labels.push(`${getPretty(metric_name, 'clean_name')} (${getPretty(metric_name, 'source')})`);
            }

            /* END BLOCK LABELS*/

            if (
                (phase_stats_object.comparison_identifiers.length == 2
                    && (
                        detail_data['data'][phase_stats_object.comparison_identifiers[0]]?.values == null
                        || detail_data['data'][phase_stats_object.comparison_identifiers[0]]?.values?.includes(null)
                        || detail_data['data'][phase_stats_object.comparison_identifiers[1]]?.values == null
                        || detail_data['data'][phase_stats_object.comparison_identifiers[1]].values.includes(null)
                    )
                )
                ||
                (phase_stats_object.comparison_identifiers.length == 1 && detail_data['data'][phase_stats_object.comparison_identifiers[0]]?.values?.includes(null))
            ) {
                showWarning(phase, `${metric_name} ${detail_name} was missing from at least one comparison.`)
            }

            let compare_chart_data = []
            let compare_chart_mark = []
            let compare_chart_labels = []
            let metric_box_data = Array(phase_stats_object.comparison_identifiers.length).fill().map(() => ({}))

            // we loop over all keys that exist, not over the one that are present in detail_data['data']
            phase_stats_object.comparison_identifiers.forEach((key,key_index) => {
                const [transformed_mean, transformed_unit] = convertValue(detail_data['data'][key]?.mean, metric_data.unit)
                const [transformed_ci, ] = convertValue(detail_data['data'][key]?.ci, metric_data.unit)
                const transformed_values = detail_data['data'][key]?.values.map( value => convertValue(value, metric_data.unit)[0]);
                compare_chart_unit = transformed_unit;

                if(radar_chart_condition(metric_name) && phase_stats_object.comparison_identifiers.length >= 2) {
                    radar_chart_data[key_index].push(transformed_mean)
                }

                if (top_bar_chart_condition(metric_name)) {
                    top_bar_chart_unit = transformed_unit;
                    top_bar_chart_data[key_index].push(transformed_mean)
                }

                if (phase_stats_object.comparison_case == null && psu_machine_carbon_metric_condition(metric_name)) {
                    if(co2_calculated) {
                        showWarning(phase, 'CO2 was already calculated! Do you have multiple machine energy reporters set?');
                    }
                    // mean will always be present, as we only have one key and thus we need no ?.
                    calculateCO2(phase, detail_data['data'][key].mean); // must take the untransformed value, as it expects ug
                    co2_calculated = true;
                }

                metric_box_data[key_index] = detail_data['data'][key]?.mean

                compare_chart_data.push(transformed_values)
                compare_chart_labels.push(`${phase_stats_object.comparison_case}: ${key}`)
                compare_chart_mark.push({
                    name:'Confidence Interval',
                    bottom: transformed_mean-transformed_ci,
                    top: transformed_mean+transformed_ci
                })
            }) // end key

            if (phase_stats_object.comparison_identifiers.length == 1) {
                // Note: key is still the set variable from the for loop earlier
                displaySimpleMetricBox(phase, metric_name, metric_data, detail_name, detail_data['data'][phase_stats_object.comparison_identifiers[0]], phase_stats_object.comparison_case);
            } else {
                displayDiffMetricBox(
                    phase, metric_name, metric_data, detail_name, metric_box_data,
                    detail_data.is_significant
                );
            }
            if(phase_stats_object.comparison_case != null) { // compare charts will display for everything apart stats.html
                displayCompareChart(
                    phase,
                    `${getPretty(metric_name, 'clean_name')} via ${getPretty(metric_name, 'source')} - ${detail_name} <i data-tooltip="${getPretty(metric_name, 'explanation')}" data-position="bottom center" data-inverted><i class="question circle icon link"></i></i>`,
                    compare_chart_unit,
                    compare_chart_labels,
                    compare_chart_data,
                    compare_chart_mark,
                    null, // graphic
                    phase_stats_object.comparison_details,
                    phase_stats_object.comparison_identifiers,
                );
            }
        } // end detail
    } // end metric

    let radar_legend = phase_stats_object.comparison_identifiers.map(e => `${phase_stats_object.comparison_case}: ${e}`)

    if(phase_stats_object.comparison_identifiers.length >= 2) {
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
        phase,
        top_bar_chart_unit,
    )

    // displayKeyMetricsEmbodiedCarbonChart(phase);

    $(`div.tab[data-tab='${phase}'] .compare-metrics-table.sortable`).tablesort();

    window.dispatchEvent(new Event('resize'));
}

const buildTotalChartData = (phase_stats_object) => {

    let total_chart_bottom_data =  {};
    let total_chart_bottom_legend =  {};
    let total_chart_bottom_labels = [];
    let transformed_total_chart_bottom_unit = null;

    for (const phase in phase_stats_object['data']) {
        let phase_data = phase_stats_object['data'][phase]['data'];

        total_chart_bottom_labels.push(phase);
        total_chart_bottom_legend[phase]  = [];

        // the following variables are needed for filling missing values in charts and the machine energy
        // we need to keep track if in the coming loop a matching metric was found or mitigate the missing value
        let found_bottom_chart_metric = false;
        const bottom_chart_present_keys = Object.fromEntries(phase_stats_object.comparison_identifiers.map(e => [e, false]))

        for (const metric_name in phase_data) {
            let metric_data = phase_data[metric_name]

            for (const detail_name in metric_data['data']) {
                let detail_data = metric_data['data'][detail_name]

                if (total_chart_bottom_condition(metric_name)) {
                    if(found_bottom_chart_metric) {
                        showWarning(phase, `Another metric for the bottom chart was already set (${found_bottom_chart_metric}), skipping ${metric_name} and only first one will be shown.`);
                    } else {
                        total_chart_bottom_legend[phase].push(getPretty(metric_name, 'clean_name'));
                        found_bottom_chart_metric = `${metric_name} ${detail_name}`;
                        total_chart_bottom_unit = convertValue(0, metric_data.unit)[1]
                    }
                }
                // we loop over all keys that exist, not over the one that are present in detail_data['data']
                phase_stats_object.comparison_identifiers.forEach((key,key_index) => {
                    const [transformed_total_chart_bottom_mean, transformed_unit] = convertValue(detail_data['data'][key]?.mean, metric_data.unit)

                    if (total_chart_bottom_condition(metric_name) && `${metric_name} ${detail_name}` == found_bottom_chart_metric) {
                        transformed_total_chart_bottom_unit = transformed_unit;
                        if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] == null) {
                            total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] = []
                        }
                        total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`].push(transformed_total_chart_bottom_mean)
                        bottom_chart_present_keys[key] = true
                    }
                })
            } // end metric_data['data']
        } // end phase_data

        // a phase can have no bottom chart metric and must be null-filled
        // this can for instance happen if a phase is too short and no metric was reported in the timespan
        for (const key in bottom_chart_present_keys) {
            if(bottom_chart_present_keys[key] == false) {
                if(total_chart_bottom_data?.[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] == null) {
                    total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`] = []
                }
                total_chart_bottom_data[`${TOTAL_CHART_BOTTOM_LABEL} - ${key}`].push(null)
            }
        }

    } // end phase_stats_object['data']

    return [total_chart_bottom_legend, total_chart_bottom_labels, total_chart_bottom_data, transformed_total_chart_bottom_unit];
}
