
var display_in_watts = localStorage.getItem('display_in_watts');
if(display_in_watts == 'true') display_in_watts = true;
else display_in_watts = false;

var remove_idle = localStorage.getItem('remove_idle');
if(remove_idle == 'true') remove_idle = true;
else remove_idle = false;

var display_in_metric_units = false;
if(display_in_metric_units == 'true') display_in_metric_units = true;
else display_in_metric_units = false;

let toggleWatts = () => {
    localStorage.setItem('display_in_watts', !display_in_watts);
    window.location.reload();
}

let toggleRemoveIdle = () => {
    localStorage.setItem('remove_idle', !remove_idle);
    window.location.reload();
}

let toggleUnits = () => {
    localStorage.setItem('display_in_metric_units', !display_in_metric_units);
    window.location.reload();
}


(() => {

    $(window).on('load', function() {
      $('.ui.secondary.menu .item').tab();

      if(display_in_watts) $("#energy-display").text("Currently showing Watts");
      else $("#energy-display").text("Currently showing Joules");
      if(remove_idle) $("#remove-idle").text("Currently hiding idle");
      else $("#remove-idle").text("Currently showing idle");
      if(display_in_metric_units) $("#units-display").text("Currently showing metric units");
      else $("#units-display").text("Currently showing imperial units");

    });

})();
