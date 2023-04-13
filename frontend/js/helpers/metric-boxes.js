/*
    WebComponent function without ShadowDOM
    to expand the template in the HTML pages
*/
class PhaseMetrics extends HTMLElement {
   connectedCallback() {
        this.innerHTML = `
        <div class="ui four cards stackable no-transform-statistics">
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
                            <span class="detail-name"></span>
                            <i class="question circle icon"></i>
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
                            <span class="detail-name"></span>
                            <i class="question circle icon"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card network-energy">
                <div class="ui content">
                    <div class="ui top blue attached label overflow-ellipsis">Network Energy <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="battery three quarters icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Transfer cost of data through routers, data-centers and transmission networks.">
                            <span class="detail-name"></span>
                            <u><a href="https://www.green-coding.berlin/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
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
                            <u><a href="https://www.green-coding.berlin/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card network-co2">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">Network CO2 <span class="si-unit"></span></div>
                    <div class="description">
                        <div class="ui fluid mini statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span>N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Transfer cost of data through routers, data-centers and transmission networks.">
                            <u><a href="https://www.green-coding.berlin/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
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
                            <u><a href="https://www.green-coding.berlin/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
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
                <h3 class="ui dividing header">container / VM level metrics</h3>
                <div class="ui three cards stackable no-transform-statistics container-level-metrics"></div>
                <h3 class="ui dividing header">system level metrics</h3>
                <div class="ui three cards stackable no-transform-statistics system-level-metrics"></div>
                <h3 class="ui dividing header">component level metrics</h3>
                <div class="ui three cards stackable no-transform-statistics component-level-metrics"></div>
                <h3 class="ui dividing header">machine level metrics</h3>
                <div class="ui three cards stackable no-transform-statistics machine-level-metrics"></div>
                <h3 class="ui dividing header">extra metrics</h3>
                <div class="ui three cards stackable no-transform-statistics extra-metrics"></div>
                <h3 class="ui dividing header">Detailed Charts</h3>
                <div class="compare-chart-container"></div>
            </div>
        </div>`;
    }
}

customElements.define('phase-metrics', PhaseMetrics);


/*
    TODO: Include one sided T-test?
*/
const displaySimpleMetricBox = (phase, metric_name, metric_data, detail_data, comparison_key)  => {
    let extra_label = ''
    if (detail_data.max != null) {
        let [max,max_unit] = convertValue(detail_data.max, metric_data.unit);
        extra_label = `${max} ${max_unit} (MAX)`;

    }
    let std_dev_text = '';
    if(detail_data.stddev == 0) std_dev_text = `± 0.00%`
    else if(detail_data.stddev != null) {
        std_dev_text = `± ${((detail_data.stddev/detail_data.mean)*100).toFixed(2)}%`
    }


    let [value, unit] = convertValue(detail_data.mean, metric_data.unit);

    displayMetricBox(
        phase, metric_name, metric_data.clean_name, detail_data.name,
        value , std_dev_text, extra_label, unit,
        metric_data.explanation, metric_data.color, metric_data.icon
    );
}

/*
    This function assumes that detail_data has only two elements. For everything else we would need to
    calculate a trend / regression and not a simple comparison
*/
const displayDiffMetricBox = (phase, metric_name, metric_data, detail_data_array, comparison_key, is_significant)  => {
    let extra_label = '';
    if (is_significant == true) extra_label = 'Significant';
    else extra_label = 'not significant / no-test';

    // no max, we use significant rather

    // no value conversion, cause we just use relatives
    let value = (((detail_data_array[1].mean - detail_data_array[0].mean)/detail_data_array[0].mean)*100).toFixed(2)
    let icon_color = 'green';

    if (value > 0) {
        icon_color = 'red';
        value = `+ ${value} %`;
    } else {
        value = `${value} %`; // minus (-) already present in number
    }

    displayMetricBox(
        phase, metric_name, metric_data.clean_name, detail_data_array[0].name,
        value, '', extra_label, metric_data.unit,
        metric_data.explanation, metric_data.color, metric_data.icon, icon_color
    );
}

