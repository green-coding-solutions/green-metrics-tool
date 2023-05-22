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
            var phase_stats_data = (await makeAPICall(api_url)).data
        } catch (err) {
            showNotification('Could not get compare in-repo data from API', err);
        }

        if (phase_stats_data == undefined) return;

        let comparison_details = phase_stats_data.comparison_details.map((el) => replaceRepoIcon(el));
        comparison_details = comparison_details.join(' vs. ')
        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Type</strong></td><td>${phase_stats_data.comparison_case}</td></tr>`)
        document.querySelector('#project-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${phase_stats_data.comparison_case}</strong></td><td>${comparison_details}</td></tr>`)

        let multi_comparison = determineMultiComparison(phase_stats_data.comparison_case)
        setupPhaseTabs(phase_stats_data, multi_comparison)
        displayComparisonMetrics(phase_stats_data, phase_stats_data.comparison_case, multi_comparison)

    })();
});

