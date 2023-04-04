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
                            [SYSTEM]
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
                            [SYSTEM]
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
                            [SYSTEM]
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
    This function behaves differentrly if it gets passed an element of detail metrics or a list of.

    When a list it passed it will calculate a std.dev. and instruct the createMetricBox to display the +/-
*/
const displayDetailMetricBox = (metric, metric_data, compare_key, phase, comparison_type) => {

    // the metric might contain multiple details and multiple to compare
    // this we iterate over it here
    // what we wanna show is the detailed metric itself with its max
    // and if it has a stddev we also want to show that
    // if there is even a metric to compare to, then we also want to show that

    let location = 'div.extra-metrics'
    if(metric.name.indexOf('_container') !== -1 || metric.name.indexOf('_vm') !== -1)
        location = 'div.container-level-metrics';
    else if(metric.name.indexOf('_system') !== -1)
         location = 'div.system-level-metrics';
    else if(metric.name.indexOf('_component') !== -1)
         location = 'div.component-level-metrics';
    else if(metric.name.indexOf('_machine') !== -1)
         location = 'div.machine-level-metrics';

    let max_label = ''
    if (metric_data.max != null) {
        max_label = `<div class="ui bottom left attached label">
        ${metric_data.max.toFixed(2)} ${metric.unit} (MAX)
        </div>`
    }
    let std_dev_text = '';

    if(metric_data.stddev == 0) std_dev_text = `± 0.00%`
    else if(metric_data.stddev != null) {
        std_dev_text = `± ${(metric_data.stddev/metric_data.mean).toFixed(2)}%`
    }

    let metric_name = metric.clean_name;
    if(comparison_type != null && comparison_type != 'Repeated Runs')
        metric_name = `${metric_name} [${compare_key}]`
    let node = createMetricBox(
        metric,
        metric_name,
        metric_data.mean,
        std_dev_text,
        max_label
    );
    document.querySelector(`div.tab[data-tab='${phase}'] ${location}`).appendChild(node)
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

const createMetricBox = (metric, name, value, std_dev_text, max_label) => {
    const node = document.createElement("div")
    node.classList.add("card");
    node.classList.add('ui')
    node.innerHTML = `
        <div class="content">
            <div class="ui top attached ${metric.color} label overflow-ellipsis">${name}</div>
            <div class="description">
                <div class="ui fluid tiny statistic">
                    <div class="value">
                        <i class="${metric.icon} icon"></i> ${value.toFixed(2)} <span class="si-unit">${metric.unit}</span>
                        ${std_dev_text}
                    </div>
                </div>
                ${max_label}
                <div class="ui bottom right attached label icon rounded" data-position="bottom right" data-inverted="" data-tooltip="${metric.explanation}">
                    ${metric.detail_name}
                    <i class="question circle icon"></i>
                </div>
            </div>
        </div>

        `;
    return node;
}



