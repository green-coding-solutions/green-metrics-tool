

const compareButton = () => {
    const checkedBoxes = document.querySelectorAll('input[type=checkbox]:checked');

    let link = '/compare.html?ids='

    checkedBoxes.forEach(checkbox => {
        link = `${link}${checkbox.value},`;
    });
    link = link.substr(0,link.length-1);

    if (localStorage.getItem('expert_compare_mode') === 'true'){
        const value = document.querySelector('#compare-force-mode').value;
        link = `${link}&force_mode=${value}`
        localStorage.setItem('expert_compare_mode_last_value', value);
    }

    window.open(link, '_blank');
}

const unselectHandler = () => {
    document.querySelectorAll('input[type="checkbox"]').forEach(el => {
        el.checked = '';
    })
    updateCompareCount();
}
const updateCompareCount = () => {
    const countButton = document.querySelector('#compare-button');
    const checkedCount = document.querySelectorAll('input[type=checkbox]:checked').length;
    countButton.textContent = `Compare: ${checkedCount} Run(s)`;
    if (checkedCount === 0) {
        document.querySelector('#unselect-button').style.display = 'none';
        if (localStorage.getItem('expert_compare_mode') === 'true') {
            document.querySelector('#compare-force-mode').style.display = 'none';
        }

    } else {
        document.querySelector('#unselect-button').style.display = 'block';
        if (localStorage.getItem('expert_compare_mode') === 'true') {
            document.querySelector('#compare-force-mode').style.display = 'block';
        }

    }
}

let lastChecked = null;

function handleCheckboxClick(e){
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    if (lastChecked && e.shiftKey) {
        let inBetween = false;
        checkboxes.forEach(checkbox => {
            if (checkbox === this || checkbox === lastChecked) {
                inBetween = !inBetween;
            }

          if (inBetween) {
            checkbox.checked = this.checked;
          }
        })
    }
    lastChecked = this;
};

const allow_group_select_checkboxes = () => {

    const checkboxes = document.querySelectorAll('input[type="checkbox"]');

    checkboxes.forEach(checkbox => {
        checkbox.removeEventListener('click', handleCheckboxClick);
        checkbox.addEventListener('click', handleCheckboxClick);
    });
}



const removeFilter = (paramName) => {
    const urlSearchParams = new URLSearchParams(window.location.search);
    urlSearchParams.delete(paramName);
    const newUrl = `${window.location.pathname}?${urlSearchParams.toString()}`;
    window.location.href = newUrl;
}


const getFilterQueryStringFromURI = () => {
    const url_params = getURLParams();

    let query_string = '';
    if (url_params['uri'] != null && url_params['uri'].trim() != '') {
        const uri = url_params['uri'].trim()
        query_string += `&uri=${uri}`
        document.querySelector('input[name=uri]').value = uri;
        document.querySelector('#filters-active').classList.remove('hidden');
    }
    if (url_params['filename'] != null && url_params['filename'].trim() != '') {
        const filename = url_params['filename'].trim()
        query_string += `&filename=${filename}`
        document.querySelector('input[name=filename]').value = filename;
        document.querySelector('#filters-active').classList.remove('hidden');
    }
    if (url_params['branch'] != null && url_params['branch'].trim() != '') {
        const branch = url_params['branch'].trim()
        query_string += `&branch=${branch}`
        document.querySelector('input[name=branch]').value = branch;
        document.querySelector('#filters-active').classList.remove('hidden');
    }
    if (url_params['machine_id'] != null && url_params['machine_id'].trim() != '') {
        const machine_id = url_params['machine_id'].trim()
        query_string += `&machine_id=${machine_id}`
        document.querySelector('input[name=machine_id]').value = machine_id;
        document.querySelector('#filters-active').classList.remove('hidden');
    }
    if (url_params['machine'] != null && url_params['machine'].trim() != '') {
        const machine = url_params['machine'].trim()
        query_string += `&machine=${machine}`
        document.querySelector('input[name=machine]').value = machine;
        document.querySelector('#filters-active').classList.remove('hidden');
    }
    if (url_params['usage_scenario_variables'] != null && url_params['usage_scenario_variables'].trim() != '') {
        const usage_scenario_variables = url_params['usage_scenario_variables'].trim()
        query_string += `&usage_scenario_variables=${usage_scenario_variables}`
        document.querySelector('input[name=usage_scenario_variables]').value = usage_scenario_variables;
        document.querySelector('#filters-active').classList.remove('hidden');
    }

    return query_string
}

