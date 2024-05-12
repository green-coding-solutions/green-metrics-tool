async function getRepositories(sort_by = 'date') {
    try {
        var api_data = await makeAPICall(`/v1/ci/repositories?sort_by=${sort_by}`)
    } catch (err) {
        showNotification('Could not get data from API', err);
        return;
    }

    const table_body = document.querySelector('#repositories-table tbody');
    table_body.innerHTML = '';

    api_data.data.forEach(el => {
        const repo = el[0]; // escaping not needed, as done in API ingest
        const source = el[1]; // escaping not needed, as done in API ingest
        const last_run = el[2]; // escaping not needed, as done in API ingest


        let row = table_body.insertRow()
        row.innerHTML = `
            <td>
                <div class="ui accordion" style="width: 100%;">
                  <div class="title">
                    <i class="dropdown icon"></i> ${getRepoLink(repo, source)}
                    <span class="ui label right icon" style="float: right;">${dateToYMD(new Date(last_run), short=true)}<i class="clock icon"></i></span>
                  </div>

                  <div class="content" data-uri="${repo}">
                      <table class="ui celled striped table"></table>
                  </div>
                </div>
            </td>`;
    });
    $('.ui.accordion').accordion({
        onOpen: function(value, text) {
            const table = this.querySelector('table');

            if(!$.fn.DataTable.isDataTable(table)) {
                const repo = this.getAttribute('data-uri');
                getCIRunsTable($(table), `${API_URL}/v1/ci/runs?repo=${repo}`, false, false, true)
            }
    }});
};



// Function to generate the repository link
function getRepoLink(repo, source) {
    let iconClass = '';
    if (source.startsWith('github')) {
        iconClass = 'github';
    } else if (source.startsWith('gitlab')) {
        iconClass = 'gitlab';
    } else if (source.startsWith('bitbucket')) {
        iconClass = 'bitbucket';
    }

    // Assumes the repo var is sanitized before being sent to this function
    return `<i class="icon ${iconClass}"></i>${repo} <a href="${getRepoUri(repo, source)}"><i class="icon external alternate"></i></a>`;
}

// Function to generate the repository URI
function getRepoUri(repo, source) {
    if (source.startsWith('github')) {
        return `https://www.github.com/${repo}`;
    } else if (source.startsWith('gitlab')) {
        return `https://www.gitlab.com/${repo}`;
    } else if (source.startsWith('bitbucket')) {
        return `https://bitbucket.com/${repo}`;
    }
}

const getCIRunsTable = (el, url, include_uri=true, include_button=true, searching=false) => {

    const columns = [
        {
            data: 0, title: 'Workflow', render: function(el,type,row) {
                return `<a href="/ci.html?repo=${row[0]}&branch=${row[1]}&workflow=${row[2]}">${row[5]}</a>`;
            }
        },
        {data : 1, title: 'Branch'},
        {data: 2, title: 'Workflow-ID'},
        {data: 3, title: 'Source'},
        {
            data: 4, title: 'Last Run', render: function(el, type, row) {
                return `<span title=${el}}>${dateToYMD(new Date(el), short=true)}</span>`;
            }
        }
    ]
    el.DataTable({
        // searchPanes: {
        //     initCollapsed: true,
        // },
        searching: searching,
        ajax: url,
        columns: columns,
        deferRender: true,
    });
}

(async () => {
    await sortDate();
})();