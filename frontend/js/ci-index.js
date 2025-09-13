async function getRepositories(sort_by = 'date') {
    try {
        var api_data = await makeAPICall(`/v1/ci/repositories?sort_by=${sort_by}`)
    } catch (err) {
        showNotification('Could not get data from API', err);
        return;
    }

    const table_body = document.querySelector('#ci-repositories-table tbody');
    table_body.innerHTML = '';

    api_data.data.forEach(el => {
        const repo = el[0];
        const source = el[1];
        const last_run = el[2];

        let row = table_body.insertRow()
        row.innerHTML = `
            <td>
                <div class="ui accordion" style="width: 100%;">
                  <div class="title">
                    <i class="dropdown icon"></i> ${getRepoLink(repo, source)} <!-- raw values: function handles escaping internally -->
                    <span class="ui label right icon" style="float: right;">${dateToYMD(new Date(last_run), short=true)}<i class="clock icon"></i></span>
                  </div>

                  <div class="content" data-uri="${escapeString(repo)}">
                      <table class="ui celled striped table"></table>
                  </div>
                </div>
            </td>`;
    });
    $('.ui.accordion').accordion({
        onOpen: async function(value, text) {
            const table = this.querySelector('table');

            if(!$.fn.DataTable.isDataTable(table)) {
                const repo = this.getAttribute('data-uri');
                await getCIRunsTable($(table), `/v1/ci/runs?repo=${repo}`, false, false, true)
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

    return `<i class="icon ${iconClass}"></i>${escapeString(repo)} <a href="${getRepoUri(repo, source)}"><i class="icon external alternate"></i></a>`;
}

// Function to generate the repository URI
function getRepoUri(repo, source) {
    if (source.startsWith('github')) {
        return `https://www.github.com/${encodeURIComponent(repo)}`;
    } else if (source.startsWith('gitlab')) {
        return `https://www.gitlab.com/${encodeURIComponent(repo)}`;
    } else if (source.startsWith('bitbucket')) {
        return `https://bitbucket.com/${encodeURIComponent(repo)}`;
    }
}

const getCIRunsTable = async (el, url, include_uri=true, include_button=true, searching=false) => {

    let ci_data = null;
    try {
        ci_data = await makeAPICall(url);
    } catch (err) {
        showNotification('Could not get CI data from API', err);
        return
    }

    const columns = [
        {
            data: 0, title: 'Workflow', render: function(el,type,row) {
                return `<a href="/ci.html?repo=${encodeURIComponent(row[0])}&branch=${encodeURIComponent(row[1])}&workflow=${encodeURIComponent(row[2])}">${escapeString(row[5])}</a>`;
            }
        },
        {data : 1, title: 'Branch'},
        {data: 3, title: 'Source'},

        {
            data: 4, title: 'Last Run', render: function(el, type, row) {
                return `<span title=${el}>${dateToYMD(new Date(el), short=true)}</span>`;
            }
        },
        {
            title: 'Carbon', render: function(el,type,row) {
                return `<img src="${API_URL}/v1/ci/badge/get?repo=${encodeURIComponent(row[0])}&branch=${encodeURIComponent(row[1])}&workflow=${encodeURIComponent(row[2])}&mode=totals&metric=carbon&duration_days=30" onerror="this.src='/images/no-data-badge.webp'">`;
            }
        },

    ]
    el.DataTable({
        // searchPanes: {
        //     initCollapsed: true,
        // },
        searching: searching,
        data: ci_data.data,
        columns: columns,
        deferRender: true,
        order: [[columns.length-2, 'desc']], // API also orders, but we need to indicate order for the user
    });
}

(async () => {
    sortDate();
})();