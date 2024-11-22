/*
    WebComponent function without ShadowDOM
    to expand the template in the HTML pages
*/
class PhaseMetrics extends HTMLElement {
   connectedCallback() {
        this.innerHTML = `
        <h3 class="ui dividing header print-page-break">Key metrics</h3>
        <div class="ui four cards stackable">
            <div class="ui card phase-duration">
                <div class="ui content">
                    <div class="ui top attached purple label overflow-ellipsis">Phase Duration <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="clock icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Duration of the phase.">
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card machine-power">
                <div class="ui content">
                    <div class="ui top attached orange label overflow-ellipsis">Machine Power <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="power off icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Power of all hardware components during current usage phase.">
                            <span class="source"></span>
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card machine-energy">
                <div class="ui content">
                    <div class="ui top attached blue label overflow-ellipsis">Machine Energy <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="battery three quarters icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Energy of all hardware components during current usage phase.">
                            <span class="source"></span>
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card network-energy">
                <div class="ui content">
                    <div class="ui top blue attached label overflow-ellipsis">Network Transmission Energy<span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="battery three quarters icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Estimated external energy cost for network infrastructure. See details under formula.">
                            <u><a href="https://www.green-coding.io/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card machine-co2">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">Machine CO<sub>2</sub> (usage) <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="CO2 cost of usage phase">
                            <u><a href="https://www.green-coding.io/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card network-co2">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">Network Transmission CO2 <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Estimated external CO2 cost for network infrastructure. See details under formula.">
                            <u><a href="https://www.green-coding.io/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card embodied-carbon">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">Machine CO<sub>2</sub> (manufacturing)  <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="CO2 (manufacturing) attr. to lifetime share of phase duration.">
                            <u><a href="https://www.green-coding.io/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card software-carbon-intensity">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">SCI</sub> <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="SCI by the Green Software Foundation">
                            <u><a href="https://docs.green-coding.io/docs/measuring/sci/">see Details</a></u>
                            <i class="question circle icon"></i>
                        </div>
                        <div class="ui bottom left attached label">
                            <span class="metric-type"></span>
                        </div>
                    </div>
                </div>
            </div>
        </div><!-- end ui three cards stackable -->
        <br>
        <div class="ui accordion">
            <div class="title ui header">
                <i class="dropdown icon"></i> <a><u>Click here for detailed metrics ...</u></a>
            </div>
            <div class="content">
                <h3 class="ui dividing header">Detailed metrics</h3>
                <table class="ui celled table compare-metrics-table sortable">
                  <thead></thead>
                  <tbody></tbody>
                </table>
                <co2-tangible></co2-tangible>
                <h3 class="ui dividing header hide-for-single-stats">Detailed Charts</h3>
                <div class="compare-chart-container"></div>
            </div>
        </div>`;
    }
}

customElements.define('phase-metrics', PhaseMetrics);


