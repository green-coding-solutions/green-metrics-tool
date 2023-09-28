$(document).ready(function () {
    (async () => {
        getRunsTable($('#runs-table'), `${API_URL}/v1/runs?${getFilterQueryStringFromURI()}&limit=50`)
    })();
});