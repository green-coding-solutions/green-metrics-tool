const compareButton = () => {
    let checkedBoxes = document.querySelectorAll('input[type=checkbox]:checked');

    let link = '/compare.html?ids=';
    checkedBoxes.forEach(checkbox => {
        link = `${link}${checkbox.value},`;
    });
    window.open(link.substr(0,link.length-1), '_blank');
}
const updateCompareCount = () => {
    const countButton = document.getElementById('compare-button');
    const checkedCount = document.querySelectorAll('input[type=checkbox]:checked').length;
    countButton.textContent = `Compare: ${checkedCount} Run(s)`;
}


const allow_group_select_checkboxes = (checkbox_wrapper_id) => {
    let lastChecked = null;
    let checkboxes = document.querySelectorAll(checkbox_wrapper_id);

    for (let i=0;i<checkboxes.length;i++){
        checkboxes[i].setAttribute('data-index',i);
        checkboxes[i].addEventListener("click",function(e){

            if (lastChecked && e.shiftKey) {
                let i = parseInt(lastChecked.getAttribute('data-index'));
                let j = parseInt(this.getAttribute('data-index'));

                if (i>j) {
                    [i, j] = [j, i]
                }

                for (let c=0; c<checkboxes.length; c++) {
                    if (i <= c && c <=j) {
                        checkboxes[c].checked = this.checked;
                    }
                }
            }
            lastChecked = this;
        });
    }
}

const removeFilter = (paramName) => {
    const urlSearchParams = new URLSearchParams(window.location.search);
    urlSearchParams.delete(paramName);
    const newUrl = `${window.location.pathname}?${urlSearchParams.toString()}`;
    window.location.href = newUrl;
}

const showActiveFilters = (key, value) => {
    document.querySelector(`.ui.warning.message`).classList.remove('hidden');
    const newListItem = document.createElement("span");
    newListItem.innerHTML = `<div class="ui label"><i class="times circle icon" onClick="removeFilter('${escapeString(key)}')"></i>${escapeString(key)}: ${escapeString(value)} </div> `;
    document.querySelector(`.ui.warning.message ul`).appendChild(newListItem);

}

const getFilterQueryStringFromURI = () => {
    const url_params = (new URLSearchParams(window.location.search))
    let query_string = '';
    if (url_params.get('uri') != null && url_params.get('uri').trim() != '') {
        const uri = url_params.get('uri').trim()
        query_string = `${query_string}&uri=${uri}`
        showActiveFilters('uri', uri)
    }
    if (url_params.get('filename') != null && url_params.get('filename').trim() != '') {
        const filename = url_params.get('filename').trim()
        query_string = `${query_string}&filename=${filename}`
        showActiveFilters('filename', filename)
    }
    if (url_params.get('branch') != null && url_params.get('branch').trim() != '') {
        const branch = url_params.get('branch').trim()
        query_string = `${query_string}&branch=${branch}`
        showActiveFilters('branch', branch)
    }
    if (url_params.get('machine_id') != null && url_params.get('machine_id').trim() != '') {
        const machine_id = url_params.get('machine_id').trim()
        query_string = `${query_string}&machine_id=${machine_id}`
        showActiveFilters('machine_id', machine_id)
    }
    if (url_params.get('machine') != null && url_params.get('machine').trim() != '') {
        const machine = url_params.get('machine').trim()
        query_string = `${query_string}&machine=${machine}`
        showActiveFilters('machine', machine)
    }


    return query_string
}

const getRunsTable = (el, url, include_uri=true, include_button=true, searching=false) => {

    const columns = [
        {
            data: 1,
            title: 'Name',
            render: function(name, type, row) {

                if(row[9] == null) name = `${name} (in progress 🔥)`;
                if(row[5] != null) name = `${name} <span class="ui yellow horizontal label" title="${row[5]}">invalidated</span>`;
                return `<a href="/stats.html?id=${row[0]}">${name}</a>`
            },
        },
    ]

    if(include_uri) {
        columns.push({
                data: 2,
                title: '(<i class="icon code github"></i> / <i class="icon code gitlab"></i> / <i class="icon code folder"></i> etc.) Repo',
                render: function(uri, type, row) {
                    let uri_link = replaceRepoIcon(uri);

                    if (uri.startsWith("http")) {
                        uri_link = `${uri_link} <a href="${uri}"><i class="icon external alternate"></i></a>`;
                    }
                    return uri_link
                },
        })
    }

    columns.push({ data: 3, title: '<i class="icon code branch"></i>Branch'});

    columns.push({
        data: 8,
        title: '<i class="icon history"></i>Commit</th>',
        render: function(commit, type, row) {
          // Modify the content of the "Name" column here
          return commit == null ? null : `${commit.substr(0,3)}...${commit.substr(-3,3)}`
        },
    });

    columns.push({ data: 6, title: '<i class="icon file alternate"></i>Filename', });
    columns.push({ data: 7, title: '<i class="icon laptop code"></i>Machine</th>' });
    columns.push({ data: 4, title: '<i class="icon calendar"></i>Last run</th>' });

    const button_title = include_button ? '<button id="compare-button" onclick="compareButton()" class="ui small button blue right">Compare: 0 Run(s)</button>' : '';

    columns.push({
        data: 0,
        title: button_title,
        render: function(id, type, row) {
            // Modify the content of the "Name" column here
            return `<input type="checkbox" value="${id}" name="chbx-proj"/>&nbsp;`
        }
    });

    el.DataTable({
        // searchPanes: {
        //     initCollapsed: true,
        // },
        searching: searching,
        ajax: url,
        columns: columns,
        deferRender: true,
        drawCallback: function(settings) {
            document.querySelectorAll('input[type="checkbox"]').forEach((e) =>{
                e.addEventListener('change', updateCompareCount);
            })
            allow_group_select_checkboxes('input[type="checkbox"]');
            updateCompareCount();
        },
        order: [] // API determines order
    });
}