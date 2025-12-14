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
    const run_data_accordion_node = document.querySelector('#run-data-accordion');

    for (const item in run_data) {
        if (item == 'machine_id') {
            run_data_accordion_node.insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td>${escapeString(run_data[item])} (${escapeString(GMT_MACHINES[run_data[item]] || run_data[item])})</td></tr>`);
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
                    container.insertAdjacentHTML('beforeend', `<li><span class="ui label">${escapeString(key)}=${escapeString(run_data[item][key])}</span></li>`)
                }
            } else {
                document.querySelector("#usage-scenario-variables").insertAdjacentHTML('beforeend', `N/A`)
            }
        } else if(item == 'containers') {
            if (run_data[item] == null) continue; // can be null
            const containers_node = document.querySelector('#containers');
            for (const ctr_name in run_data[item]) {
                containers_node.insertAdjacentHTML('beforeend', `
                    <div id="container-${escapeString(ctr_name)}" class="ui segment">
                        <h3>${escapeString(ctr_name)}</h3>
                        <p>CPUS: ${escapeString(run_data[item][ctr_name].cpus)}</p>
                        <p>Memory Limit: ${escapeString(run_data[item][ctr_name].mem_limit)} (${Math.round(run_data[item][ctr_name].mem_limit/1024**2)} MB)</p>
                        <p>Image: ${escapeString(run_data?.container_dependencies?.[ctr_name]?.['source']?.['image'])}</p>
                        <p>Hash: ${escapeString(run_data?.container_dependencies?.[ctr_name]?.['source']?.['hash'])}</p>
                        <h4>Dependencies</h4>
                        ${renderUsageScenarioDependencies(ctr_name, run_data?.container_dependencies)}
                </div>`);
            }
            document.querySelectorAll('.ui.accordion.container-dependencies').forEach(accordion => {
                $(accordion).accordion();
            });



        } else if(item == 'logs') {
            const logsData = run_data[item];
            if (logsData === null) {
                // Display simple message indicating no output was produced
                document.querySelector("#logs").innerHTML = '<pre>Run did not produce any logs to be captured</pre>';
            } else if (typeof logsData === 'object' && logsData !== null) {
                // Handle JSON structure logs
                // Check first if any logs have type 'legacy' - if so, render as simple text instead of structured interface
                const hasLegacyLogs = Object.values(logsData).some(containerLogs =>
                    Array.isArray(containerLogs) && containerLogs.some(log => log.type === 'legacy')
                );
                if (!hasLegacyLogs) {
                    renderLogsInterface(logsData);
                } else {
                    renderLegacyLogsFromJson(logsData);
                }
            } else {
                // Handle legacy plain text logs (pre-JSON structure)
                displayLegacyLogs(run_data[item]);
            }
        } else if(item == 'measurement_config') {
            fillRunTab('#measurement-config', run_data[item]); // recurse
        } else if(item == 'id' || item == 'phases') {
            // skip
        }  else if(item == 'commit_hash') {
            if (run_data[item] == null) continue; // some old runs did not save it
            let commit_link = buildCommitLink(run_data);
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td><a href="${commit_link}" target="_blank">${escapeString(run_data[item])}</a></td></tr>`)
        } else if(item == 'name' || item == 'filename' || item == 'branch') {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td>${escapeString(run_data[item])}</td></tr>`)
        } else if(item == 'failed' && run_data[item] == true) {
            const failedContainer = document.querySelector('#run-failed');
            failedContainer.classList.remove('hidden');
            const rerunButton = document.createElement('button');
            rerunButton.className = 'ui tiny primary button';
            rerunButton.textContent = 'Re Submit';
            rerunButton.style.marginLeft = '1em';

            rerunButton.addEventListener('click', () => {
                const params = new URLSearchParams();
                if (run_data.name) params.set('name', run_data.name);
                if (run_data.uri) params.set('repo_url', run_data.uri);
                if (run_data.filename) params.set('filename', run_data.filename);
                if (run_data.branch) params.set('branch', run_data.branch);
                if (run_data.machine_id) params.set('machine_id', run_data.machine_id);
                if (run_data.schedule_mode) params.set('schedule_mode', run_data.schedule_mode);
                if (run_data.usage_scenario_variables && Object.keys(run_data.usage_scenario_variables).length > 0) {
                    params.set('usage_scenario_variables', JSON.stringify(run_data.usage_scenario_variables));
                }
                
                window.open(`request.html?${params.toString()}`, '_blank');
            });
            failedContainer.appendChild(rerunButton);
        } else if(item == 'start_measurement' || item == 'end_measurement') {
            run_data_accordion_node.insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td title="${escapeString(run_data[item])}">${new Date(run_data[item] / 1e3)}</td></tr>`)
        } else if(item == 'created_at' ) {
            run_data_accordion_node.insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td title="${escapeString(run_data[item])}">${new Date(run_data[item])}</td></tr>`)
        } else if(item == 'gmt_hash') {
            run_data_accordion_node.insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td><a href="https://github.com/green-coding-solutions/green-metrics-tool/commit/${run_data[item]}">${escapeString(run_data[item])}</a></td></tr>`);
        } else if(item == 'uri') {
            const uri = run_data[item];
            let uriDisplay;
            if(uri.startsWith('http')) {
                // URI is safe for href attribute: validated to have http/https protocol prevents XSS
                // HTML escaping not needed here and would break URLs (e.g., & would become &amp;)
                uriDisplay = `<a href="${uri}">${escapeString(uri)}</a>`;
            } else {
                uriDisplay = escapeString(uri);
            }
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td>${uriDisplay}</td></tr>`);
        } else if(item == 'note') {
            const note = run_data[item].trim();
            if (note !== '') {
                // no need to escape here as .value and .innerText will not execute HTML / JS
                document.querySelector('textarea[name=note]').value = note;
                document.querySelector('#run-note-text').innerText = note;
                document.querySelector('#run-note').classList.remove('hidden')
            }
        } else if(item == 'archived') {
            const archive_run_button = document.querySelector('#archive-run');
            const unarchive_run_button = document.querySelector('#unarchive-run');

            if (run_data[item] === true) {
                archive_run_button.classList.add('hidden');
                unarchive_run_button.classList.remove('hidden');
            }

            archive_run_button.addEventListener('click', async () => {
                await makeAPICall(`/v1/run/${url_params['id']}`, {archived: true}, false, true);
                archive_run_button.classList.add('hidden');
                unarchive_run_button.classList.remove('hidden');
                showNotification('Run Archived!', '', 'success')
            })
            unarchive_run_button.addEventListener('click', async () => {
                await makeAPICall(`/v1/run/${url_params['id']}`, {archived: false}, false, true);
                archive_run_button.classList.remove('hidden');
                unarchive_run_button.classList.add('hidden');
                showNotification('Run Unarchived!', '', 'success')
            })

        } else if(item == 'public') {
            const public_button = document.querySelector('#make-run-public');
            const non_public_button = document.querySelector('#make-run-non-public');

            if (run_data[item] === true) {
                public_button.classList.add('hidden');
                non_public_button.classList.remove('hidden');
            }

            public_button.addEventListener('click', async () => {
                await makeAPICall(`/v1/run/${url_params['id']}`, {public: true}, false, true);
                public_button.classList.add('hidden');
                non_public_button.classList.remove('hidden');
                showNotification('Run Made Public!', '', 'success')
            })
            non_public_button.addEventListener('click', async () => {
                await makeAPICall(`/v1/run/${url_params['id']}`, {public: false}, false, true);
                public_button.classList.remove('hidden');
                non_public_button.classList.add('hidden');
                showNotification('Run Made Non-Public!', '', 'success')
            })

        } else {
            run_data_accordion_node.insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(item)}</strong></td><td>${escapeString(run_data[item])}</td></tr>`)
        }
    }

    document.querySelector('#save-note').addEventListener('click', async () => {
        const note_text = document.querySelector('textarea[name=note]').value;
        await makeAPICall(`/v1/run/${url_params['id']}`, {note: note_text}, false, true);
        showNotification('Note saved!', '', 'success')
    });

    // create new custom field
    // timestamp is in microseconds, therefore divide by 10**6
    const measurement_duration_in_s = (run_data.end_measurement - run_data.start_measurement) / 1e6
    const measurement_duration_display = (measurement_duration_in_s > 60) ? `${numberFormatter.format(measurement_duration_in_s / 60)} min` : `${numberFormatter.format(measurement_duration_in_s)} s`

    run_data_accordion_node.insertAdjacentHTML('beforeend', `<tr><td><strong>duration</strong></td><td title="${measurement_duration_in_s} seconds">${measurement_duration_display}</td></tr>`)

    // warnings will be fetched separately

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
    const node = document.querySelector(selector);
    for (const item in data) {

        if(data[item] != null && typeof data[item] == 'object') {
            if (parent == '') {
                node.insertAdjacentHTML('beforeend', `<tr><td><strong><h2>${escapeString(item)}</h2></strong></td><td></td></tr>`)
            }
            fillRunTab(selector, data[item], `${item}.`)
        } else {
            node.insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(parent)}${escapeString(item)}</strong></td><td>${escapeString(data[item])}</td></tr>`)
        }
    }
}

const displayLegacyLogs = (logData) => {
    const logsElement = document.querySelector("#logs");
    logsElement.innerHTML = `<pre>${escapeString(logData)}</pre>`;
};

const renderLegacyLogsFromJson = (logsData) => {
    const legacyLogTemplate = `
        <div class="ui segment">
            <h4 class="ui header">{{containerName}}</h4>
            <pre>{{stdout}}</pre>
        </div>
    `;

    const logsElement = document.querySelector("#logs");
    let contentHTML = '';

    // actually, in the legacy case there is only one 'container' called "unified (legacy)"
    // but to be on the safe side, still use loops for all lists in the JSON structure
    Object.keys(logsData).forEach(containerName => {
        const containerLogs = logsData[containerName];
        containerLogs.forEach(logEntry => {
            if (logEntry.stdout) {
                contentHTML += legacyLogTemplate
                    .replace('{{containerName}}', escapeString(containerName))
                    .replace('{{stdout}}', escapeString(logEntry.stdout));
            }
        });
    });

    logsElement.innerHTML = contentHTML;
};

const renderLogsInterface = (logsData) => {
    const containerTemplate = `
        <div class="title">
            <i class="dropdown icon"></i><i class="server icon"></i> {{containerName}}
            <div class="ui mini label">{{logCount}} log{{logPlural}}</div>
        </div>
        <div class="content">{{content}}</div>
    `;

    const logCardTemplate = `
        <div class="ui card fluid">
            {{metadataContent}}
            {{commandContent}}
            {{stdoutContent}}
            {{stderrContent}}
        </div>
    `;

    const metadataTemplate = `
        <div class="content">
            <div class="header">
                <div class="ui small labels">
                    {{typeLabel}}
                    {{flowLabel}}
                    {{classLabel}}
                    {{operationLabel}}
                    {{phaseLabel}}
                    {{idLabel}}
                </div>
            </div>
        </div>
    `;

    const commandTemplate = `
        <div class="content">
            <h5 class="ui header"><i class="terminal icon"></i> Command</h5>
            <div class="ui segment">
                <code>{{command}}</code>
            </div>
        </div>
    `;

    const stdoutTemplate = `
        <div class="content">
            <h5 class="ui header"><i class="file text outline icon"></i> Standard Output</h5>
            <div class="ui segment stdout">
                <div>{{stdout}}</div>
            </div>
        </div>
    `;

    const stderrTemplate = `
        <div class="content">
            <h5 class="ui header"><i class="exclamation triangle icon"></i> Standard Error</h5>
            <div class="ui segment stderr">
                <div>{{stderr}}</div>
            </div>
        </div>
    `;

    const logsElement = document.querySelector("#logs");
    let accordionHTML = '<div class="ui styled accordion">';

    const containerNames = Object.keys(logsData);
    // Display [SYSTEM] logs first
    const systemIndex = containerNames.indexOf('[SYSTEM]');
    if (systemIndex > -1) {
        containerNames.splice(systemIndex, 1);
        containerNames.unshift('[SYSTEM]');
    }

    containerNames.forEach(containerName => {
        const containerLogs = logsData[containerName];

        let contentHTML = '';
        containerLogs.forEach(logEntry => {
            let typeIcon, typeTooltip;
            switch (logEntry.type) {
                case 'container_execution':
                    typeIcon = 'cog';
                    typeTooltip = 'Logs from the entire container execution process';
                    break;
                case 'setup_commands':
                    typeIcon = 'wrench';
                    typeTooltip = 'Logs from setup commands before flow execution';
                    break;
                case 'flow_command':
                    typeIcon = 'play';
                    typeTooltip = 'Logs from a specific flow execution';
                    break;
                case 'network_stats':
                    typeIcon = 'wifi';
                    typeTooltip = 'Network connection statistics from tcpdump';
                    break;
                case 'exception':
                    typeIcon = 'exclamation triangle';
                    typeTooltip = 'An error occurred during execution';
                    break;
                default:
                    typeIcon = 'question';
                    typeTooltip = 'Logs from an unknown or custom execution type';
                    break;
            }

            // Make the type name more visually appealing by replacing underscores with spaces and capitalising the first letter of each word
            const typeTitle = escapeString(logEntry.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()));
            const typeLabel = `<div class="ui purple label" data-tooltip="${typeTooltip}" data-position="top center"><i class="${typeIcon} icon"></i> ${typeTitle}</div>`;

            const phaseLabel = logEntry.phase ?
                `<div class="ui blue label" data-tooltip="Execution phase when this command was run" data-position="top center"><i class="clock icon"></i> ${escapeString(logEntry.phase)}</div>` : '';

            const flowLabel = logEntry.flow ?
                `<div class="ui green label" data-tooltip="Flow this command belongs to" data-position="top center"><i class="sitemap icon"></i> ${escapeString(logEntry.flow)}</div>` : '';

            const idLabel = `<div class="ui label" data-tooltip="Unique identifier for this log entry" data-position="top center"><i class="hashtag icon"></i> ID: ${escapeString(logEntry.id)}</div>`;

            const stdoutContent = logEntry.stdout ?
                stdoutTemplate.replace('{{stdout}}', escapeString(logEntry.stdout)) : '';

            const stderrContent = logEntry.stderr ?
                stderrTemplate.replace('{{stderr}}', escapeString(logEntry.stderr)) : '';

            // Show different information if the type is exception
            let operationLabel = '';
            let classLabel = '';
            if (logEntry.type === 'exception') {
                let operationTooltip;
                switch (logEntry.cmd) {
                    case 'run_scenario':
                        operationTooltip = 'Exception occurred during main scenario execution runtime';
                        break;
                    case 'post_process':
                        operationTooltip = 'Exception occurred during cleanup and post-processing phase';
                        break;
                    default:
                        operationTooltip = `Exception occurred during '${logEntry.cmd}' operation`;
                }
                // Make the operation name more visually appealing by replacing underscores with spaces and capitalising the first letter of each word
                const operationTitle = escapeString(logEntry.cmd.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()));
                operationLabel = `<div class="ui orange label" data-tooltip="${operationTooltip}" data-position="top center"><i class="cogs icon"></i> ${operationTitle}</div>`;

                if (logEntry.exception_class) {
                    classLabel = `<div class="ui red label" data-tooltip="Exception class type" data-position="top center"><i class="exclamation triangle icon"></i> ${escapeString(logEntry.exception_class)}</div>`;
                }
            }

            const metadataContent = metadataTemplate
                .replace('{{flowLabel}}', flowLabel)
                .replace('{{typeLabel}}', typeLabel)
                .replace('{{operationLabel}}', operationLabel)
                .replace('{{classLabel}}', classLabel)
                .replace('{{phaseLabel}}', phaseLabel)
                .replace('{{idLabel}}', idLabel);

            // For exceptions or empty/null commands, don't show the command section
            const commandContent = (logEntry.type === 'exception' || !logEntry.cmd) ? '' :
                commandTemplate.replace('{{command}}', escapeString(logEntry.cmd));

                contentHTML += logCardTemplate
                .replace('{{metadataContent}}', metadataContent)
                .replace('{{commandContent}}', commandContent)
                .replace('{{stdoutContent}}', stdoutContent)
                .replace('{{stderrContent}}', stderrContent);
        });

        accordionHTML += containerTemplate
            .replace('{{containerName}}', escapeString(containerName))
            .replace('{{logCount}}', containerLogs.length)
            .replace('{{logPlural}}', containerLogs.length === 1 ? '' : 's')
            .replace('{{content}}', contentHTML);
    });

    accordionHTML += '</div>';
    logsElement.innerHTML = accordionHTML;
    $('.ui.accordion').accordion();
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

const wrapNoteText = (text, maxLength = 80) => {
    if (text.length <= maxLength) return text;

    const lines = [];
    let currentLine = '';
    const breakChars = [' ', '/', ':', '-', '_'];

    for (const char of text) {
        currentLine += char;

        if (currentLine.length >= maxLength) {
            const breakIndex = currentLine.split('').findLastIndex(c => breakChars.includes(c));

            if (breakIndex > maxLength * 0.5) {
                const breakChar = currentLine[breakIndex];
                const endIndex = breakChar === ' ' ? breakIndex : breakIndex + 1;
                lines.push(currentLine.substring(0, endIndex));
                currentLine = currentLine.substring(breakIndex + 1);
            } else {
                lines.push(currentLine.substring(0, maxLength));
                currentLine = currentLine.substring(maxLength);
            }
        }
    }

    if (currentLine) lines.push(currentLine);
    return lines.join('\n');
};

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
                notes_labels.push({xAxis: note[3]/1000, label: {formatter: wrapNoteText(note[2]), position: note_positions[inner_counter%2]}})
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
                    <img src="${API_URL}/v1/badge/single/${url_params['id']}?metric=${encodeURIComponent(metric_name)}" loading="lazy" onerror="this.parentNode.parentNode.remove(); console.log('Could not render ${metric_name} badge - Likely due to non public visibility of the run.')">
                </a>
                <a class="copy-badge"><i class="copy icon"></i></a>
                <div class="ui left pointing blue basic label">
                    ${escapeString(METRIC_MAPPINGS[metric_name]['explanation'])}
                </div>
                <hr class="ui divider"></hr>
            </div>`;


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
        if (err instanceof APIEmptyResponse204) {
            console.log('No network intercepts present in API response. Skipping error as this is allowed case.')
        } else {
            showNotification('Could not get network intercepts data from API', err);
        }
        return
    }

    if (network.data.length === 0) {
        document.querySelector("#network-divider").insertAdjacentHTML('afterEnd', '<p>No external network connections were detected.</p>')
    } else {
        const node = document.querySelector("#network-intercepts");
        for (const item of network.data) {
            const date = (new Date(Number(item[2]))).toLocaleString();
            node.insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(date)}</strong></td><td>${escapeString(item[3])}</td><td>${escapeString(item[4])}</td></tr>`)
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
            .replace("{{header}}", escapeString(optimization[0]))
            .replace("{{label}}", escapeString(optimization[1]))
            .replace("{{label_colour}}", escapeString(optimization[2]))
            .replace("{{description}}", escapeString(optimization[5]))
            .replace("{{subsystem}}", escapeString(optimization[3]))
            .replace("{{subsystem_icon}}", escapeString(optimization[4]))

        if (optimization[6]){
            optimizationHTML = optimizationHTML.replace("{{link}}", `
            <a class="ui mini icon primary basic button" href="${escapeString(optimization[6])}">
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
            .replace("{{function_name}}", escapeString(d.name))
            .replace("{{rating}}", escapeString(d.rating))
            .replace("{{filename}}", escapeString(d.filename))
            .replace("{{code}}", escapeString(d.code))
            .replace("{{model}}", escapeString(d.model))
            .replace("{{color}}", escapeString(d.color))
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
    document.querySelector('#api-loader').classList.remove('hidden');
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

const fetchAndFillWarnings = async (url_params) => {
    let warnings = null;
    try {
        warnings = await makeAPICall('/v1/warnings/' + url_params['id'])
    } catch (err) {
        if (err instanceof APIEmptyResponse204) {
            console.log('No warnings where present in API response. Skipping error as this is allowed case.')
        } else {
            showNotification('Could not get warnings data from API', err);
        }
        return;

    }

    if (!warnings || warnings?.data?.length === 0) return;

    const container = document.querySelector('#run-warnings');
    const ul = container.querySelector('ul');
    warnings.data.forEach(w => {
        ul.insertAdjacentHTML('beforeend', `<li>${escapeString(w[1])}</li>`);
    });
    container.classList.remove('hidden');
}



// Templates for usage scenario dependencies
const dependencies_templates = {
    scopeAccordion: `
        <div class="ui accordion container-dependencies">
            {{accordion_items}}
        </div>
    `,

    accordionItem: `
        <div class="title">
            <i class="dropdown icon"></i>
            {{scopeDisplayName}} Packages ({{totalDeps}} packages)
        </div>
        <div class="content">
            {{scopeMetadata}}
            {{depsTable}}
        </div>
    `,

    scopeMetadata: `
        <div>
            {{metadataContent}}
        </div>
    `,

    depsTable: `
        <table class="ui celled compact table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Version</th>
                    <th>Hash</th>
                </tr>
            </thead>
            <tbody>
                {{tableRows}}
            </tbody>
        </table>
    `,

    depsTableRow: `
        <tr>
            <td>{{depName}}</td>
            <td>{{version}}</td>
            <td><code title="{{fullHash}}">{{truncatedHash}}</code></td>
        </tr>
    `,

    noDepsMessage: `<div class="ui message">{{message}}</div>`
};

function renderUsageScenarioDependencies(container_name, dependency_data) {

    if (dependency_data == null || dependency_data?.[container_name] == null) {
        return '<em>No dependency information available</em>';
    }

    const container_dependencies = dependency_data[container_name];
    const container_data = container_dependencies['source'] || {};

    const package_managers = Object.keys(container_dependencies).filter(key => key !== 'source');

    let package_manager_content = '';

    if (package_managers.length > 0) {
        const accordion_items = buildPackageManagerAccordionItems(package_managers, container_dependencies);

        package_manager_content = dependencies_templates.scopeAccordion.replace('{{accordion_items}}', accordion_items);
    } else {
        package_manager_content = dependencies_templates.noDepsMessage.replace('{{message}}', '<em>No package dependencies found</em>');
    }

    return package_manager_content;

}

function buildSingleAccordionItem(packageManager, displayName, data) {
    const dependencies = data.dependencies || {};
    const dependenciesArray = Object.entries(dependencies).map(([name, pkgData]) => ({
        name: name,
        version: pkgData.version || 'N/A',
        type: packageManager,
        hash: pkgData.hash || 'N/A'
    }));
    const totalDeps = dependenciesArray.length;

    // Build metadata content
    let metadataContent = '';
    if (data.scope) {
        metadataContent += `<strong>Scope:</strong> ${escapeString(data.scope)}<br>`;
    }
    if (data.location) {
        metadataContent += `<strong>Location:</strong> ${escapeString(data.location)}<br>`;
    }
    if (data.hash) {
        metadataContent += `<strong>Hash:</strong> <code>${escapeString(data.hash)}</code><br>`;
    }

    const packageManagerMetadata = metadataContent ?
        dependencies_templates.scopeMetadata.replace('{{metadataContent}}', metadataContent) : '';

    let depsTable = '';
    if (totalDeps > 0) {
        const tableRows = buildDependencyTableRows(dependenciesArray);
        depsTable = dependencies_templates.depsTable.replace('{{tableRows}}', tableRows);
    } else {
        depsTable = dependencies_templates.noDepsMessage.replace('{{message}}', '<em>No dependencies found</em>');
    }

    return dependencies_templates.accordionItem
        .replace('{{scopeDisplayName}}', escapeString(displayName))
        .replace('{{totalDeps}}', totalDeps)
        .replace('{{scopeMetadata}}', packageManagerMetadata)
        .replace('{{depsTable}}', depsTable);
}

function buildPackageManagerAccordionItems(package_managers, container_dependencies) {
    let accordion_items = '';

    package_managers.forEach(packageManager => {
        const packageManagerData = container_dependencies[packageManager];

        // Check if this is a mixed-scope with multiple locations
        if (packageManagerData.locations) {
            // Handle mixed-scope with multiple locations
            for (const [location, locationData] of Object.entries(packageManagerData.locations)) {
                const scope = locationData.scope || 'unknown';
                const displayName = `${packageManager} (${scope})`;
                const dataWithLocation = { ...locationData, location: location };
                accordion_items += buildSingleAccordionItem(packageManager, displayName, dataWithLocation);
            }
        } else {
            // Handle system or project scope with direct dependencies
            accordion_items += buildSingleAccordionItem(packageManager, packageManager, packageManagerData);
        }
    });

    return accordion_items;
}

function buildDependencyTableRows(packages) {
    let tableRows = '';

    packages.forEach(pkg => {
        const version = escapeString(pkg.version || 'N/A');
        const depHash = pkg.hash || 'N/A';
        const truncatedHash = depHash !== 'N/A' ? depHash.substring(0, 12) + '...' : 'N/A';

        const row = dependencies_templates.depsTableRow
            .replace('{{depName}}', escapeString(pkg.name || 'N/A'))
            .replace('{{version}}', version)
            .replace('{{fullHash}}', escapeString(depHash))
            .replace('{{truncatedHash}}', escapeString(truncatedHash));

        tableRows += row;
    });

    return tableRows;
}


/* Chart starting code*/
$(document).ready( () => {
    (async () => {

        $('.ui.secondary.menu .item').tab({childrenOnly: true, context: '.run-data-container'}); // activate tabs for run data
        $('.ui.accordion').accordion();

        let url_params = getURLParams();

        if(url_params['id'] == null || url_params['id'] == '' || url_params['id'] == 'null') {
            showNotification('No run id', 'ID parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }

        // run all without await, as they have no blocking visuals or depended upon changes
        fetchAndFillNetworkIntercepts(url_params);
        fetchAndFillOptimizationsData(url_params);
        fetchAndFillAIData(url_params);
        fetchAndFillWarnings(url_params);
        fetchAndFillRunData(url_params);

        (async () => { // since we need to wait for fetchAndFillPhaseStatsData we wrap in async so later calls cann already proceed
            const phase_stats = await fetchAndFillPhaseStatsData(url_params);
            renderBadges(url_params, phase_stats?.data?.data?.['[RUNTIME]']?.data); // phase_stats can be empty when returned if run is broken or not done. thus the safe access
        })();


        if (localStorage.getItem('fetch_time_series') === 'true') {
            const [timeline_data, timeline_notes] = await Promise.all([
                fetchTimelineData(url_params),
                fetchTimelineNotes(url_params)
            ]);
            if (timeline_data == null) {
                document.querySelector('#api-loader').remove()
                document.querySelector('#message-chart-load-failure').classList.remove('hidden');
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
                    document.querySelector('#message-chart-load-failure').classList.remove('hidden');
                    return
                }
                const timeline_chart_data = await buildTimelineChartData(timeline_data);
                displayTimelineCharts(timeline_chart_data, timeline_notes);


            });
        }
    })();
});