const getFilterQueryStringFromInputs = () => {
    let query_string = '';

    const uri = document.querySelector('input[name=uri]').value.trim()
    const filename = document.querySelector('input[name=filename]').value.trim()
    const branch = document.querySelector('input[name=branch]').value.trim()
    const machine = document.querySelector('input[name=machine]').value.trim()
    const machine_id = document.querySelector('input[name=machine_id]').value.trim()
    const usage_scenario_variables = document.querySelector('input[name=usage_scenario_variables]').value.trim()
    const show_archived = document.querySelector('input[name=show_archived]:checked').value.trim()

    if(uri != '') query_string += `&uri=${uri}`
    if(filename != '') query_string += `&filename=${filename}`
    if(branch != '') query_string += `&branch=${branch}`
    if(machine != '') query_string += `&machine=${machine}`
    if(machine_id != '') query_string += `&machine_id=${machine_id}`
    if(usage_scenario_variables != '') query_string += `&usage_scenario_variables=${usage_scenario_variables}`
    if(show_archived) query_string += `&show_archived=${show_archived}`

    document.querySelector('#filters-active').classList.remove('hidden');

    return query_string
}

async function getRepositories(sort_by = 'date') {
    try {
        var api_data = await makeAPICall(`/v1/repositories?${getFilterQueryStringFromURI()}&sort_by=${sort_by}`)
    } catch (err) {
        showNotification('Could not get data from API', err);
        return
    }

    const table_body = document.querySelector('#runs-and-repos-table tbody')
    table_body.innerHTML = '';

    api_data.data.forEach(el => {

        const uri = el[0];
        const last_run = el[1];
        let uri_link = replaceRepoIcon(uri);

        uri_link = `${uri_link} ${createExternalIconLink(uri)}`;

        let row = table_body.insertRow()
        row.innerHTML = `
            <td>
                <div class="ui accordion repositories" style="width: 100%;">
                  <div class="title">
                    <i class="dropdown icon"></i> ${uri_link}
                    <span class="ui label float-right"><i class="clock icon"></i> ${dateToYMD(new Date(last_run), short=true)}</span>
                  </div>
                  <div class="content" data-uri="${escapeString(uri)}">
                      <table class="ui celled striped table"></table>
                  </div>
                </div>
            </td>`;
    });
    $('.ui.accordion.repositories').accordion({
        onOpen: function(value, text) {
            const table = this.querySelector('table');

            if(!$.fn.DataTable.isDataTable(table)) {
                const uri = this.getAttribute('data-uri');
                getRunsTable($(table), `/v2/runs?uri=${uri}&uri_mode=exact&limit=0`, false, false, true)
            }
    }});
    $('.ui.accordion.filter-dropdown').hide();
}

const getRunsTable = async (el, url, include_uri=true, include_button=true, searching=false) => {

    let runs = null;
    el.DataTable().clear().destroy() // clear old

    try {
        runs = await makeAPICall(url)
    } catch (err) {
        showNotification('Could not get run data from API', err);
        return
    }

    const columns = [
        {
            data: 1,
            title: 'Name',
            render: function(el, type, row) {

                el = escapeString(el);

                // Show status labels based on run state
                if(row[11] == true) el = `${el} <span class="ui red horizontal label">Failed</span>`;
                else if(row[10] == null) el = `${el} (in progress 🔥)`;

                // Show warning label if warnings exist
                if(row[5] != 0) el = `${el} <span class="ui yellow horizontal label" title="${row[5]}">Warnings</span>`;

                return `<a href="/stats.html?id=${row[0]}" target="_blank">${el}</a>`
            },
        },
    ]

    if(include_uri) {
        columns.push({
                data: 2,
                title: '(<i class="icon code github"></i> / <i class="icon code gitlab"></i> / <i class="icon code folder"></i> etc.) Repo',
                render: function(el, type, row) {
                    let uri_link = replaceRepoIcon(el);

                    uri_link = `${uri_link} ${createExternalIconLink(el)}`;
                    return uri_link
                },
        })
    }

    columns.push({ data: 3, title: '<i class="icon code branch"></i>Branch', render: (el, type, row) => escapeString(el) });

    columns.push({
        data: 9,
        title: '<i class="icon history"></i>Commit</th>',
        render: function(el, type, row) {
          // Modify the content of the "Name" column here
          return el == null ? null : `${escapeString(el.substr(0,3))}...${escapeString(el.substr(-3,3))}`
        },
    });

    columns.push({
        data: 6,
        title: '<i class="icon file alternate"></i>Filename',
        render: function(el, type, row) {
            const usage_scenario_variables = Object.entries(row[7]).map(([k, v]) => `<span class="ui label">${escapeString(k)}=${escapeString(v)}</span>`);
            return `${escapeString(el)} ${usage_scenario_variables.join(' ')}`
        }
    });
    columns.push({ data: 8, title: '<i class="icon laptop code"></i>Machine</th>', render: (el, type, row) => escapeString(el) });
    columns.push({
        data: 4,
        title: '<i class="icon calendar"></i>Last run</th>',
        render: function(el, type, row) {
            if (el == null) return '-';
            let usage_scenario_variables = Object.entries(row[7]).map(([k, v]) => typeof(v) == 'number' ? `"${k}": ${v}` : `"${k}": ${JSON.stringify(v)}`).join(', ')
            usage_scenario_variables = `{${usage_scenario_variables}}`

            return `${dateToYMD(new Date(el))}<br><a href="/timeline.html?uri=${encodeURIComponent(row[2])}&amp;branch=${encodeURIComponent(row[3])}&amp;machine_id=${row[12]}&amp;filename=${encodeURIComponent(row[6])}&amp;usage_scenario_variables=${encodeURIComponent(usage_scenario_variables)}&amp;metrics=key" class="ui teal horizontal label  no-wrap"><i class="ui icon clock"></i>History &nbsp;</a>`;

        }
    });

    columns.push({
        data: 0,
        render: function(el, type, row) {
            // Modify the content of the "Name" column here
            return `<input type="checkbox" value="${el}" name="chbx-proj"/>&nbsp;`
        }
    });

    el.DataTable({
        // searchPanes: {
        //     initCollapsed: true,
        // },
        searching: searching,
        data: runs.data,
        columns: columns,
        deferRender: true,
        layout: {
    topStart: '',
    topEnd: '',
    bottomStart: 'pageLength',
    bottomEnd: 'paging'
},
        drawCallback: function(settings) {
            document.querySelectorAll('input[type="checkbox"]').forEach((e) =>{
                e.removeEventListener('change', updateCompareCount);
                e.addEventListener('change', updateCompareCount);
            })
            document.querySelector('#unselect-button').removeEventListener('click', unselectHandler);
            document.querySelector('#unselect-button').addEventListener('click', unselectHandler)
            allow_group_select_checkboxes();
            updateCompareCount();
        },
        order: [[columns.length-2, 'desc']] // API also orders, but we need to indicate order for the user
    });

}

