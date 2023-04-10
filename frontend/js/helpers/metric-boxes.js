/*
    WebComponent function without ShadowDOM
    to expand the template in the HTML pages
*/
class PhaseMetrics extends HTMLElement {
   connectedCallback() {
        this.innerHTML = `
        <div class="ui three cards stackable no-transform-statistics">
            <div class="ui card">
                <div class="ui content">
                    <div class="ui top attached orange label overflow-ellipsis">Machine Power</div>
                    <div class="description">
                        <div class="ui fluid tiny statistic">
                            <div class="value">
                                <i class="power off icon"></i> <span class="machine-power">N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Power of all hardware components during current usage phase.">
                            [MACHINE]
                            <i class="question circle icon"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card">
                <div class="ui content">
                    <div class="ui top attached blue label overflow-ellipsis">Machine Energy</div>
                    <div class="description">
                        <div class="ui fluid tiny statistic">
                            <div class="value">
                                <i class="battery three quarters icon"></i> <span class="machine-energy">N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Energy of all hardware components during current usage phase.">
                            [MACHINE]
                            <i class="question circle icon"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card">
                <div class="ui content">
                    <div class="ui top blue attached label overflow-ellipsis">Network Energy</div>
                    <div class="description">
                        <div class="ui fluid tiny statistic">
                            <div class="value">
                                <i class="battery three quarters icon"></i> <span class="network-energy">N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Transfer cost of data through routers, data-centers and transmission networks.">
                            <u><a href="https://www.green-coding.berlin/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">Machine CO<sub>2</sub> (usage)</div>
                    <div class="description">
                        <div class="ui fluid tiny statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span class="machine-co2">N/A</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">Network CO2</div>
                    <div class="description">
                        <div class="ui fluid tiny statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span class="network-co2">N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="Transfer cost of data through routers, data-centers and transmission networks.">
                            <u><a href="https://www.green-coding.berlin/co2-formulas/">via Formula</a></u>
                            <i class="question circle icon"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="ui card">
                <div class="ui content">
                    <div class="ui top black attached label overflow-ellipsis">Machine CO<sub>2</sub> (manufacturing) </div>
                    <div class="description">
                        <div class="ui fluid tiny statistic">
                            <div class="value">
                                <i class="burn icon"></i> <span class="embodied-carbon">N/A</span>
                            </div>
                        </div>
                        <div class="ui bottom right attached label icon" data-position="bottom right" data-inverted="" data-tooltip="CO2 (manufacturing) attr. to lifetime share of phase duration.">
                            [MACHINE]
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
const displaySimpleDetailMetricBox = (phase, metric_name, metric_data, detail_data, comparison_key)  => {
    let extra_label = ''
    if (detail_data.max != null) extra_label = `${detail_data.max.toFixed(2)} ${metric_data.unit} (MAX)`;

    let std_dev_text = '';
    if(detail_data.stddev == 0) std_dev_text = `± 0.00%`
    else if(detail_data.stddev != null) {
        std_dev_text = `± ${(detail_data.stddev/detail_data.mean).toFixed(2)}%`
    }
    console.log(detail_data);
    let value = detail_data.mean.toFixed(2);

    displayMetricBox(
        phase, metric_name, metric_data.clean_name, detail_data.name,
        value , std_dev_text, extra_label, metric_data.unit,
        metric_data.explanation, metric_data.color, metric_data.icon
    );
}

/*
    This function assumes that detail_data has only two elements. For everything else we would need to
    calculate a trend / regression and not a simple comparison
*/
const displayDiffDetailMetricBox = (phase, metric_name, metric_data, detail_data_array, comparison_key, is_significant)  => {
    let extra_label = '';
    if (is_significant == true) extra_label = 'Significant';
    else extra_label = 'not significant / no-test';

    if (detail_data_array[0].max != null && detail_data_array[1].max != null) {
        max_label = `${Math.max(detail_data_array[0].max, detail_data_array[1].max).toFixed(2)} ${metric_data.unit} (MAX)`
    }

    let std_dev_text = '';
    let value = ((detail_data_array[1].mean - detail_data_array[0].mean)/detail_data_array[0].mean).toFixed(2)
    let icon_color = 'green';

    if (value > 0) {
        icon_color = 'red';
        value = `+ ${value} %`;
    } else {
        value = `${value} %`; // minus (-) already present in number
    }

    displayMetricBox(
        phase, metric_name, metric_data.clean_name, detail_data_array[0].name,
        value, std_dev_text, extra_label, metric_data.unit,
        metric_data.explanation, metric_data.color, metric_data.icon, icon_color
    );
}



/*
        if(comparison_type != null && comparison_type != 'repetition_comparison') {
            document.querySelector(`div.tab[data-tab='${phase}'] ${location}`).insertAdjacentHTML('beforeend', '<div class="break"></div>')
        }
*/

const createKeyMetricBox = (energy, power, network_io, phase) => {
    const energy_in_mWh = energy / 3.6;
    if(energy_in_mWh) {
        if(display_in_watts) {
            document.querySelector(`div.tab[data-tab='${phase}'] .machine-energy`).innerHTML = `${energy_in_mWh.toFixed(2)} <span class="si-unit">mWh</span>`
        } else {
            document.querySelector(`div.tab[data-tab='${phase}'] .machine-energy`).innerHTML = `${energy.toFixed(2)} <span class="si-unit">J</span>`
        }
    }

    if(power) {
        document.querySelector(`div.tab[data-tab='${phase}'] .machine-power`).innerHTML = `${power.toFixed(2)} <span class="si-unit">W</span>`;
    }
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
            <div class="ui top attached ${header_color} label overflow-ellipsis">${clean_name}</div>
            <div class="description">
                <div class="ui fluid tiny statistic ${stat_color}">
                    <div class="value">
                        <i class="${icon} icon"></i> ${value} <span class="si-unit">${unit}</span>
                        ${std_dev_text}
                    </div>
                </div>
                ${extra_label}
                <div class="ui bottom right attached label icon rounded" data-position="bottom right" data-inverted="" data-tooltip="${explanation}">
                    ${detail_name}
                    <i class="question circle icon"></i>
                </div>
            </div>
        </div>

        `;
    document.querySelector(`div.tab[data-tab='${phase}'] ${location}`).appendChild(node)
}



