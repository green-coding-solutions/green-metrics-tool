const updateSetting = async (el) => {
    const left_el = el.parentElement.previousElementSibling.querySelector('input, select');
    const name = left_el.getAttribute('data-setting');
    try {
        if (left_el.type == 'select-multiple') {
            const value = $(left_el).dropdown('get values');
            await makeAPICall('/v1/user/setting', {name: name, value: value}, null, true)
            showNotification('Save success!', `${name} = ${value}`, 'success')
        } else if (left_el.type == 'checkbox') {
            await makeAPICall('/v1/user/setting', {name: name, value: left_el.checked}, null, true)
            showNotification('Save success!', `${name} = ${left_el.checked}`, 'success')
        } else {
            await makeAPICall('/v1/user/setting', {name: name, value: left_el.value}, null, true)
            showNotification('Save success!', `${name} = ${left_el.value}`, 'success')
        }
    } catch (err) {
        showNotification('Could not save setting', err);
        return
    }
}

const getSettings = async () => {
    try {
        const data = await makeAPICall('/v1/user/settings');

        // Checkboxes
        document.querySelector('#measurement-dev-no-optimizations').checked = data?.data?._capabilities?.measurement?.dev_no_optimizations === true;
        document.querySelector('#measurement-dev-no-sleeps').checked = data?.data?._capabilities?.measurement?.dev_no_sleeps === true;
        document.querySelector('#measurement-phase-padding').checked = data?.data?._capabilities?.measurement?.phase_padding === true;
        document.querySelector('#measurement-skip-volume-inspect').checked = data?.data?._capabilities?.measurement?.skip_volume_inspect === true;

        // Other
        document.querySelector('#measurement-flow-process-duration').value = data?.data?._capabilities?.measurement?.flow_process_duration;
        document.querySelector('#measurement-total-duration').value = data?.data?._capabilities?.measurement?.total_duration;
        $('#measurement-disabled-metric-providers').dropdown('set exactly', data?.data?._capabilities?.measurement?.disabled_metric_providers);
        document.querySelector('#measurement-system-check-threshold').value = data?.data?._capabilities?.measurement?.system_check_threshold;
        document.querySelector('#measurement-pre-test-sleep').value = data?.data?._capabilities?.measurement?.pre_test_sleep;
        document.querySelector('#measurement-idle-duration').value = data?.data?._capabilities?.measurement?.idle_duration;
        document.querySelector('#measurement-baseline-duration').value = data?.data?._capabilities?.measurement?.baseline_duration;
        document.querySelector('#measurement-post-test-sleep').value = data?.data?._capabilities?.measurement?.post_test_sleep;
        document.querySelector('#measurement-phase-transition-time').value = data?.data?._capabilities?.measurement?.phase_transition_time;
        document.querySelector('#measurement-wait-time-dependencies').value = data?.data?._capabilities?.measurement?.wait_time_dependencies;
    } catch (err) {
        showNotification('Could not load settings', err);
    }
}

const toggleJoules = () => {
    const display_in_joules = localStorage.getItem('display_in_joules') === 'true';
    localStorage.setItem('display_in_joules', !display_in_joules);
    showDisplayTextJoules(!display_in_joules)
}
const showDisplayTextJoules = (display_in_joules) => {
    if(display_in_joules) $("#energy-display").html("Currently showing <b>Joules</b>");
    else $("#energy-display").html("Currently showing <b>milli-Watt-Hours</b>");
}

const toggleTimelinesEnergyPower = () => {
    const transform_timelines_energy_to_power = localStorage.getItem('transform_timelines_energy_to_power') === 'true';
    localStorage.setItem('transform_timelines_energy_to_power', !transform_timelines_energy_to_power);
    showDisplayTextTransformTimelinesEnergyToPower(!transform_timelines_energy_to_power);
}
const showDisplayTextTransformTimelinesEnergyToPower = (transform_timelines_energy_to_power) => {
    if(transform_timelines_energy_to_power) $("#timeline-energy-or-power").html("Currently showing <b>power timelines</b>");
    else $("#timeline-energy-or-power").html("Currently showing <b>energy timelines</b>");
}

const toggleMetricUnits = () => {
    const display_in_metric_units = localStorage.getItem('display_in_metric_units') === 'true';
    localStorage.setItem('display_in_metric_units', !display_in_metric_units);
    showDisplayTextMetricUnits(!display_in_metric_units)
}
const showDisplayTextMetricUnits = (display_in_metric_units) => {
    if(display_in_metric_units) $("#units-display").html("Currently showing <b>metric units</b>");
    else $("#units-display").html("Currently showing <b>imperial units</b>");
}

const toggleTimeSeries = () => {
    const fetch_time_series = localStorage.getItem('fetch_time_series') === 'true';
    localStorage.setItem('fetch_time_series', !fetch_time_series);
    showDisplayTextTimeSeries(!fetch_time_series)
}
const showDisplayTextTimeSeries = (fetch_time_series) => {
    if(fetch_time_series) $("#fetch-time-series-display").html("Currently <b>fetching</b> time series by default");
    else $("#fetch-time-series-display").html("Currently <b>not fetching</b> time series by default");
}


const toggleTimeSeriesAVG = () => {
    const time_series_avg = localStorage.getItem('time_series_avg') === 'true';
    localStorage.setItem('time_series_avg', !time_series_avg);
    showDisplayTextTimeSeriesAVG(!time_series_avg)
}
const showDisplayTextTimeSeriesAVG = (time_series_avg) => {
    if(time_series_avg) $("#time-series-avg-display").html("Currently <b>showing</b> AVG time series");
    else $("#time-series-avg-display").html("Currently <b>not showing</b> AVG in time series");
}


const resetHelpTexts = () => {
    localStorage.setItem('closed_descriptions', '');
    document.querySelector('#reset-help-texts-button').innerText = 'OK!';
}

(() => {

    $(window).on('load', function() {
        $('.ui.secondary.menu .item').tab();
        $('select').dropdown({keepSearchTerm: true});
        $('.ui.checkbox').checkbox();

        showDisplayTextJoules(localStorage.getItem('display_in_joules') === 'true')
        showDisplayTextTransformTimelinesEnergyToPower(localStorage.getItem('transform_timelines_energy_to_power') === 'true')
        showDisplayTextMetricUnits(localStorage.getItem('display_in_metric_units') === 'true')
        showDisplayTextTimeSeries(localStorage.getItem('fetch_time_series') === 'true')
        showDisplayTextTimeSeriesAVG(localStorage.getItem('time_series_avg') === 'true')
        getSettings();
    });

})();