/*
    TODO: Include one sided T-test?
*/
const displaySimpleMetricBox = (phase, metric_name, metric_data, detail_name, detail_data, comparison_case)  => {
    let max_value = ''
    if (detail_data.max != null) {
        let [max,max_unit] = convertValue(detail_data.max, metric_data.unit);
        max_value = `${max} ${max_unit}`;
    }
    let min_value = ''
    if (detail_data.min != null) {
        let [min,min_unit] = convertValue(detail_data.min, metric_data.unit);
        min_value = `${min} ${min_unit}`;
    }

    let max_mean_value = ''
    if (detail_data.max_mean != null) {
        let [max_mean,max_unit] = convertValue(detail_data.max_mean, metric_data.unit);
        max_mean_value = `${max_mean} ${max_unit}`;
    }
    let min_mean_value = ''
    if (detail_data.min_mean != null) {
        let [min_mean,min_unit] = convertValue(detail_data.min_mean, metric_data.unit);
        min_mean_value = `${min_mean} ${min_unit}`;
    }


    let std_dev_text = '';
    let std_dev_text_table = 'N/A';

    if(detail_data.stddev == 0) std_dev_text = std_dev_text_table = `± 0.00%`;
    else if(detail_data.stddev != null) {
        std_dev_text = std_dev_text_table = `± ${((detail_data.stddev/detail_data.mean)*100).toFixed(2)}%`
    }

    let scope = metric_name.split('_')
    scope = scope[scope.length-1]

    let [value, unit] = convertValue(detail_data.mean, metric_data.unit);

    let tr = document.querySelector(`div.tab[data-tab='${phase}'] table.compare-metrics-table tbody`).insertRow();
    if(comparison_case !== null) {
        tr.innerHTML = `
            <td data-position="bottom left" data-inverted="" data-tooltip="${getPretty(metric_name, 'explanation')}"><i class="question circle icon"></i>${getPretty(metric_name, 'clean_name')}</td>
            <td>${getPretty(metric_name, 'source')}</td>
            <td>${scope}</td>
            <td>${detail_name}</td>
            <td>${metric_data.type}</td>
            <td>${value}</td>
            <td>${unit}</td>
            <td>${std_dev_text_table}</td>
            <td>${max_value}</td>
            <td>${min_value}</td>
            <td>${max_mean_value}</td>
            <td>${min_mean_value}</td>`;

    } else {
        tr.innerHTML = `
            <td data-position="bottom left" data-inverted="" data-tooltip="${getPretty(metric_name, 'explanation')}"><i class="question circle icon"></i>${getPretty(metric_name, 'clean_name')}</td>
            <td>${getPretty(metric_name, 'source')}</td>
            <td>${scope}</td>
            <td>${detail_name}</td>
            <td>${metric_data.type}</td>
            <td>${value}</td>
            <td>${unit}</td>
            <td>${max_value}</td>
            <td>${min_value}</td>`;
    }


    updateKeyMetric(
        phase, metric_name, getPretty(metric_name, 'clean_name'), detail_name,
        value , std_dev_text, unit, detail_data.mean, metric_data.unit,
        getPretty(metric_name, 'explanation'), getPretty(metric_name, 'source')
    );
}

/*
    This function assumes that detail_data has only two elements. For everything else we would need to
    calculate a trend / regression and not a simple comparison
*/
const displayDiffMetricBox = (phase, metric_name, metric_data, detail_name, detail_data_array, is_significant)  => {

    // no max, we use significant rather
    let extra_label = 'not significant / no-test';
    if (is_significant == true) extra_label = 'Significant';

    // TODO: Remove this guard clause once we want to support more than 2 compared items
    if (detail_data_array.length > 2) throw "Comparions > 2 currently not implemented"

    // no value conversion in this block, cause we just use relatives
    let value = 'N/A';
    if (detail_data_array[0] == 0 && detail_data_array[1] == 0) {
        value = 0;
    } else if (detail_data_array[0] == null || detail_data_array[1] == null) {
        value = 'not comparable';
    } else {
       value = detail_data_array[0] == 0 ? 0: (((detail_data_array[1] - detail_data_array[0])/detail_data_array[0])*100).toFixed(2);
    }

    let icon_color = 'positive';
    if (value > 0) {
        icon_color = 'error';
        value = `+ ${value} %`;
    } else {
        value = `${value} %`; // minus (-) already present in number
    }

    let scope = metric_name.split('_')
    scope = scope[scope.length-1]

    let [value_1, unit] = convertValue(detail_data_array[0], metric_data.unit);
    let [value_2, _] = convertValue(detail_data_array[1], metric_data.unit);

    let tr = document.querySelector(`div.tab[data-tab='${phase}'] table.compare-metrics-table tbody`).insertRow();
    tr.innerHTML = `
        <td data-position="bottom left" data-inverted="" data-tooltip="${getPretty(metric_name, 'explanation')}"><i class="question circle icon"></i>${getPretty(metric_name, 'clean_name')}</td>
        <td>${getPretty(metric_name, 'source')}</td>
        <td>${scope}</td>
        <td>${detail_name}</td>
        <td>${metric_data.type}</td>
        <td>${value_1}</td>
        <td>${value_2}</td>
        <td>${unit}</td>
        <td class="${icon_color}">${value}</td>
        <td>${extra_label}</td>`;

    updateKeyMetric(
        phase, metric_name, getPretty(metric_name, 'clean_name'), detail_name,
        value, '', metric_data.unit, null, null,
        getPretty(metric_name, 'explanation'), getPretty(metric_name, 'source')
    );

}

