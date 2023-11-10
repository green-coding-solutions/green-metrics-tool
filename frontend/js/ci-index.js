(async () => {
    try {
        var api_data = await makeAPICall('/v1/ci/projects');
    } catch (err) {
        showNotification('Could not get data from API', err);
        return;
    }

    const projectsTableBody = document.querySelector('#projects-table tbody');
    let currentRepoRow = null; // Track the current repository row

    api_data.data.forEach(el => {
        const repo = el[0];
        const branch = el[1];
        const workflow_id = el[2];
        const source = el[3];
        const last_run = el[4];
        let workflow_name = el[5];

        if (workflow_name == '' || workflow_name == null) {
            workflow_name = workflow_id;
        }

        const repo_esc = escapeString(repo);
        // Check if it's a new repository
        if (currentRepoRow === null || currentRepoRow.repo !== repo_esc) {
            // Create a row for the repository with an accordion
            currentRepoRow = projectsTableBody.insertRow();
            currentRepoRow.repo = repo_esc;
            currentRepoRow.innerHTML = `
                <td>
                    <div class="ui accordion" style="width: 100%;">
                        <div class="title">
                            <i class="dropdown icon"></i>
                            ${getRepoLink(repo_esc, source)}
                        </div>
                        <div class="content">
                            <table class="ui sortable celled striped table">
                                <thead class="full-width">
                                    <tr>
                                        <th>Workflow</th>
                                        <th>Branch</th>
                                        <th>Last Run</th>
                                        <th>Workflow ID</th>
                                        <th>Source</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                        </div>
                    </div>
                </td>
            `;
        }

        const content = currentRepoRow.querySelector('.content table tbody');

        // Add branch as a row within the accordion content
        const branchRow = content.insertRow();
        branchRow.innerHTML = `
            <td class="td-index"><a href="/ci.html?repo=${repo}&branch=${branch}&workflow=${workflow_id}">${escapeString(workflow_name)}</a></td>
            <td>${escapeString(branch)}</td>
            <td class="td-index" style="width: 120px">${dateToYMD(new Date(last_run))}</td>
            <td class="td-index">${escapeString(workflow_id)}</td>
            <td class="td-index" title="${escapeString(source)}">${escapeString(source)}</td>
        `;
    });

    // Initialize the accordion
    $('.ui.accordion').accordion();
})();

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