// TODO
const calculateCO2 = () => {
    // network via formula: https://www.green-coding.berlin/co2-formulas/
    const network_io_in_mWh = network_io * 0.00006 * 1000000;
    const network_io_in_J = network_io_in_mWh * 3.6;  //  60 * 60 / 1000 => 3.6
    if(display_in_watts) {
        if(network_io_in_mWh) document.querySelector(`div.tab[data-tab='${phase}'] .network-energy`).innerHTML = `${network_io_in_mWh.toFixed(2)} <span class="si-unit">mWh</span>`
    } else {
        if(network_io_in_J) document.querySelector(`div.tab[data-tab='${phase}'] .network-energy`).innerHTML = `${network_io_in_J.toFixed(2)} <span class="si-unit">J</span>`
    }

    // co2 calculations
    const network_io_co2_in_kg = ( (network_io_in_mWh / 1000000) * 519) / 1000;
    const [network_co2_value, network_co2_unit] = rescaleCO2Value(network_io_co2_in_kg)
    if (network_co2_value) document.querySelector(`div.tab[data-tab='${phase}'] .network-co2`).innerHTML = `${(network_co2_value).toFixed(2)} <span class="si-unit">${network_co2_unit}</span>`

    const total_CO2_in_kg = ( ((energy_in_mWh + network_io_in_mWh) / 1000000) * 519) / 1000;
    const [component_co2_value, component_co2_unit] = rescaleCO2Value(total_CO2_in_kg)
    if (component_co2_value) document.querySelector(`div.tab[data-tab='${phase}'] .machine-co2`).innerHTML = `${(component_co2_value).toFixed(2)} <span class="si-unit">${component_co2_unit}</span>`

    const daily_co2_budget_in_kg_per_day = 1.739; // (12.7 * 1000 * 0.05) / 365 from https://www.pawprint.eco/eco-blog/average-carbon-footprint-uk and https://www.pawprint.eco/eco-blog/average-carbon-footprint-globally
    const co2_budget_utilization = total_CO2_in_kg*100 / daily_co2_budget_in_kg_per_day;

    if (co2_budget_utilization) document.querySelector("#co2-budget-utilization").innerHTML = (co2_budget_utilization).toFixed(2) + ' <span class="si-unit">%</span>'

    upscaled_CO2_in_kg = total_CO2_in_kg * 1000 * 365 ; // upscaled to 365 days for 1000 runs per day

    if(upscaled_CO2_in_kg) {
        document.querySelector("#trees").innerText = (upscaled_CO2_in_kg / 0.06 / 1000).toFixed(2);
        document.querySelector("#miles-driven").innerText = (upscaled_CO2_in_kg / 0.000403 / 1000).toFixed(2);
        document.querySelector("#gasoline").innerText = (upscaled_CO2_in_kg / 0.008887 / 1000).toFixed(2);
            // document.querySelector("#smartphones-charged").innerText = (upscaled_CO2_in_kg / 0.00000822 / 1000).toFixed(2);
        document.querySelector("#flights").innerText = (upscaled_CO2_in_kg / 1000).toFixed(2);
    }
}

const displayMetricBox = (phase, metric_name, clean_name, detail_name, value, std_dev_text, extra_label, unit, explanation, header_color, icon, stat_color = '') => {

    // key metrics are already there, cause we want a fixed order, so we just replace
    if(metric.match(/^.*_energy.*_machine$/) !== null) {
        updateKeyMetric('.machine-energy', phase, value, unit, std_dev_text, clean_name)
    } else if(metric == 'network_energy_formula_global') {
        updateKeyMetric('.network-energy', phase, value, unit, std_dev_text, clean_name)
    } else if(metric == 'phase_time_syscall_system') {
        updateKeyMetric('.phase-duration', phase, value, unit, std_dev_text, clean_name)
    } else if(metric == 'network_co2_formula_global') {
        updateKeyMetric('.network-co2', phase, value, unit, std_dev_text, clean_name)
    } else if(metric.match(/^.*_power.*_machine$/) !== null) {
        updateKeyMetric('.machine-power', phase, value, unit, std_dev_text, clean_name)
    } else if(metric.match(/^.*_co2.*_machine$/) !== null) {
        updateKeyMetric('.machine-co2', phase, value, unit, std_dev_text, clean_name)
    }


    let location = 'div.extra-metrics'
    if(metric_name.indexOf('_container') !== -1 || metric_name.indexOf('_vm') !== -1)
        location = 'div.container-level-metrics';
    else if(metric_name.indexOf('_system') !== -1)
         location = 'div.system-level-metrics';
    else if(metric_name.indexOf('_component') !== -1)
         location = 'div.component-level-metrics';
    else if(metric_name.indexOf('_machine') !== -1)
         location = 'div.machine-level-metrics';

     if (extra_label != '') extra_label = `<div class="ui bottom left attached label">${extra_label}</div>`;

    const node = document.createElement("div")
    node.classList.add("card");
    node.classList.add('ui')
    node.innerHTML = `
        <div class="content">
            <div class="ui top attached ${header_color} label overflow-ellipsis">${clean_name} <span class="si-unit">[${unit}]</span></div>
            <div class="description">
                <div class="ui fluid mini statistic ${stat_color}">
                    <div class="value">
                        <i class="${icon} icon"></i> ${value}
                        ${std_dev_text}
                    </div>
                </div>
                ${extra_label}
                <div class="ui bottom right attached label icon explanation rounded" data-position="bottom right" data-inverted="" data-tooltip="${explanation}">
                    ${detail_name}
                    <i class="question circle icon"></i>
                </div>
            </div>
        </div>

        `;
    document.querySelector(`div.tab[data-tab='${phase}'] ${location}`).appendChild(node)
}

