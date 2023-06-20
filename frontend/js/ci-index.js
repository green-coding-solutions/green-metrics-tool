(async () => {
    try {
        var api_data = await makeAPICall('/v1/ci/projects')
    } catch (err) {
            showNotification('Could not get data from API', err);
            return;
    }
    api_data.data.forEach(el => {

        const repo = el[0]
        const branch = el[1]
        const workflow = el[2]
        const source = el[3]

        let uri_display = repo;
        let uri = repo;

        if (source == 'github'){
            uri_display = `<i class="icon github"></i>${repo}`;
            uri = `https://www.github.com/${repo}`;
        } else if (source == 'gitlab'){
            uri_display = `<i class="icon gitlab"></i>${repo}`;
            uri = `https://www.gitlab.com/${repo}`;
        } else if (source == 'bitbucket'){
            uri_display = `<i class="icon bitbucket"></i>${repo}`;
            uri = `https://bitbucket.com/${repo}`;
        } 

        console.log(uri_display);
        uri_link = `${uri_display} <a href="${uri}"><i class="icon external alternate"></i></a>`;


        // insert new accordion row if repository not known
        let td_node = document.querySelector(`td[data-uri='${uri}_${branch}']`)
        if (td_node == null || td_node == undefined) {
            let row = document.querySelector('#projects-table tbody').insertRow()
            row.innerHTML = `
                <td data-uri="${uri}_${branch}">
                    <div class="ui accordion" style="width: 100%;">
                      <div class="title">
                        <i class="dropdown icon"></i> ${uri_link}
                      </div>
                      <div class="content">
                      </div>
                    </div>
                </td>`;
            let content = document.querySelector(`#projects-table td[data-uri='${uri}_${branch}'] div.content`);
            content.innerHTML = `
                <table class="ui table">
                    <thead class="full-width">
                        <tr>
                            <th>Workflow</th>
                            <th>Branch</th>
                            <th>Source</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>`;
        }


        let inner_row = document.querySelector(`#projects-table td[data-uri='${uri}_${branch}'] div.content table tbody`).insertRow();

        inner_row.innerHTML = `
            <td class="td-index"><a href="/ci.html?repo=${repo}&branch=${branch}&workflow=${workflow}">${workflow}</a></td>
            <td class="td-index" title="${branch}">${branch}</td>
            <td class="td-index" title="${source}">${source}</td>`;

    });

    $('.ui.accordion').accordion();
    $('#projects-table table').tablesort();

})();