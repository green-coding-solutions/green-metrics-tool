class CO2Tangible extends HTMLElement {
   connectedCallback() {
        this.innerHTML = `
                <div class="ui blue icon message">
                    <i class="question circle icon"></i>
                    <div class="content">
                        <div class="header">
                            How much is this value of CO2 to something tangible?
                        </div>
                        <p>CO2 of software per run is relatively small. The values get big though cause software is repeatedly run.<br>Therefore the following numbers reflect the CO2 value of the software as if it was run for 1,000 times a day over the course of a year (365 days).</p>
                        <p>Source of CO2 to Tree etc. conversion: <a href="https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator">EPA</a></p>
                    </div>
                </div>
                <div class="ui five cards stackable">
                    <div class="card">
                        <div class="content">
                            <div class="ui header">Trees</div>
                            <div class="ui small statistic">
                                <div class="value">
                                    <i class="tree icon"></i> <span class="co2-trees">-</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="content">
                            <div class="ui header">Distance driven</div>
                            <div class="ui small statistic">
                                <div class="value">
                                    <i class="truck pickup icon"></i> <span class="co2-distance-driven">-</span>
                                </div>
                            </div>
                            <div class="ui bottom right attached label distance-units">in miles by car</div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="content">
                            <div class="ui header">Gasoline</div>
                            <div class="ui small statistic">
                                <div class="value">
                                    <i class="gas pump icon"></i> <span class="co2-gasoline">-</span>
                                </div>
                            </div>
                            <div class="ui bottom right attached label gasoline-units">in gallons</div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="content">
                            <div class="ui header">Flights</div>
                            <div class="ui small statistic">
                                <div class="value">
                                    <i class="plane departure icon"></i> <span class="co2-flights">-</span>
                                </div>
                            </div>
                            <div class="ui bottom right attached label">Berlin &raquo; NYC</div>
                        </div>
                    </div>
                    <div class="ui card">
                        <div class="ui content">
                            <div class="ui header">co2 budget / day</div>
                            <div class="ui small statistic">
                                <div class="value">
                                    <i class="user icon"></i> <span class="co2-budget-utilization"> - %</span>
                                </div>
                            </div>
                            <div class="ui bottom right attached label">for CPU + Memory + Network</div>
                        </div>
                    </div>
                </div><!-- end ui five cards stackable -->`;
    }
}

customElements.define('co2-tangible', CO2Tangible);

const fetchAndFillRunData = async (url_params) => {

    let run = null;

    try {
        run = await makeAPICall('/v2/run/' + url_params['id'])
    } catch (err) {
        showNotification('Could not get run data from API', err);
        return
    }

    const run_data = run.data

    for (const item in run_data) {
        if (item == 'machine_id') {
            document.querySelector('#run-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${run_data?.[item]} (${GMT_MACHINES[run_data?.[item]] || run_data?.[item]})</td></tr>`);
        } else if (item == 'runner_arguments') {
            fillRunTab('#runner-arguments', run_data[item]); // recurse
        } else if (item == 'machine_specs') {
            fillRunTab('#machine-specs', run_data[item]); // recurse
        } else if(item == 'usage_scenario') {
            // we would really like to highlight here what was replaced, but since the replace mechanism is so powerful that even the !include command could be modified we can only replace after the file was merged. Thus it is not possible to know after what the replacements are
            document.querySelector("#usage-scenario").textContent = json2yaml(run_data[item]);
        } else if(item == 'usage_scenario_variables') {
            if (Object.keys(run_data[item]).length > 0) {
                const container = document.querySelector("#usage-scenario-variables ul");
                for (const key in run_data[item]) {
                    container.insertAdjacentHTML('beforeend', `<li><span class="ui label">${key}=${run_data[item][key]}</span></li>`)
                }
            } else {
                document.querySelector("#usage-scenario-variables").insertAdjacentHTML('beforeend', `N/A`)
            }

        } else if(item == 'logs' && run_data?.[item] != null) {
            // textContent does escaping for us
            document.querySelector("#logs").textContent = run_data[item];
        } else if(item == 'measurement_config') {
            fillRunTab('#measurement-config', run_data[item]); // recurse
        } else if(item == 'phases' || item == 'id') {
            // skip
        }  else if(item == 'commit_hash') {
            if (run_data?.[item] == null) continue; // some old runs did not save it
            let commit_link = buildCommitLink(run_data);
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td><a href="${commit_link}" target="_blank">${run_data?.[item]}</a></td></tr>`)
        } else if(item == 'name' || item == 'filename' || item == 'branch') {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${run_data?.[item]}</td></tr>`)
        } else if(item == 'failed' && run_data?.[item] == true) {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Status</strong></td><td><span class="ui red horizontal label">This run has failed. Please see logs for details</span></td></tr>`)
        } else if(item == 'start_measurement' || item == 'end_measurement') {
            document.querySelector('#run-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td title="${run_data?.[item]}">${new Date(run_data?.[item] / 1e3)}</td></tr>`)
        } else if(item == 'created_at' ) {
            document.querySelector('#run-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td title="${run_data?.[item]}">${new Date(run_data?.[item])}</td></tr>`)
        } else if(item == 'invalid_run' && run_data?.[item] != null) {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td><span class="ui yellow horizontal label">${run_data?.[item]}</span></td></tr>`)
        } else if(item == 'gmt_hash') {
            document.querySelector('#run-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td><a href="https://github.com/green-coding-solutions/green-metrics-tool/commit/${run_data?.[item]}">${run_data?.[item]}</a></td></tr>`);
        } else if(item == 'uri') {
            let entry = run_data?.[item];
            if(run_data?.[item].indexOf('http') === 0) entry = `<a href="${run_data?.[item]}">${run_data?.[item]}</a>`;
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${entry}</td></tr>`);
        } else {
            document.querySelector('#run-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${run_data?.[item]}</td></tr>`)
        }
    }

    // create new custom field
    // timestamp is in microseconds, therefore divide by 10**6
    const measurement_duration_in_s = (run_data.end_measurement - run_data.start_measurement) / 1e6
    const measurement_duration_display = (measurement_duration_in_s > 60) ? `${numberFormatter.format(measurement_duration_in_s / 60)} min` : `${numberFormatter.format(measurement_duration_in_s)} s`

    document.querySelector('#run-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>duration</strong></td><td title="${measurement_duration_in_s} seconds">${measurement_duration_display}</td></tr>`)

    if (run_data.invalid_run) {
        showNotification('Run measurement has been marked as invalid', run_data.invalid_run);
        document.body.classList.add("invalidated-measurement")
    }

}

