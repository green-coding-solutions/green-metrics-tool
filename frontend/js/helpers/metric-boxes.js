class PhaseMetrics extends HTMLElement {
   connectedCallback() {

        const createCard = ({ key, name, icon, variable }, suffix = '', colour) => {
            const cardClass = variable ? `${key}-${suffix}` : key;
            const colourClass = variable ? colour : 'teal';
            return `
                <div class="ui ${colourClass} card ${cardClass}">
                    <div class="content">
                        <i class="${icon} icon"></i><span class="metric-name">${name}</span>
                        <div class="right floated meta source"></div>

                    </div>
                    <div class="extra content">
                        <div class="description">
                            <span class="value bold">N/A</span> <span class="si-unit"></span>
                            <div class="right floated meta help" data-tooltip="No data available" data-position="bottom right" data-inverted>
                                <span class="metric-type"></span><i class="question circle outline icon"></i>
                            </div>
                        </div>
                    </div>
                </div>`;
        };

        const buildTab = (tab, active = false, colour='teal') => `
            <div class="ui tab ${active ? 'active' : ''}" data-tab="${tab}">
                <div class="ui five cards stackable">
                    ${HARDWARECARDS.map(card => createCard(card, tab, colour)).join('')}
                </div>
                <h4 class="ui horizontal left aligned divider header">Impact</h4>
                <div class="ui five cards stackable">
                    ${EXTRACARDS.map(card => createCard(card, tab, colour)).join('')}
                </div>

            </div>`;


        this.innerHTML = `
            <div class="ui segments">
                <div class="ui segment">
                    <div class="ui pointing menu">
                        <a class="active item" data-tab="power">Power</a>
                        <a class="item" data-tab="energy">Energy</a>
                        <a class="item" data-tab="co2">CO<sub>2</sub></a>
                    </div>
                    <h4 class="ui horizontal left aligned divider header">Hardware</h4>
                    ${buildTab('power', true, 'orange')}
                    ${buildTab('energy', false, 'blue')}
                    ${buildTab('co2', false, 'black')}
                </div>
            </div>
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
            </div>
        `;

        $(this).find('.menu .item').tab();
    }
}

customElements.define('phase-metrics', PhaseMetrics);


