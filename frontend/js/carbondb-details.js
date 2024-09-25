$(document).ready(function () {
    function getURLParameter(name) {
        return new URLSearchParams(window.location.search).get(name);
    }

    (async () => {
        const machine_uuid = getURLParameter('machine_uuid')
        try {

            var measurements = await makeAPICall(`/v1/carbondb/machine/day/${machine_uuid}`);
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }
        if (measurements.data.length == 0){
            showNotification('No data', 'We could not find any data. Did you follow a correct URL?')
            return
        }

        let types = new Set();
        let companies = new Set();
        let machines = new Set();
        let projects = new Set();
        let tags = new Set();

        measurements.data.forEach(item => {
            types.add(item[1]);
            companies.add(item[2]);
            machines.add(item[3]);
            projects.add(item[4]);
            item[5]?.forEach(tag => tags.add(tag));
        });

        types = Array.from(types);
        companies = Array.from(companies);
        machines = Array.from(machines);
        projects = Array.from(projects);
        tags = Array.from(tags);

        let info_string = ``

        if (types.length > 0){
            info_string += `
            <div class="item">
                <div class="content">
                    <b>Type</b>: ${types.map(c => `${c} `).join('')}
                </div>
            </div>
            `
        }
        if (companies.length > 0){
            info_string += `
            <div class="item">
                <div class="content">
                    <b>Company:</b> ${companies.map(c => `<a href="/carbondb-lists.html?company_uuid=${c}">${c}</a><br>`).join('')}
                </div>
            </div>
            `
        }
        if (projects.length > 0){
            info_string += `
            <div class="item">
                <div class="content">
                    <b>Project</b>: ${projects.map(c => `<a href="/carbondb-lists.html?project_uuid=${c}">${c}</a><br>`).join('')}
                </div>
            </div>
            `
        }
        if (tags.length > 0){
            info_string += `
            <div class="item">
                <div class="content">
                    <b>Tags:</b> ${tags.map(c => `<div class="ui tag label">${c}</div>`).join('')}
                </div>
            </div>
            `
        }

        $('#detail_list').append(info_string);

        const table_td_string = measurements.data.map(subArr => `
            <tr>

                    <td>${subArr[6]}</td>
                    <td>${subArr[7].toFixed(4)}</td>
                    <td>${subArr[8].toFixed(4)}</td>
                    <td>${subArr[9].toFixed(2)}</td>
                    <td>${subArr[10]}</td>
            <tr>
        `).join(' ');

        $("#energy_table").html(`
        <table class="ui table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Energy (J)</th>
                <th>CO2eq (g)</th>
                <th>Intensity (gCO2e/kWh)</th>
                <th>Records</th>
            </tr>
        </thead>
        <tbody>
            ${table_td_string}
        </tbody>
        </table>
        `)

        let sumEnergy = 0;
        let sumCO2 = 0;
        let sumCount = 0;
        let sumCarbonIntensity = 0;

        measurements.data.forEach(item => {
            sumEnergy += item[7];
            sumCO2 += item[8];
            sumCount += item[10];
            sumCarbonIntensity += item[9];
        });

        const averageCarbonIntensity = sumCarbonIntensity / measurements.data.length;

        $("#sum_energy").html(sumEnergy.toFixed(2));
        $("#sum_co2eq").html(sumCO2.toFixed(6));
        $("#sum_records").html(sumCount);
        $("#avg_carbon_intensity").html(averageCarbonIntensity.toFixed(0));

    })();
});