const buildCommitLink = (run_data) => {
    let commit_link;
    commit_link = run_data['uri'].endsWith('.git') ? run_data['uri'].slice(0, -4) : run_data['uri']
    if (run_data['uri'].includes('github')) {
        commit_link = commit_link + '/tree/' + run_data['commit_hash']
    }
    else if (run_data['uri'].includes('gitlab')) {
        commit_link = commit_link + '/-/tree/' + run_data ['commit_hash']
    }
    return commit_link;
}

const fillRunTab = async (selector, data, parent = '') => {
    for (const item in data) {

        if(data[item] != null && typeof data[item] == 'object') {
            if (parent == '') {
                document.querySelector(selector).insertAdjacentHTML('beforeend', `<tr><td><strong><h2>${item}</h2></strong></td><td></td></tr>`)
            }
            fillRunTab(selector, data[item], `${item}.`)
        } else {
            document.querySelector(selector).insertAdjacentHTML('beforeend', `<tr><td><strong>${parent}${item}</strong></td><td>${data?.[item]}</td></tr>`)
        }
    }
}


const buildTimelineChartData = async (measurements_data) => {
    const metrics = {}
    const t0 = performance.now();

    const transform_timelines_energy_to_power = localStorage.getItem('transform_timelines_energy_to_power') === 'true' ? true : false;

    try {
         // define here as var (not let!), so we can alert it later in error case.
         // this was done, because we apparently often forget to add new metrics here and this helps debugging quickly with the alert later :)
        var metric_name = null

        // this can be let
        let time_before = 0;
        let detail_name = null;

        measurements_data.forEach(el => {
            const time_after = el[1] / 1000000;
            const time_in_ms = el[1] / 1000; // divide microseconds timestamp to ms to be handled by charting lib
            let value = el[3];
            let metric_changed = false;
            let unit = el[4];

            if(metric_name !== el[2] || detail_name !== el[0]) {
                // metric changed -> reset time counter and update variables
                metric_name = el[2];
                detail_name = el[0];
                time_before = time_after;
                metric_changed = true;
            }

            [value, unit] = convertValue(value, unit);
            if (metrics[metric_name] == undefined) {
                metrics[metric_name] = {
                    series: {},
                    unit: unit,
                    converted_unit: unit
                }
            }

            if(transform_timelines_energy_to_power && metrics[metric_name].unit == 'J') {
                value = value/(time_after-time_before); // convert Joules to Watts by dividing through the time difference of two measurements
                metrics[metric_name].converted_unit = 'W';
            } else if(!transform_timelines_energy_to_power && metrics[metric_name].unit == 'W') {
                value = value*(time_after-time_before); // convert Watts to Joules by multiplying with the time difference of two measurements
                metrics[metric_name].converted_unit = 'J';
            }
            time_before = time_after;

            if(metric_changed && transform_timelines_energy_to_power) return; // if watts display then the first graph value will be zero. We skip that.

            // Depending on the charting library the object has to be reformatted
            // First we check if structure is initialized
            if (metrics[metric_name].series[detail_name] == undefined) {
                metrics[metric_name].series[detail_name] = { name: detail_name, data: [] }
            }

            metrics[metric_name].series[detail_name]['data'].push([time_in_ms, value]);

        })
    } catch (err) {
        alert(err)
        alert(metric_name)
    }

    const t1 = performance.now();
    console.log(`buildTimelineMetrics Took ${t1 - t0} milliseconds.`);
    return metrics;
}