/*
    TODO: Include one sided T-test?
*/
const displaySimpleMetricBox = (phase, metric_name, metric_data, detail_name, detail_data, comparison_case)  => {
    let max_value = '-'
    if (detail_data.max != null) {
        const [max,max_unit] = convertValue(detail_data.max, metric_data.unit);
        max_value = `${max?.toFixed(2)} ${max_unit}`;
    }
    let min_value = '-'
    if (detail_data.min != null) {
        const [min,min_unit] = convertValue(detail_data.min, metric_data.unit);
        min_value = `${min?.toFixed(2)} ${min_unit}`;
    }

    let max_mean_value = '-'
    if (detail_data.max_mean != null) {
        const [max_mean,max_unit] = convertValue(detail_data.max_mean, metric_data.unit);
        max_mean_value = `${max_mean?.toFixed(2)} ${max_unit}`;
    }
    let min_mean_value = '-'
    if (detail_data.min_mean != null) {
        const [min_mean,min_unit] = convertValue(detail_data.min_mean, metric_data.unit);
        min_mean_value = `${min_mean?.toFixed(2)} ${min_unit}`;
    }


    let std_dev_text = '';
    let std_dev_text_table = 'N/A';

    if(detail_data.stddev == 0) std_dev_text = std_dev_text_table = `± 0.00%`;
    else if(detail_data.stddev != null) {
        std_dev_text = std_dev_text_table = `± ${((detail_data.stddev/detail_data.mean)*100).toFixed(2)}%`
    }

    let scope = metric_name.split('_')
    scope = scope[scope.length-1]

    const [transformed_value, transformed_unit] = convertValue(detail_data.mean, metric_data.unit);

    let tr = document.querySelector(`div.tab[data-tab='${phase}'] table.compare-metrics-table tbody`).insertRow();
    if(comparison_case != null) {
        tr.innerHTML = `
            <td data-position="bottom left" data-inverted="" data-tooltip="${getPretty(metric_name, 'explanation')}"><i class="question circle icon"></i>${getPretty(metric_name, 'clean_name')}</td>
            <td>${getPretty(metric_name, 'source')}</td>
            <td>${scope}</td>
            <td>${detail_name}</td>
            <td>${metric_data.type}</td>
            <td><span title="${detail_data.mean}">${transformed_value?.toFixed(2)}</span> ${ transformed_value?.toFixed(2) == '0.00' ? `<span data-tooltip="Value is lower than rounding. Unrounded value is ${detail_data.mean} ${metric_data.unit}" data-position="bottom center" data-inverted><i class="question circle icon link"></i></span>` : ''}</td>
            <td>${transformed_unit}</td>
            <td>${std_dev_text_table}</td>
            <td>${max_value}</td>
            <td>${min_value}</td>
            <td>${max_mean_value}</td>
            <td>${min_mean_value}</td>
            <td>
                <span title="${detail_data.sr_avg_avg} us">${(detail_data.sr_avg_avg == null) ? '-' : (detail_data.sr_avg_avg/1000).toFixed(0)}</span> /
                <span title="${detail_data.sr_95p_max} us">${(detail_data.sr_95p_max == null) ? '-' : (detail_data.sr_95p_max/1000).toFixed(0)}</span> /
                <span title="${detail_data.sr_max_max} us">${(detail_data.sr_max_max == null) ? '-' : (detail_data.sr_max_max/1000).toFixed(0)}</span> ms
            </td>`;

    } else {
        tr.innerHTML = `
            <td data-position="bottom left" data-inverted="" data-tooltip="${getPretty(metric_name, 'explanation')}"><i class="question circle icon"></i>${getPretty(metric_name, 'clean_name')}</td>
            <td>${getPretty(metric_name, 'source')}</td>
            <td>${scope}</td>
            <td>${detail_name}</td>
            <td>${metric_data.type}</td>
            <td><span title="${detail_data.mean}">${transformed_value?.toFixed(2)}</span> ${ transformed_value?.toFixed(2) == '0.00' ? `<span data-tooltip="Value is lower than rounding. Unrounded value is ${detail_data.mean} ${metric_data.unit}" data-position="bottom center" data-inverted><i class="question circle icon link"></i></span>` : ''}</td>
            <td>${transformed_unit}</td>
            <td>${max_value}</td>
            <td>${min_value}</td>
            <td>
                <span title="${detail_data.sr_avg_avg} us">${(detail_data.sr_avg_avg == null) ? '-' : (detail_data.sr_avg_avg/1000).toFixed(0)}</span> /
                <span title="${detail_data.sr_95p_max} us">${(detail_data.sr_95p_max == null) ? '-' : (detail_data.sr_95p_max/1000).toFixed(0)}</span> /
                <span title="${detail_data.sr_max_max} us">${(detail_data.sr_max_max == null) ? '-' : (detail_data.sr_max_max/1000).toFixed(0)}</span> ms
            </td>`;
    }


    updateKeyMetric(
        phase, metric_name, getPretty(metric_name, 'clean_name'), detail_name,
        transformed_value.toFixed(2) , std_dev_text, transformed_unit, detail_data.mean, metric_data.unit,
        getPretty(metric_name, 'explanation'), getPretty(metric_name, 'source')
    );
}

/*
    This function assumes that detail_data has only two elements. For everything else we would need to
    calculate a trend / regression and not a simple comparison
*/
const displayDiffMetricBox = (phase, metric_name, metric_data, detail_name, detail_data_array, is_significant)  => {

    // no max, we use significant rather
    const extra_label = (is_significant == true) ? 'Significant' : 'not significant / no-test';

    // TODO: Remove this guard clause once we want to support more than 2 compared items
    if (detail_data_array.length > 2) throw "Comparions > 2 currently not implemented"

    // no value conversion in this block, cause we just use relatives
    let relative_difference = 'N/A';
    if (detail_data_array[0] == 0 && detail_data_array[1] == 0) {
        relative_difference = 0;
    } else if (detail_data_array[0] == null || detail_data_array[1] == null) {
        relative_difference = 'not comparable';
    } else {
       relative_difference = detail_data_array[0] == 0 ? 0: (((detail_data_array[1] - detail_data_array[0])/detail_data_array[0])*100).toFixed(2);
    }

    let icon_color = 'positive';
    if (relative_difference > 0) {
        icon_color = 'error';
        relative_difference = `+ ${relative_difference} %`;
    } else {
        relative_difference = `${relative_difference} %`; // minus (-) already present in number
    }

    let scope = metric_name.split('_')
    scope = scope[scope.length-1]

    const [transformed_value_1, transformed_unit] = convertValue(detail_data_array[0], metric_data.unit);
    const [transformed_value_2, _] = convertValue(detail_data_array[1], metric_data.unit);

    let tr = document.querySelector(`div.tab[data-tab='${phase}'] table.compare-metrics-table tbody`).insertRow();
    tr.innerHTML = `
        <td data-position="bottom left" data-inverted="" data-tooltip="${getPretty(metric_name, 'explanation')}"><i class="question circle icon"></i>${getPretty(metric_name, 'clean_name')}</td>
        <td>${getPretty(metric_name, 'source')}</td>
        <td>${scope}</td>
        <td>${detail_name}</td>
        <td>${metric_data.type}</td>
        <td><span title="${detail_data_array[0]}">${transformed_value_1?.toFixed(2)}</span> ${ transformed_value_1?.toFixed(2) == '0.00' ? `<span data-tooltip="Value is lower than rounding. Unrounded value is ${detail_data_array[0]} ${metric_data.unit}" data-position="bottom center" data-inverted><i class="question circle icon link"></i></span>` : ''}</td>
        <td><span title="${detail_data_array[1]}">${transformed_value_2?.toFixed(2)}</span> ${ transformed_value_2?.toFixed(2) == '0.00' ? `<span data-tooltip="Value is lower than rounding. Unrounded value is ${detail_data_array[1]} ${metric_data.unit}" data-position="bottom center" data-inverted><i class="question circle icon link"></i></span>` : ''}</td>
        <td>${transformed_unit}</td>
        <td class="${icon_color}">${relative_difference}</td>
        <td>${extra_label}</td>`;

    updateKeyMetric(
        phase, metric_name, getPretty(metric_name, 'clean_name'), detail_name,
        relative_difference, '', transformed_unit, null, null,
        getPretty(metric_name, 'explanation'), getPretty(metric_name, 'source')
    );

}