const updateKeyMetric = (selector, phase, value, unit, std_dev_text, metric_name) => {
    document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .value span`).innerText = `${(value)} ${std_dev_text}`
    document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .si-unit`).innerText = `[${unit}]`
    node = document.querySelector(`div.tab[data-tab='${phase}'] ${selector} .detail-name`)
    if (node !== null) node.innerText = metric_name // not every key metric shall have a custom detail_name

}


/* TODO
    // network via formula: https://www.green-coding.berlin/co2-formulas/
    const network_io_in_mWh = network_io * 0.00006 * 1000000;
    const network_io_in_J = network_io_in_mWh * 3.6;  //  60 * 60 / 1000 => 3.6
    if(display_in_watts) {
        if(network_io_in_mWh) document.querySelector(`div.tab[data-tab='${phase}'] .network-energy`).innerHTML = `${network_io_in_mWh.toFixed(2)} <span class="si-unit">mWh</span>`
    } else {
        if(network_io_in_J) document.querySelector(`div.tab[data-tab='${phase}'] .network-energy`).innerHTML = `${network_io_in_J.toFixed(2)} <span class="si-unit">J</span>`
    }

    // co2 calculations
    const network_io_co2_in_kg = ( (network_io_in_mWh / 1000000) * 519) / 1000;
    const [network_co2_value, network_co2_unit] = rescaleCO2Value(network_io_co2_in_kg)
    if (network_co2_value) document.querySelector(`div.tab[data-tab='${phase}'] .network-co2`).innerHTML = `${(network_co2_value).toFixed(2)} <span class="si-unit">${network_co2_unit}</span>`

    const total_CO2_in_kg = ( ((energy_in_mWh + network_io_in_mWh) / 1000000) * 519) / 1000;
    const [component_co2_value, component_co2_unit] = rescaleCO2Value(total_CO2_in_kg)
    if (component_co2_value) document.querySelector(`div.tab[data-tab='${phase}'] .machine-co2`).innerHTML = `${(component_co2_value).toFixed(2)} <span class="si-unit">${component_co2_unit}</span>`

    const daily_co2_budget_in_kg_per_day = 1.739; // (12.7 * 1000 * 0.05) / 365 from https://www.pawprint.eco/eco-blog/average-carbon-footprint-uk and https://www.pawprint.eco/eco-blog/average-carbon-footprint-globally
    const co2_budget_utilization = total_CO2_in_kg*100 / daily_co2_budget_in_kg_per_day;

    if (co2_budget_utilization) document.querySelector("#co2-budget-utilization").innerHTML = (co2_budget_utilization).toFixed(2) + ' <span class="si-unit">%</span>'

    upscaled_CO2_in_kg = total_CO2_in_kg * 1000 * 365 ; // upscaled to 365 days for 1000 runs per day

    if(upscaled_CO2_in_kg) {
        document.querySelector("#trees").innerText = (upscaled_CO2_in_kg / 0.06 / 1000).toFixed(2);
        document.querySelector("#miles-driven").innerText = (upscaled_CO2_in_kg / 0.000403 / 1000).toFixed(2);
        document.querySelector("#gasoline").innerText = (upscaled_CO2_in_kg / 0.008887 / 1000).toFixed(2);
            // document.querySelector("#smartphones-charged").innerText = (upscaled_CO2_in_kg / 0.00000822 / 1000).toFixed(2);
        document.querySelector("#flights").innerText = (upscaled_CO2_in_kg / 1000).toFixed(2);
    }*/