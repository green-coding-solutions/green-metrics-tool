async function getRepositories(sort_by = 'date') {
    try {
        var api_data = await makeAPICall(`/v1/repositories?${getFilterQueryStringFromURI()}&sort_by=${sort_by}`)
    } catch (err) {
        showNotification('Could not get data from API', err);
        return
    }

    const table_body = document.querySelector('#repositories-table tbody')
    table_body = .innerHTML = '';

    api_data.data.forEach(el => {

        const uri = el[0];
        const last_run = el[1];
        let uri_link = replaceRepoIcon(uri);

        if (uri.startsWith("http")) {
            uri_link = `${uri_link} <a href="${uri}"><i class="icon external alternate"></i></a>`;
        }

        let row = table_body.insertRow()
        row.innerHTML = `
            <td>
                <div class="ui accordion" style="width: 100%;">
                  <div class="title">
                    <i class="dropdown icon"></i> ${uri_link}
                    <span class="ui label float-right"><i class="clock icon"></i> ${dateToYMD(new Date(last_run), short=true)}</span>
                  </div>
                  <div class="content" data-uri="${uri}">
                      <table class="ui celled striped table"></table>
                  </div>
                </div>
            </td>`;
    });
    $('.ui.accordion').accordion({
        onOpen: function(value, text) {
            const table = this.querySelector('table');

            if(!$.fn.DataTable.isDataTable(table)) {
                const uri = this.getAttribute('data-uri');
                getRunsTable($(table), `${API_URL}/v1/runs?uri=${uri}`, false, false, true)
            }
    }});
}

(async () => {
    await sortDate();
})();