const displayTimelineCharts = async (metrics, notes) => {

    const note_positions = [
        'insideStartTop',
        'insideEndBottom'
        ];
    const chart_instances = [];
    const t0 = performance.now();

    let markline = {};
    if(localStorage.getItem('time_series_avg') === 'true') {
        markline = {
                    precision: 4, // generally annoying that precision is by default 2. Wrong AVG if values are smaller than 0.001 and no autoscaling!
                    data: [ {type: "average",label: {formatter: "AVG\n(selection):\n{c}"}}]
        }
    }

    for (const metric_name in metrics) {

        const element = createChartContainer("#chart-container", `${getPretty(metric_name, 'clean_name')} via ${getPretty(metric_name, 'source')} <i data-tooltip="${getPretty(metric_name, 'explanation')}" data-position="bottom center" data-inverted><i class="question circle icon link"></i></i>`);

        let legend = [];
        let series = [];

        for (const detail_name in metrics[metric_name].series) {
            legend.push(detail_name)
            series.push({
                name: detail_name,
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: {},
                data: metrics[metric_name].series[detail_name].data,
                markLine: markline,
            });
        }
        // now we add all notes to every chart
        legend.push('Notes')
        let notes_labels = [];
        let inner_counter = 0;
        if (notes != null) {
            notes.forEach(note => {
                notes_labels.push({xAxis: note[3]/1000, label: {formatter: note[2], position: note_positions[inner_counter%2]}})
                inner_counter++;
            });
        }

        series.push({
            name: "Notes",
            type: 'line',
            smooth: true,
            symbol: 'none',
            areaStyle: {},
            data: [],
            markLine: { data: notes_labels}
        });

        const chart_instance = echarts.init(element);
        let options = getLineBarChartOptions(null, legend, series, 'Time', metrics[metric_name].converted_unit);
        chart_instance.setOption(options);
        chart_instances.push(chart_instance);

    }

    const t1 = performance.now();
    console.log(`buildTimelineCharts took ${t1 - t0} milliseconds.`);

    window.onresize = function() { // set callback when ever the user changes the viewport
        chart_instances.forEach(chart_instance => {
            chart_instance.resize();
        })
    }

    document.querySelector('#api-loader').remove();

    // after all charts instances have been placed
    // the flexboxes might have rearranged. We need to trigger resize
    setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);

}

const renderBadges = async (url_params, phase_stats) => {
    if (phase_stats == null) return;

    const phase_stats_keys = Object.keys(phase_stats);


    const badge_container = document.querySelector('#run-badges')

    phase_stats_keys.forEach(metric_name => {
        if (phase_stats[metric_name].type != 'TOTAL') return; // skip averaged metrics

        badge_container.innerHTML += `
            <div class="inline field">
                <a href="${METRICS_URL}/stats.html?id=${url_params['id']}">
                    <img src="${API_URL}/v1/badge/single/${url_params['id']}?metric=${metric_name}" loading="lazy">
                </a>
                <a class="copy-badge"><i class="copy icon"></i></a>
                <div class="ui left pointing blue basic label">
                    ${METRIC_MAPPINGS[metric_name]['explanation']}
                </div>
            </div>
            <hr class="ui divider"></hr>`;

    })
    document.querySelectorAll(".copy-badge").forEach(el => {
        el.addEventListener('click', copyToClipboard)
    })
}

