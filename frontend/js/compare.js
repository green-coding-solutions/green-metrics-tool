const getURLParams = () => {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))
    return url_params;
}

async function fetchDiff() {
    document.querySelector('#loader-question').remove();
    const url_params = getURLParams();
    document.querySelector('#diff-pre').insertAdjacentHTML('beforebegin', '<h2>Configuration and Settings diff</h2>')
    try {
        let api_url = '/v1/diff?ids=';
        params.forEach( id => {
            api_url = `${api_url}${id}`
        });
        const diff_data = (await makeAPICall(api_url)).data
        document.querySelector('#diff-pre').insertAdjacentHTML('beforeend', diff_data)
    } catch (err) {
        showNotification('Could not get diff data from API', err);
    }
}

$(document).ready( (e) => {
    (async () => {

        const url_params = getURLParams();

        if(url_params.get('ids') == null
            || url_params.get('ids') == ''
            || url_params.get('ids') == 'null') {
            showNotification('No ids', 'ids parameter in URL is empty or not present. Did you follow a correct URL?');
            throw "Error";
        }

        params = url_params.getAll('ids');
        const runs = params[0].split(",").length
        try {
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
        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Type</strong></td><td>${phase_stats_data.comparison_case}</td></tr>`)
        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Number of runs compared</strong></td><td>${runs}</td></tr>`)
        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${phase_stats_data.comparison_case}</strong></td><td>${comparison_details}</td></tr>`)
        Object.keys(phase_stats_data['common_info']).forEach(function(key) {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${key}</strong></td><td>${phase_stats_data['common_info'][key]}</td></tr>`)
          });

        document.querySelector('#fetch-diff').addEventListener('click', fetchDiff);

        displayComparisonMetrics(phase_stats_data)

    })();
});