const calculateCO2 = (phase, total_CO2_in_ug) => {
    const display_in_metric_units = localStorage.getItem('display_in_metric_units') === 'true' ? true : false;

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

const updateKeyMetric = (
    phase, metric_name, clean_name, detail_name,
    value, std_dev_text, unit, raw_value, raw_unit,
    explanation, source
) => {

    let selector = null;



    if (phase_time_metric_condition(metric_name)) {
        selector = '.runtime';
    } else if (network_io_metric_condition(metric_name)) {
        selector = '.network-data';
    } else if (embodied_carbon_share_metric_condition(metric_name)) {
        selector = '.embodied-carbon';
    }else if (psu_machine_carbon_metric_condition(metric_name)) {
        selector = '.machine-co2';
    } else if (sci_metric_condition(metric_name)) {
        selector = '.sci';
    } else {

        let component = null;
        if (metric_name.includes('cpu')) component = 'cpu';
        else if (metric_name.includes('memory') || metric_name.includes('dram')) component = 'dram';
        else if (metric_name.includes('gpu')) component = 'gpu';
        else if (metric_name.includes('disk')) component = 'disk';
        else if (metric_name.includes('psu') && metric_name.includes('machine')) component = 'machine';
        else if (metric_name.includes('network')) component = 'network';
        else return; // no selector found, which means this is no currently configured key metric

        if (component !== null) {
            if (metric_name.startsWith(`${component}_power_`)) selector = `.${component}-power`;
            else if (metric_name.startsWith(`${component}_energy_`)) selector = `.${component}-energy`;
            else if (metric_name.startsWith(`${component}_carbon_`)) selector = `.${component}-co2`;
            else return; // no selector found, which means this is no currently configured key metric
        }
    }

    const cards = document.querySelectorAll(`div.tab[data-tab='${phase}'] ${selector}`);

    if (cards.length === 0) {
        console.warn(`No card found for selector "${selector}" in phase "${phase}"`);
        return;
    }

    cards.forEach(card => {
        const valueNode = card.querySelector('.value');
        valueNode.innerText = `${value} ${std_dev_text}`;
        if (raw_value != null && raw_unit != null){
            // this check can be improved in the future once we see missing tooltips to only skip
            // if a "repeated run" comparison is done, as this is the only case where we want no tooltips
            valueNode.setAttribute('title', `${raw_value} [${raw_unit}]`);
        }

        const unitNode = card.querySelector('.si-unit');
        if (unitNode) unitNode.innerText = unit;

        const typeNode = card.querySelector('.metric-type');

        if(std_dev_text != ''){
            if (typeNode) typeNode.innerText = `(AVG + STD.DEV)`;
        } else {
            if(String(value).indexOf('%') !== -1) {
                if (typeNode) typeNode.innerText = `(Diff. in %)`;
            }
        }

        const helpNode = card.querySelector('.help');
        if (helpNode) helpNode.setAttribute('data-tooltip', explanation || 'No data available');

        const metricNameNode = card.querySelector('.metric-name');
        if (metricNameNode) metricNameNode.innerText = clean_name || '';

        const sourceNode = card.querySelector('.source');
        if (sourceNode) sourceNode.innerText = `via ${source}` || '';
    });


};