const fetchAndFillPhaseStatsData = async (url_params) => {

    let phase_stats = null;
    try {
        phase_stats = await makeAPICall('/v1/phase_stats/single/' + url_params['id'])
    } catch (err) {
        showNotification('Could not get phase_stats data from API', err);
        return
    }


    buildPhaseTabs(phase_stats.data)

    document.querySelectorAll('.ui.steps.phases .step, .runtime-step').forEach(node => node.addEventListener('click', el => {
            const phase = el.currentTarget.getAttribute('data-tab');
            renderCompareChartsForPhase(phase_stats.data, phase);
        })
    );

    renderCompareChartsForPhase(phase_stats.data, getAndShowPhase());
    displayTotalChart(...buildTotalChartData(phase_stats.data));

    return phase_stats;
}

const fetchAndFillNetworkIntercepts = async (url_params) => {
    let network = null;
    try {
        network = await makeAPICall('/v1/network/' + url_params['id'])
    } catch (err) {
        showNotification('Could not get network intercepts data from API', err);
        return
    }

    if (network.data.length === 0) {
        document.querySelector("#network-divider").insertAdjacentHTML('afterEnd', '<p>No external network connections were detected.</p>')
    } else {
        for (const item of network.data) {
            const date = (new Date(Number(item[2]))).toLocaleString();
            document.querySelector("#network-intercepts").insertAdjacentHTML('beforeend', `<tr><td><strong>${date}</strong></td><td>${item[3]}</td><td>${item[4]}</td></tr>`)
        }
    }
}

const fetchAndFillOptimizationsData = async (url_params) => {

    let optimizations = null;
    try {
        optimizations = await makeAPICall('/v1/optimizations/' + url_params['id'])
    } catch (err) {
        showNotification('Could not get optimizations data from API', err);
        return
    }

    const optimizationTemplate = `
            <div class="content">
                <div class="header">{{header}}
                    <span class="right floated time">
                        <div class="ui label"><i class="{{subsystem_icon}} icon"></i>{{subsystem}}</div>
                        <div class="ui {{label_colour}} label">{{label}}</div>
                    </span>
                </div>
                <div class="description">
                    <p>{{description}}</p>
                </div>
                <div class="extra content">
                    <span class="right floated time">
                    {{link}}
                    </span>
                </div>
            </div>
    `;
    const container = document.getElementById("optimizationsContainer");

    optimizations.data.forEach(optimization => {
        let optimizationHTML = optimizationTemplate
            .replace("{{header}}", optimization[0])
            .replace("{{label}}", optimization[1])
            .replace("{{label_colour}}", optimization[2])
            .replace("{{description}}", optimization[5])
            .replace("{{subsystem}}", optimization[3])
            .replace("{{subsystem_icon}}", optimization[4])

        if (optimization[6]){
            optimizationHTML = optimizationHTML.replace("{{link}}", `
            <a class="ui mini icon primary basic button" href="${optimization[6]}">
                <i class="angle right icon"></i>
            </a>`);
        }else{
            optimizationHTML = optimizationHTML.replace("{{link}}", "");
        }

        const optimizationElement = document.createElement("div");
        optimizationElement.classList.add("ui", "horizontal", "fluid", "card");
        optimizationElement.innerHTML = optimizationHTML;
        container.appendChild(optimizationElement);

    });

    $('#optimization_count').html(optimizations.data.length)
}