(async () => {

    const url_params = getURLParams();

    document.querySelector('#home-toggle-button').addEventListener('click', el => {
        if (el.currentTarget.innerText === 'Switch to repository view') {
            document.querySelector('h1.ui.header span').innerText = 'ScenarioRunner - Repositories';
            localStorage.setItem('scenario_runner_data_shown', 'repositories');
            history.replaceState(null, '', window.location.pathname); // clear any filters if any set
            window.location.reload();
        } else {
            document.querySelector('h1.ui.header span').innerText = 'ScenarioRunner - Last 50 Runs';
            localStorage.setItem('scenario_runner_data_shown', 'last_runs');
            history.replaceState(null, '', window.location.pathname); // clear any filters if any set
            window.location.reload();
        }
    });

    if (url_params['show'] === 'repositories' || localStorage.getItem('scenario_runner_data_shown') === 'repositories') {
        document.querySelector('#runs-and-repos-table-title').innerText = 'Repositories';
        document.querySelector('#home-toggle-button').innerText = 'Switch to last runs view';
        document.querySelector('h1.ui.header span').innerText = 'ScenarioRunner - Repositories';
        document.querySelector('#scenario-runner-runs-description')?.remove();
        sortDate();
    } else {
        document.querySelector('#scenario-runner-repositories-description')?.remove();
        document.querySelector('#sort-button').remove()
        getRunsTable($('#runs-and-repos-table tbody table'), `/v2/runs?${getFilterQueryStringFromURI()}&limit=50`)
    }

    if (localStorage.getItem('expert_compare_mode') === 'true') {
        const value = localStorage.getItem('expert_compare_mode_last_value');
        if (value != null) {
            const el = document.querySelector('#compare-force-mode');
            el.value = value;
        }
    }

    // filters
    $('.ui.accordion.filter-dropdown').accordion();
    $('form').on('submit', async function (e) {
        e.preventDefault();
        const query_string = getFilterQueryStringFromInputs()
        getRunsTable($('#runs-and-repos-table tbody table'), `/v2/runs?${query_string}&limit=0`)
        history.pushState(null, '', `${window.location.origin}${window.location.pathname}?${query_string}`); // replace URL to bookmark!
        $('.ui.accordion.filter-dropdown').accordion('close', 0);
        return false;
    });
    $('button[name=clear]').on('click', async function () {
        history.replaceState(null, '', window.location.pathname);
        document.querySelectorAll('input.filter-option').forEach((el) => {
            el.value = '';
        })
        getRunsTable($('#runs-and-repos-table tbody table'), `/v2/runs?limit=50`)
        $('.ui.accordion').accordion('close', 0);
        document.querySelector('#filters-active').classList.add('hidden');
    });


})();