const calculateCO2 = (phase, total_CO2_in_ug) => {
    let display_in_metric_units = localStorage.getItem('display_in_metric_units');
    if(display_in_metric_units == 'true') display_in_metric_units = true;
    else display_in_metric_units = false;

    // network via formula: https://www.green-coding.io/co2-formulas/
    let total_CO2_in_kg = total_CO2_in_ug / 1_000_000_000;
    const [component_co2_value, component_co2_unit] = rescaleCO2Value(total_CO2_in_kg)

    const daily_co2_budget_in_kg_per_day = 1.739; // (12.7 * 1000 * 0.05) / 365 from https://www.pawprint.eco/eco-blog/average-carbon-footprint-uk and https://www.pawprint.eco/eco-blog/average-carbon-footprint-globally
    const co2_budget_utilization = total_CO2_in_kg*100 / daily_co2_budget_in_kg_per_day;

    if (co2_budget_utilization) document.querySelector(`div.tab[data-tab='${phase}'] .co2-budget-utilization`).innerHTML = (co2_budget_utilization).toFixed(2) + ' <span class="si-unit">%</span>'

    upscaled_CO2_in_kg = total_CO2_in_kg * 1000 * 365 ; // upscaled to 365 days for 1000 runs per day

    if(display_in_metric_units) {
        document.querySelectorAll(".distance-units").forEach((el) => {el.innerText = "in kms by car"})
        document.querySelectorAll(".gasoline-units").forEach((el) => {el.innerText = "in litres"})
    }

    if(upscaled_CO2_in_kg) {
        let co2_distance_driven = (upscaled_CO2_in_kg / 0.000403 / 1000); // in miles
        let co2_gasoline = (upscaled_CO2_in_kg / 0.008887 / 1000); // in gallons

        if(display_in_metric_units){
            co2_distance_driven = co2_distance_driven * 1.60934; // to kilometres
            co2_gasoline = co2_gasoline * 3.78541; // to litres
        }

        document.querySelector(`div.tab[data-tab='${phase}'] .co2-distance-driven`).innerText = co2_distance_driven.toFixed(2);
        document.querySelector(`div.tab[data-tab='${phase}'] .co2-gasoline`).innerText = co2_gasoline.toFixed(2);
        document.querySelector(`div.tab[data-tab='${phase}'] .co2-trees`).innerText = (upscaled_CO2_in_kg / 0.06 / 1000).toFixed(2);
        // document.querySelector(`.co2-smartphones-charged`).innerText = (upscaled_CO2_in_kg / 0.00000822 / 1000).toFixed(2);
        document.querySelector(`div.tab[data-tab='${phase}'] .co2-flights`).innerText = (upscaled_CO2_in_kg / 1000).toFixed(2);
    }
}

const updateKeyMetric = (phase, metric_name, clean_name, detail_name, value, std_dev_text, unit, raw_value, raw_unit, explanation, source) => {

    let selector = null;
    // key metrics are already there, cause we want a fixed order, so we just replace
    if(machine_energy_metric_condition(metric_name)) {
        selector = '.machine-energy';
    } else if(network_energy_metric_condition(metric_name)) {
        selector = '.network-energy';
    } else if(phase_time_metric_condition(metric_name)) {
        selector = '.phase-duration';
    } else if(network_carbon_metric_condition(metric_name)) {
        selector = '.network-co2';
    } else if(embodied_carbon_share_metric_condition(metric_name)) {
        selector = '.embodied-carbon';
    } else if(sci_metric_condition(metric_name)) {
        selector = '.software-carbon-intensity';
    } else if(machine_power_metric_condition(metric_name)) {
        selector = '.machine-power';
    } else if(psu_machine_carbon_metric_condition(metric_name)) {
        selector = '.machine-co2';
    } else {
        return; // could not match key metric
    }


    document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .value span`).innerText = `${(value)} ${std_dev_text}`

    document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .value`).setAttribute('title', `${raw_value} [${raw_unit}]`)

    document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .si-unit`).innerText = `[${unit}]`
    if(std_dev_text != '') document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .metric-type`).innerText = `(AVG + STD.DEV)`;
    else if(String(value).indexOf('%') !== -1) document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .metric-type`).innerText = `(Diff. in %)`;

    node = document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .source`)
    if (node !== null) node.innerText = source // not every key metric shall have a custom detail_name

}