const fetchAndFillAIData = async (url_params) => {

    if (ACTIVATE_AI_OPTIMISATIONS !== true) return;

    let ai_data = null;
    try {
        ai_data = await makeAPICall('/v1/ai/' + url_params['id'])
    } catch (err) {
        // Do nothing as ai data will be empty most of the time
        return
    }

    ai_data.sort((a, b) => a.rating - b.rating);

    const stats = {
        'green':0,
        'yellow':0,
        'red':0
    };

    ai_data.forEach(d => {
        if (d.rating > 75) {
            d.color = "green";
        } else if (d.rating > 35) {
            d.color = "yellow";
        } else if (d.rating > 0) {
            d.color = "red";
        } else {
            console.log('Massive error. We need to report this');
            return;
        }

        stats[d.color] += 1;
    });

    const progressBar = `
        <div id="ai_progress" class="ui multiple progress" data-value="${stats['red']},${stats['yellow']},${stats['green']}" data-total=${ai_data.length}>
            <div class="red bar"></div>
            <div class="yellow bar"></div>
            <div class="green bar"></div>
        </div>
        `

    const aiTemplate = `
        <div class="title">
            <div class="ui {{color}} label">{{rating}}</div> {{filename}}:{{function_name}} <i class="dropdown icon"></i>
        </div>
        <div class="content">
            <h4 class="ui horizontal divider header">
            <i class="barcode icon"></i>
                Your code
            </h4>
            <pre>{{code}}</pre>
            <h4 class="ui horizontal divider header">
            <i class="brain icon"></i>
                {{model}}
            </h4>
            <p>{{ret_val}}</p>
            <button class="ui primary basic button copy-button">Improve this with AI</button>
        </div>
    `;
    const ai_container = document.getElementById("ai-container");

    ai_container.innerHTML = progressBar;

    ai_data.forEach(d => {
        let optimizationHTML = aiTemplate
            .replace("{{function_name}}", d.name)
            .replace("{{rating}}", d.rating)
            .replace("{{filename}}", d.filename)
            .replace("{{code}}", d.code)
            .replace("{{model}}", d.model)
            .replace("{{color}}", d.color)
            .replace("{{ret_val}}", (d.ret_val || '').replace(/\n/g, '<br>'))

        const optimizationElement = document.createElement("div");
        optimizationElement.classList.add("ui", "styled","fluid", "accordion");
        optimizationElement.innerHTML = optimizationHTML;
        ai_container.appendChild(optimizationElement);

    });

    $('#ai_progress').progress();

    $('body').on('click', '.copy-button', function() {
        var code = $(this).closest('.content').find('pre').text();
        copyTextToClipboard('You are a world class programmer. Please improve:' + code); // TODO: Refactor to use central function in main.js
        showNotification('Code copied', 'The code has been copied to the clipboard.')
    });

}

function copyTextToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
            console.log("Text successfully copied to clipboard");
        }, function(err) {
            console.error("Failed to copy text: ", err);
        });
    } else {
        // Fallback for older browsers
        var textArea = $('<textarea>');
        $('body').append(textArea);
        textArea.val(text).select();
        document.execCommand('copy');
        textArea.remove();
    }
}

const fetchTimelineData = async (url_params) => {
    document.querySelector('#api-loader').style.display = '';
    document.querySelector('#loader-question').remove();

    let measurements = null;
    try {
        measurements = await makeAPICall('/v1/measurements/single/' + url_params['id'])
    } catch (err) {
        showNotification('Could not get stats data from API', err);
    }
    return measurements?.data;

}

const fetchTimelineNotes = async (url_params) => {
    let notes = null;
    try {
        notes = await makeAPICall('/v1/notes/' + url_params['id'])
    } catch (err) {
        showNotification('Could not get notes data from API', err);
    }
    return notes?.data;
}


/* Chart starting code*/
$(document).ready( (e) => {
    (async () => {

        $('.ui.secondary.menu .item').tab({childrenOnly: true, context: '.run-data-container'}); // activate tabs for run data
        $('.ui.accordion').accordion();

        let url_params = getURLParams();

        if(url_params['id'] == null || url_params['id'] == '' || url_params['id'] == 'null') {
            showNotification('No run id', 'ID parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }

        fetchAndFillRunData(url_params);
        fetchAndFillNetworkIntercepts(url_params);
        fetchAndFillOptimizationsData(url_params);
        fetchAndFillAIData(url_params);

        (async () => { // since we need to wait for fetchAndFillPhaseStatsData we wrap in async so later calls cann already proceed
            const phase_stats = await fetchAndFillPhaseStatsData(url_params);
            renderBadges(url_params, phase_stats?.data?.data['[RUNTIME]']);
        })();


        if (localStorage.getItem('fetch_time_series') === 'true') {
            const [timeline_data, timeline_notes] = await Promise.all([
                fetchTimelineData(url_params),
                fetchTimelineNotes(url_params)
            ]);
            if (timeline_data == null) {
                document.querySelector('#api-loader').remove()
                document.querySelector('#message-chart-load-failure').style.display = '';
                return
            }
            const timeline_chart_data = await buildTimelineChartData(timeline_data);
            displayTimelineCharts(timeline_chart_data, timeline_notes);
        } else {
            document.querySelector('#fetch-time-series').addEventListener('click', async () => {
                const [timeline_data, timeline_notes] = await Promise.all([
                    fetchTimelineData(url_params),
                    fetchTimelineNotes(url_params)
                ]);

                if (timeline_data == null) {
                    document.querySelector('#api-loader').remove()
                    document.querySelector('#message-chart-load-failure').style.display = '';
                    return
                }
                const timeline_chart_data = await buildTimelineChartData(timeline_data);
                displayTimelineCharts(timeline_chart_data, timeline_notes);


            });
        }
    })();
});

