$(document).ready(function () {
    (async () => {
        getRunsTable($('#runs-table'), `/v1/runs?${getFilterQueryStringFromURI()}&limit=50`)
    })();
});