
const display_in_watthours = localStorage.getItem('display_in_watthours') == 'false' ? false : true;
const transform_timelines_energy_to_power = localStorage.getItem('transform_timelines_energy_to_power') == 'true' ? true : false;
const display_in_metric_units = localStorage.getItem('display_in_metric_units') == 'true' ? true : false;
const fetch_time_series = localStorage.getItem('fetch_time_series') == 'true' ? true : false;
const time_series_avg = localStorage.getItem('time_series_avg') == 'true' ? true : false;

const toggleWattHours = () => {
    localStorage.setItem('display_in_watthours', !display_in_watthours);
    window.location.reload();
}

const toggleTimelinesEnergyPower = () => {
    localStorage.setItem('transform_timelines_energy_to_power', !transform_timelines_energy_to_power);
    window.location.reload();
}

const toggleMetricUnits = () => {
    localStorage.setItem('display_in_metric_units', !display_in_metric_units);
    window.location.reload();
}

const toggleTimeSeries = () => {
    localStorage.setItem('fetch_time_series', !fetch_time_series);
    window.location.reload();
}

const toggleTimeSeriesAVG = () => {
    localStorage.setItem('time_series_avg', !time_series_avg);
    window.location.reload();
}

const resetHelpTexts = () => {
    localStorage.setItem('closed_descriptions', '');
    document.querySelector('#reset-help-texts-button').innerText = 'OK!';
}

(() => {

    $(window).on('load', function() {
      $('.ui.secondary.menu .item').tab();

      if(display_in_watthours) $("#energy-display").text("Currently showing Watt-Hours");
      else $("#energy-display").text("Currently showing Joules");

      if(transform_timelines_energy_to_power) $("#timeline-energy-or-power").text("Currently showing power timelines");
      else $("#timeline-energy-or-power").text("Currently showing energy timelines");

      if(display_in_metric_units) $("#units-display").text("Currently showing metric units");
      else $("#units-display").text("Currently showing imperial units");

      if(fetch_time_series) $("#fetch-time-series-display").text("Currently fetching time series by default");
      else $("#fetch-time-series-display").text("Currently not fetching time series by default");

      if(time_series_avg) $("#time-series-avg-display").text("Currently showing AVG time series");
      else $("#time-series-avg-display").text("Currently not showing AVG in time series");


    });

})();
