(async () => {

    try {

        var api_data = await makeAPICall(`/v1/repositories?${getFilterQueryStringFromURI()}`)
    } catch (err) {
        showNotification('Could not get data from API', err);
        return
    }


    api_data.data.forEach(el => {

        const uri = el[0]
        let uri_link = replaceRepoIcon(uri);

        if (uri.startsWith("http")) {
            uri_link = `${uri_link} <a href="${uri}"><i class="icon external alternate"></i></a>`;
        }


        let row = document.querySelector('#repositories-table tbody').insertRow()
        row.innerHTML = `
            <td>
                <div class="ui accordion" style="width: 100%;">
                  <div class="title">
                    <i class="dropdown icon"></i> ${uri_link}
                  </div>
                  <div class="content" data-uri="${uri}">
                      <table class="ui sortable celled striped table"></table>
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
})();
