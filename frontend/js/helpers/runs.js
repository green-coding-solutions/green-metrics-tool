

// Tables are paginated server-side, so checkboxes of other pages are not in the DOM.
// We thus keep the selection separately to be able to compare runs across pages.
const selected_run_ids = new Set();

const compareButton = () => {
    syncSelectedRunIds();
    const ids = Array.from(selected_run_ids).join(',');

    const value = document.querySelector('#compare-force-mode').value;
    localStorage.setItem('compare_mode_last_value', value);

    let link;
    if (value === 'simple_table') {
        link = `/compare-simple.html?ids=${ids}`;
    } else {
        link = `/compare.html?ids=${ids}&force_mode=${value}`;
    }

    window.open(link, '_blank');
}

const unselectHandler = () => {
    document.querySelectorAll('input[type="checkbox"]').forEach(el => {
        el.checked = '';
    })
    selected_run_ids.clear();
    updateCompareCount();
}

const syncSelectedRunIds = () => {
    // checkboxes can also be changed programmatically (shift group select), which fires no change event
    document.querySelectorAll('input[type="checkbox"][name="chbx-proj"]').forEach(el => {
        if (el.checked) selected_run_ids.add(el.value);
        else selected_run_ids.delete(el.value);
    })
}

const updateCompareCount = () => {
    syncSelectedRunIds();
    const countButton = document.querySelector('#compare-button');
    const checkedCount = selected_run_ids.size;
    countButton.textContent = `Compare: ${checkedCount} Run(s)`;
    if (checkedCount === 0) {
        document.querySelector('#compare-force-mode-dropdown').style.visibility = 'hidden';
        document.querySelector('#unselect-button').classList.add('hidden');
    } else {
        document.querySelector('#compare-force-mode-dropdown').style.visibility = 'visible';
        document.querySelector('#unselect-button').classList.remove('hidden');
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


const getFilterQueryStringFromURI = (use_basic_filters=true) => {
    const url_params = getURLParams();

    let query_string = '';

    if (use_basic_filters !== false) {
        if (url_params['name'] != null && url_params['name'].trim() != '') {
            const name = url_params['name'].trim()
            query_string += `&name=${encodeURIComponent(name)}`
            document.querySelector('input[name="name"]').value = name;
            document.querySelector('#filters-active').classList.remove('hidden');
        }
        if (url_params['uri'] != null && url_params['uri'].trim() != '') {
            const uri = url_params['uri'].trim()
            query_string += `&uri=${encodeURIComponent(uri)}`
            document.querySelector('input[name="uri"]').value = uri;
            document.querySelector('#filters-active').classList.remove('hidden');
        }
        if (url_params['filename'] != null && url_params['filename'].trim() != '') {
            const filename = url_params['filename'].trim()
            query_string += `&filename=${encodeURIComponent(filename)}`
            document.querySelector('input[name="filename"]').value = filename;
            document.querySelector('#filters-active').classList.remove('hidden');
        }
        if (url_params['branch'] != null && url_params['branch'].trim() != '') {
            const branch = url_params['branch'].trim()
            query_string += `&branch=${encodeURIComponent(branch)}`
            document.querySelector('input[name="branch"]').value = branch;
            document.querySelector('#filters-active').classList.remove('hidden');
        }
        if (url_params['machine_id'] != null && url_params['machine_id'].trim() != '') {
            const machine_id = url_params['machine_id'].trim()
            query_string += `&machine_id=${encodeURIComponent(machine_id)}`
            document.querySelector('input[name="machine_id"]').value = machine_id;
            document.querySelector('#filters-active').classList.remove('hidden');
        }
        if (url_params['machine'] != null && url_params['machine'].trim() != '') {
            const machine = url_params['machine'].trim()
            query_string += `&machine=${encodeURIComponent(machine)}`
            document.querySelector('input[name="machine"]').value = machine;
            document.querySelector('#filters-active').classList.remove('hidden');
        }
        if (url_params['usage_scenario_variables'] != null && url_params['usage_scenario_variables'].trim() != '') {
            const usage_scenario_variables = url_params['usage_scenario_variables'].trim()
            query_string += `&usage_scenario_variables=${encodeURIComponent(usage_scenario_variables)}`
            document.querySelector('input[name="usage_scenario_variables"]').value = usage_scenario_variables;
            document.querySelector('#filters-active').classList.remove('hidden');
        }
    }

    let show_archived = null;
    if (url_params['show_archived'] != null && url_params['show_archived'].trim() != '') {
        show_archived = url_params['show_archived'].trim()
        document.querySelector('#filters-active').classList.remove('hidden');
    } else if (localStorage.getItem('show_archived')) {
        show_archived = localStorage.getItem('show_archived');
        document.querySelector('#filters-active').classList.remove('hidden');
    } else {
        show_archived = 'false';
    }

    const archived_radio = document.querySelector(`input[name="show_archived"][value="${show_archived}"]`)
    if (archived_radio != null) { // since user can submit bullshit we do not want to except on querySelector after accessing checkes
        archived_radio.checked = true;
        localStorage.setItem('show_archived', show_archived);
        query_string += `&show_archived=${show_archived}`
    }

    let show_other_users = null;
    if (url_params['show_other_users'] != null && url_params['show_other_users'].trim() != '') {
        show_other_users = url_params['show_other_users'].trim()
        document.querySelector('#filters-active').classList.remove('hidden');
    } else if (localStorage.getItem('show_other_users')) {
        show_other_users = localStorage.getItem('show_other_users');
        document.querySelector('#filters-active').classList.remove('hidden');
    } else {
        show_other_users = 'true';
    }

    const other_users_radio = document.querySelector(`input[name="show_other_users"][value="${show_other_users}"]`)
    if (other_users_radio != null) { // since user can submit bullshit we do not want to except on querySelector after accessing checkes
        document.querySelector(`input[name="show_other_users"][value="${show_other_users}"]`).checked = true;
        localStorage.setItem('show_other_users', show_other_users);
        query_string += `&show_other_users=${show_other_users}`
    }

    return query_string
}

const getFilterQueryStringFromInputs = (use_basic_filters=true) => {
    let query_string = '';

    const name = document.querySelector('input[name="name"]').value.trim()
    const uri = document.querySelector('input[name="uri"]').value.trim()
    const filename = document.querySelector('input[name="filename"]').value.trim()
    const branch = document.querySelector('input[name="branch"]').value.trim()
    const machine = document.querySelector('input[name="machine"]').value.trim()
    const machine_id = document.querySelector('input[name="machine_id"]').value.trim()
    const usage_scenario_variables = document.querySelector('input[name="usage_scenario_variables"]').value.trim()
    const show_archived = document.querySelector('input[name="show_archived"]:checked')?.value?.trim()
    localStorage.setItem('show_archived', show_archived);
    const show_other_users = document.querySelector('input[name="show_other_users"]:checked')?.value?.trim()
    localStorage.setItem('show_other_users', show_other_users);

    if (use_basic_filters !== false) {
        if(name != '') query_string += `&name=${encodeURIComponent(name)}`
        if(uri != '') query_string += `&uri=${encodeURIComponent(uri)}`
        if(filename != '') query_string += `&filename=${encodeURIComponent(filename)}`
        if(branch != '') query_string += `&branch=${encodeURIComponent(branch)}`
        if(machine != '') query_string += `&machine=${encodeURIComponent(machine)}`
        if(machine_id != '') query_string += `&machine_id=${encodeURIComponent(machine_id)}`
        if(usage_scenario_variables != '') query_string += `&usage_scenario_variables=${encodeURIComponent(usage_scenario_variables)}`
    }
    if(show_archived != null && show_archived != '') query_string += `&show_archived=${encodeURIComponent(show_archived)}`
    if(show_other_users != null && show_other_users != '') query_string += `&show_other_users=${encodeURIComponent(show_other_users)}`

    document.querySelector('#filters-active').classList.remove('hidden');

    return query_string
}

const PAGE_LENGTH_MAX = 100; // API limit per request
let repositories_sort_by = 'date';

async function getRepositories(sort_by = 'date') {
    repositories_sort_by = sort_by;
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

        uri_link = `<span class="left-side-ellipsis long-ellipsis" title="${escapeString(uri)}">${uri_link}</span> ${createExternalIconLink(uri)}`;

        let row = table_body.insertRow()
        row.innerHTML = `
            <td>
                <div class="ui accordion repositories" style="width: 100%;">
                  <div class="title">
                    <i class="dropdown icon"></i> ${uri_link}
                    <span class="ui label float-right"><i class="clock icon"></i> ${dateToYMD(new Date(last_run), true)}</span>
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
                getRunsTable($(table), `&uri=${encodeURIComponent(uri)}&uri_mode=exact${getFilterQueryStringFromURI(false)}`, false, false, true)
            }
    }});
}

// Fetches one page for a server-side DataTable and returns it in the format DataTables expects
const fetchDataTablesPage = async (path, dt_params, error_message) => {
    const empty_page = { draw: dt_params.draw, data: [], recordsTotal: 0, recordsFiltered: 0 };
    let api_data = null;
    try {
        api_data = await makeAPICall(path);
    } catch (err) {
        if (!(err instanceof APIHTTPError && err.status === 204)) { // 204 just means no results
            showNotification(error_message, err);
        }
        return empty_page;
    }
    return {
        draw: dt_params.draw,
        data: api_data?.data ?? [],
        recordsTotal: api_data?.total ?? 0,
        recordsFiltered: api_data?.total ?? 0,
    };
}

// query_string holds the filters (must start with & or be empty). Paging, sorting and search are added per request.
const getRunsTable = async (el, query_string, include_uri=true, include_button=true, searching=false) => {

    el.data('gmt-query-string', query_string);

    if ($.fn.DataTable.isDataTable(el)) { // filters changed: just reload. ajax.reload also resets to the first page
        el.DataTable().ajax.reload();
        return;
    }

    const columns = [
        {
            data: 1,
            name: 'name', // name is used as order_by value for the API
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

    const parseRelations = (relationsRaw) => {
        if (relationsRaw == null) return {};
        if (typeof(relationsRaw) === 'string') {
            try {
                return JSON.parse(relationsRaw);
            } catch (_) {
                return {};
            }
        }
        if (typeof(relationsRaw) !== 'object') return {};
        return relationsRaw;
    }

    if(include_uri) {
        columns.push({
                data: 2,
                name: 'uri',
                title: '(<i class="icon code github"></i> / <i class="icon code gitlab"></i> / <i class="icon code folder"></i> etc.) Repo',
                render: function(el, type, row) {
                    let uri_link = replaceRepoIcon(el);
                    const ext_link = createExternalIconLink(el);

                    uri_link = `<span class="left-side-ellipsis long-ellipsis" title="${escapeString(el)}">${uri_link}</span> ${ext_link}`;
                    const relations = parseRelations(row[13]);
                    const relationLinks = Object.values(relations)
                        .map((relation) => relation?.url)
                        .filter((relationUrl) => relationUrl != null && relationUrl !== '')
                        .map((relationUrl) => `<span class="ui mini label">${replaceRepoIcon(relationUrl)} ${createExternalIconLink(relationUrl)}</span>`);

                    if (relationLinks.length === 0) return uri_link;
                    return `${uri_link}<br>${relationLinks.join(' ')}`
                },
        })
    }

    columns.push({ data: 3, name: 'branch', title: '<i class="icon code branch"></i>Branch', render: (el, type, row) => escapeString(el) });

    columns.push({
        data: 9,
        name: 'commit_hash',
        title: '<i class="icon history"></i>Commit</th>',
        render: function(el, type, row) {
            const commitLabels = [];

            if (el != null && el !== '') {
                commitLabels.push(`${escapeString(el.slice(0,3))}...${escapeString(el.slice(-3))}<br>`);
            }

            const relations = parseRelations(row[13]);
            Object.entries(relations).forEach(([relationName, relationData]) => {
                const relationHash = relationData?.commit_hash;
                if (relationHash == null || relationHash === '') return;
                commitLabels.push(`<span class="ui small label">${escapeString(relationName)}: ${escapeString(relationHash.slice(0,7))}</span>`);
            });

            if (commitLabels.length === 0) return null;
            return commitLabels.join(' ');
        },
    });

    columns.push({
        data: 6,
        name: 'filename',
        title: '<i class="icon file alternate"></i>Filename',
        render: function(el, type, row) {
            const usage_scenario_variables = Object.entries(row[7]).map(([k, v]) => `<span class="ui small label">${escapeString(k)}=${escapeString(displayUsageScenarioVariableValue(k, v))}</span>`);
            return `${escapeString(el)} <br> ${usage_scenario_variables.join(' ')}`
        }
    });
    columns.push({ data: 8, name: 'machine', title: '<i class="icon laptop code"></i>Machine</th>', render: (el, type, row) => escapeString(el) });
    columns.push({
        data: 4,
        name: 'created_at',
        title: '<i class="icon calendar"></i>Last run</th>',
        render: function(el, type, row) {
            if (el == null) return '-';
            return `${dateToYMD(new Date(el))}`;

        }
    });
    columns.push({
        title: '<i class="cog icon"></i>Actions</th>',
        className: 'dt-nowrap',
        render: function(_, type, row) {
            const params = new URLSearchParams();
            params.set('uri', row[2]);
            params.set('branch', row[3] ?? '');
            params.set('machine_id', row[12]);
            params.set('filename', row[6] ?? '');

            const usageScenarioVariables = row[7] ?? {};
            if (Object.keys(usageScenarioVariables).length > 0) {
                Object.entries(usageScenarioVariables).forEach(([key, value]) => {
                    params.append(`usage_scenario_variables[${key}]`, String(value));
                });
            } else {
                params.set('usage_scenario_variables', 'false');
            }

            const href = `/timeline.html?${params.toString().replace(/&/g, '&amp;')}`;

            return `
                <div class="run-actions no-wrap">
                    <a title="Timeline Analysis" href="${href}" class="ui tiny teal horizontal icon button no-wrap" target="_blank"><i class="ui icon clock"></i></a>
                    <a title="Carbon Simulation" href="/simulation.html?id=${encodeURIComponent(row[0])}" class="ui tiny teal horizontal icon button no-wrap" target="_blank"><i class="chartline icon"></i></a>
                </div>`
        },
        orderable: false,
    });

    columns.push({
        data: 0,
        render: function(el, type, row) {
            // Modify the content of the "Name" column here
            return `<input type="checkbox" value="${el}" name="chbx-proj" ${selected_run_ids.has(el) ? 'checked' : ''}/>&nbsp;`
        },
        orderable: false,
    });


    el.DataTable({
        // searchPanes: {
        //     initCollapsed: true,
        // },
        searching: searching,
        serverSide: true, // paging, sorting and searching is done by the API
        processing: true,
        ajax: async (dt_params, callback) => {
            const page_length = Math.min(Math.max(dt_params.length, 1), PAGE_LENGTH_MAX);
            let params = `${el.data('gmt-query-string')}&limit=${page_length}&offset=${dt_params.start}&with_count=true`;

            const order = dt_params.order?.[0];
            const order_by = (order != null) ? dt_params.columns?.[order.column]?.name : null;
            if (order_by) {
                params += `&order_by=${encodeURIComponent(order_by)}&order_dir=${order.dir === 'asc' ? 'asc' : 'desc'}`;
            }

            const search = dt_params.search?.value?.trim();
            if (search) params += `&search=${encodeURIComponent(search)}`;

            callback(await fetchDataTablesPage(`/v2/runs?${params}`, dt_params, 'Could not get run data from API'));
        },
        columns: columns,
        pageLength: 10,
        lengthMenu: [10, 25, 50, PAGE_LENGTH_MAX],
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
        order: [[columns.length-3, 'desc']] // default order of the API, but we need to indicate order for the user
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
            document.querySelector('h1.ui.header span').innerText = 'ScenarioRunner - Last Runs';
            localStorage.setItem('scenario_runner_data_shown', 'last_runs');
            history.replaceState(null, '', window.location.pathname); // clear any filters if any set
            window.location.reload();
        }
    });

    const is_repositories_view = (url_params['show'] === 'repositories' || localStorage.getItem('scenario_runner_data_shown') === 'repositories');

    if (is_repositories_view) {
        // reduced filter: only the extra settings apply, and they are used for the runs table of each repository
        document.querySelectorAll('form .basic-filter, form button[name=clear]').forEach((el) => {
            el.style.display = 'none';
        });
        document.querySelector('#runs-and-repos-table-title').innerText = 'Repositories';
        document.querySelector('#home-toggle-button').innerText = 'Switch to last runs view';
        document.querySelector('h1.ui.header span').innerText = 'ScenarioRunner - Repositories';
        document.querySelector('#scenario-runner-runs-description')?.remove();
        sortDate();
    } else {
        document.querySelector('#scenario-runner-repositories-description')?.remove();
        document.querySelector('#sort-button').remove()
        getRunsTable($('#runs-and-repos-table tbody table'), getFilterQueryStringFromURI())
    }

    const value = localStorage.getItem('compare_mode_last_value');
    if (value != null && value != '') {
        document.querySelector('#compare-force-mode').value = value;
        $('.ui.accordion.compare-force-mode').accordion('open', 0);
    } else {
        $('.ui.accordion.compare-force-mode').accordion('close', 0);
    }



    // filters
    $('.ui.accordion.filter-dropdown').accordion();
    $('form').on('submit', async function (e) {
        e.preventDefault();
        if (is_repositories_view) {
            let query_string = getFilterQueryStringFromInputs(false)
            if (url_params['show'] === 'repositories') query_string = `show=repositories${query_string}`; // keep view on reload
            history.pushState(null, '', `${window.location.origin}${window.location.pathname}?${query_string}`); // must be set before, as the runs tables of the repositories read the filters from the URL
            getRepositories(repositories_sort_by); // re-render so that opened repositories are queried with the new settings
        } else {
            const query_string = getFilterQueryStringFromInputs()
            getRunsTable($('#runs-and-repos-table tbody table'), query_string)
            history.pushState(null, '', `${window.location.origin}${window.location.pathname}?${query_string}`); // replace URL to bookmark!
        }
        $('.ui.accordion.filter-dropdown').accordion('close', 0);
        return false;
    });
    $('button[name=clear]').on('click', async function () {
        history.replaceState(null, '', window.location.pathname);
        document.querySelectorAll('input.filter-option').forEach((el) => {
            el.value = '';
        })
        getRunsTable($('#runs-and-repos-table tbody table'), '')
        $('.ui.accordion').accordion('close', 0); // close all accordions
        document.querySelector('#filters-active').classList.add('hidden');
    });


})();
