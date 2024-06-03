$(document).ready(function () {

    function getQueryParameters(name) {
        const urlParams = new URLSearchParams(window.location.search);
        const allParams = urlParams.getAll(name);
        return [...new Set(allParams)];
    }

    function filterDataByTags(m) {
        const tags = getQueryParameters('tag');

        if (tags.length > 0) {
            return m.data.filter(item => {
                return tags.every(tag => item[4].includes(tag));
            });
        }

        return m.data;
    }

    (async () => {
        $('#filter_tags_container').hide();

        const company_uuid = getQueryParameters('company_uuid')[0];
        const project_uuid = getQueryParameters('project_uuid')[0];

        if(company_uuid){
            var query_string = 'company';
            var query_param = company_uuid;
        }else if(project_uuid){
            var query_string = 'project';
            var query_param = project_uuid;
        }else{
            showNotification('No company or project supplied as parameter. Dowing nothing!');
            return;
        }

        try {
            var measurements = await makeAPICall(`/v1/carbondb/${query_string}/${query_param}`);
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }

        if (measurements.data.length == 0){
            showNotification('No data', 'We could not find any data. Did you follow a correct URL?')
            return
        }

        measurements = filterDataByTags(measurements);

        const ftags = getQueryParameters('tag');
        if (ftags.length > 0) {
            $('#filter_tags_container').show();
            const tagsFilterHtml = ftags.map(tag => `<a class="ui tag label" href="${window.location}&tag=${escapeString(tag)}">${escapeString(tag)}</a>`).join(' ');
            $('#filter_tags').append(tagsFilterHtml);
            $('#js_remove_filters').click(function(){
                const url = new URL(window.location.href);
                const newParams = new URLSearchParams();
                url.searchParams.forEach((value, key) => {
                    if (key !== 'tag') {
                        newParams.append(key, value);
                    }
                });
                window.location.href = `${url.origin}${url.pathname}?${newParams.toString()}`;
            })
        }

        const table_td_string = measurements.map(subArr => {
            const tagsHtml = subArr[4]
                .filter(tag => tag !== null)
                .map(tag => `<a class="ui tag label" href="${window.location}&tag=${escapeString(tag)}">${escapeString(tag)}</a>`)
                .join(' ');

            return `
                <tr>
                    <td><a href='/carbondb-details.html?machine_uuid=${subArr[0]}'>${subArr[0]}</a></td>
                    <td>${subArr[1].toFixed(2)}</td>
                    <td>${subArr[2].toFixed(2)}</td>
                    <td>${subArr[3].toFixed(2)}</td>
                    <td>${tagsHtml}</td>
                </tr>
            `;
        }).join(' ');

        $("#energy_table").html(`
        <table class="ui table">
        <thead>
            <tr>
                <th>Machine</th>
                <th>Sum Energy (J)</th>
                <th>Sum CO2eq (g)</th>
                <th>Avg. Intensity (gCO2e/kWh)</th>
                <th>Tags (click to filter)<th>
            </tr>
        </thead>
        <tbody>
            ${table_td_string}
        </tbody>
        </table>
        `)

        let sumEnergy = 0;
        let sumCO2 = 0;

        // In this case we can't calculate the carbon intensity as this would be averages from averages
        //let sumCarbonIntensity = 0;

        measurements.forEach(item => {
            sumEnergy += item[1];
            sumCO2 += item[2];
        });

        $("#sum_energy").html(sumEnergy.toFixed(2));
        $("#sum_co2eq").html(sumCO2.toFixed(2));

    })();
});
