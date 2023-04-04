const getURLParams = () => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))
    return url_params;
}

$(document).ready( (e) => {
    (async () => {

        let url_params = getURLParams();
        if(url_params.get('ids') == null
            || url_params.get('ids') == ''
            || url_params.get('ids') == 'null') {
            showNotification('No ids', 'ids parameter in URL is empty or not present. Did you follow a correct URL?');
            throw "Error";
        }

        try {
            params = url_params.getAll('ids');
            let api_url = '/v1/compare?ids=';
            params.forEach( id => {
                api_url = `${api_url}${id}`
            });
            var phase_stats_data = await makeAPICall(api_url)
            phase_stats_data = phase_stats_data.data;
        } catch (err) {
            showNotification('Could not get compare in-repo data from API', err);
        }

        if (phase_stats_data == undefined) return;

        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>URI</strong></td><td><a href="${url_params.get('uri')}" target="_blank">${url_params.get('uri')}</a></td></tr>`)
        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Machine-ID</strong></td><td>${url_params.get('machine_id')}</td></tr>`)

        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Type</strong></td><td>${phase_stats_data.comparison_type}</a></td></tr>`)
        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${phase_stats_data.comparison_type}</strong></td><td>${phase_stats_data.comparison_details.join(' vs. ')}</a></td></tr>`)

        displayComparisonMetrics(phase_stats_data.data, phase_stats_data.comparison_type);

    })();
});

