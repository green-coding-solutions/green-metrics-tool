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

const fillProjectData = (project_data, key = null) => {


    for (item in project_data) {
        if (item == 'machine_specs') {
            fillProjectTab('#machine-specs', project_data[item]); // recurse
        } else if(item == 'usage_scenario') {
            document.querySelector("#usage-scenario").insertAdjacentHTML('beforeend', `<pre class="usage-scenario">${json2yaml(project_data?.[item])}</pre>`)
        } else if(item == 'logs') {
            document.querySelector("#logs").insertAdjacentHTML('beforeend', `<pre>${project_data?.[item]}</pre>`)
        } else if(item == 'measurement_config') {
            fillProjectTab('#measurement-config', project_data[item]); // recurse
        } else if(item == 'phases' || item == 'id') {
            // skip
        }  else if(item == 'commit_hash') {
            if (project_data?.[item] == null) continue; // some old projects did not save it
            let commit_link = buildCommitLink(project_data);
            document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td><a href="${commit_link}" target="_blank">${project_data?.[item]}</a></td></tr>`)
        } else if(item == 'name') {
            document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${project_data?.[item]}</td></tr>`)
        } else if(item == 'uri') {
            let entry = project_data?.[item];
            if(project_data?.[item].indexOf('http') === 0) entry = `<a href="${project_data?.[item]}">${project_data?.[item]}</a>`;
            document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${entry}</td></tr>`);
        } else {
            document.querySelector('#project-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>${item}</strong></td><td>${project_data?.[item]}</td></tr>`)
        }
    }

    // create new custom field
    // timestamp is in microseconds, therefore divide by 10**6
    const measurement_duration_in_s = (project_data.end_measurement - project_data.start_measurement) / 1000000
    document.querySelector('#project-data-accordion').insertAdjacentHTML('beforeend', `<tr><td><strong>duration</strong></td><td>${measurement_duration_in_s} s</td></tr>`)


    $('.ui.secondary.menu .item').tab({childrenOnly: true, context: '.project-data-container'}); // activate tabs for project data
    $('.ui.accordion').accordion();

    if (project_data.invalid_project) {
        showNotification('Project measurement has been marked as invalid', project_data.invalid_project);
        document.body.classList.add("invalidated-measurement")
    }

}

const buildCommitLink = (project_data) => {
    let commit_link;
    commit_link = project_data['uri'].endsWith('.git') ? project_data['uri'].slice(0, -4) : project_data['uri']
    if (project_data['uri'].includes('github')) {
        commit_link = commit_link + '/tree/' + project_data['commit_hash']
    }
    else if (project_data['uri'].includes('gitlab')) {
        commit_link = commit_link + '/-/tree/' + project_data ['commit_hash']
    }
    return commit_link;
}

const fillProjectTab = (selector, data, parent = '') => {
    for (item in data) {
        if(typeof data[item] == 'object')
            fillProjectTab(selector, data[item], `${item}.`)
        else
            document.querySelector(selector).insertAdjacentHTML('beforeend', `<tr><td><strong>${parent}${item}</strong></td><td>${data?.[item]}</td></tr>`)

    }
}


const getTimelineMetrics = (measurements_data, start_measurement, end_measurement) => {
    const metrics = {}
    const t0 = performance.now();

    let display_in_watts = localStorage.getItem('display_in_watts');
    if(display_in_watts == 'true') display_in_watts = true;
    else display_in_watts = false;

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

            if(display_in_watts && metrics[metric_name].unit == 'J') {
                value = value/(time_after-time_before); // convert Joules to Watts by dividing through the time difference of two measurements
                metrics[metric_name].converted_unit = 'W';
            } else if(!display_in_watts && metrics[metric_name].unit == 'W') {
                value = value*(time_after-time_before); // convert Joules to Watts by dividing through the time difference of two measurements
                metrics[metric_name].converted_unit = 'J';
            }
            time_before = time_after;

            if(metric_changed && display_in_watts) return; // if watts display then the first graph value will be zero. We skip that.

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
    console.log(`getTimelineMetrics Took ${t1 - t0} milliseconds.`);
    return metrics;
}

