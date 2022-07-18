(async function() {
    const query_string = window.location.search;
    const url_params = (new URLSearchParams(query_string))

    if (!url_params.has('pid[]')) {
      showNotification("No data to display", "Please supply project ids in URL");
      return;
    }
    try {
        let params = url_params.getAll('pid[]');
        let api_url = '/v1/stats/multi?dummy=dummy'
        params.forEach(pid => {
          api_url += '&p=' + pid
        });
        let stats_data = await makeAPICall(api_url)
    } catch (err) {
        showNotification('Could not get data from API', err);
        return;
    }
})();
