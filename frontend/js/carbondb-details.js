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


        const table_td_string = measurements.data.map(subArr => `
            <tr>

                    <td>${subArr[6]}</td>
                    <td>${subArr[7].toFixed(4)}</td>
                    <td>${subArr[8].toFixed(4)}</td>
                    <td>${subArr[9]}</td>
                    <td>${subArr[10]}</td>
            <tr>
        `).join(' ');

        $("#energy_table").html(`
        <table class="ui table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Energy in J</th>
                <th>CO2eq in g</th>
                <th>Carbon Intensity</th>
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