const displayTimelineCharts = (metrics, notes) => {

    const note_positions = [
        'insideStartTop',
        'insideEndBottom'
        ];
    const chart_instances = [];
    const t0 = performance.now();

    for ( metric_name in metrics) {

        const element = createChartContainer("#chart-container", `${metric_name} [${metrics[metric_name].converted_unit}]`);

        let legend = [];
        let series = [];

        for (detail_name in metrics[metric_name].series) {
            legend.push(detail_name)
            series.push({
                name: detail_name,
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: {},
                data: metrics[metric_name].series[detail_name].data,
                markLine: {
                    precision: 4, // generally annoying that precision is by default 2. Wrong AVG if values are smaller than 0.001 and no autoscaling!
                    data: [ {type: "average",label: {formatter: "AVG:\n{c}"}}]
                }
            });
        }
        // now we add all notes to every chart
        legend.push('Notes')
        let notes_labels = [];
        let inner_counter = 0;
        notes.forEach(note => {
            notes_labels.push({xAxis: note[3]/1000, label: {formatter: note[2], position: note_positions[inner_counter%2]}})
            inner_counter++;
        });

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
        let options = getLineBarChartOptions(legend, series);
        chart_instance.setOption(options);
        chart_instances.push(chart_instance);

    }

    const t1 = performance.now();
    console.log(`DisplayTimelineCharts took ${t1 - t0} milliseconds.`);

    window.onresize = function() { // set callback when ever the user changes the viewport
        chart_instances.forEach(chart_instance => {
            chart_instance.resize();
        })
    }

    document.querySelector('#api-loader').remove();
}



async function makeAPICalls(url_params) {

    try {
        var project_data = await makeAPICall('/v1/project/' + url_params.get('id'))
    } catch (err) {
        showNotification('Could not get project data from API', err);
    }

    try {
        var measurement_data = await makeAPICall('/v1/measurements/single/' + url_params.get('id'))
    } catch (err) {
        showNotification('Could not get stats data from API', err);
    }

    try {
        var notes_data = await makeAPICall('/v1/notes/' + url_params.get('id'))
    } catch (err) {
        showNotification('Could not get notes data from API', err);
    }

    try {
        var network_data = await makeAPICall('/v1/network/' + url_params.get('id'))
    } catch (err) {
        showNotification('Could not get network intercepts data from API', err);
    }

    try {
        var phase_stats_data = await makeAPICall('/v1/phase_stats/single/' + url_params.get('id'))
    } catch (err) {
        showNotification('Could not get phase_stats data from API', err);
    }

    return [project_data?.data, measurement_data?.data, notes_data?.data, phase_stats_data?.data, network_data?.data];
}

const renderBadges = (url_params) => {

    document.querySelectorAll("#badges span.energy-badge-container").forEach(el => {
        const link_node = document.createElement("a")
        const img_node = document.createElement("img")
        link_node.href = `${METRICS_URL}/stats.html?id=${url_params.get('id')}`
        img_node.src = `${API_URL}/v1/badge/single/${url_params.get('id')}?metric=${el.attributes['data-metric'].value}`
        link_node.appendChild(img_node)
        el.appendChild(link_node)
    })
    document.querySelectorAll(".copy-badge").forEach(el => {
        el.addEventListener('click', copyToClipboard)
    })
}

const displayNetworkIntercepts = (network_data) => {
    for (item of network_data) {
        date = new Date(Number(item[2]));
        date = date.toLocaleString();
        document.querySelector("#network-intercepts").insertAdjacentHTML('beforeend', `<tr><td><strong>${date}</strong></td><td>${item[3]}</td><td>${item[4]}</td></tr>`)
    }
}

const getURLParams = () => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))

    if(url_params.get('id') == null || url_params.get('id') == '' || url_params.get('id') == 'null') {
        showNotification('No project id', 'ID parameter in URL is empty or not present. Did you follow a correct URL?');
        throw "Error";
    }
    return url_params;
}


/* Chart starting code*/
$(document).ready( (e) => {
    (async () => {

        let url_params = getURLParams();
        if(url_params.get('id') == null || url_params.get('id') == '' || url_params.get('id') == 'null') {
            showNotification('No project id', 'ID parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }

        let [project_data, measurements_data, notes_data, phase_stats_data, network_data] = await makeAPICalls(url_params);

        if (project_data == undefined) return;

        renderBadges(url_params);

        fillProjectData(project_data);

        if(phase_stats_data != null) {
            setupPhaseTabs(phase_stats_data, false, true)
            displayComparisonMetrics(phase_stats_data, phase_stats_data.comparison_case, false, true)
        }

        if (measurements_data == undefined) return;
        const metrics = getTimelineMetrics(measurements_data);

        if (notes_data == undefined) return;
        displayTimelineCharts(metrics, notes_data);

        displayNetworkIntercepts(network_data);

        // after all charts instances have been placed
        // the flexboxes might have rearranged. We need to trigger resize
        setTimeout(function(){console.log("Resize"); window.dispatchEvent(new Event('resize'))}, 500);
    })();
});

