const addZed = (num) => {
    return (num <= 9 ? '0' + num : num);
}

const formatDateTime = (date) => {
        var h = date.getHours();
        var m = date.getMinutes();
        var s = date.getSeconds();

        var timeString = '' + addZed(h) + ':' + addZed(m) + ':' + addZed(s) 
        var dateString = date.toDateString();

        return '' + dateString + ' | ' + timeString
    }

const convertValue = (value, unit) => {
    switch (unit) {
      case 'mJ':
        return [value / 1000, 'Joules'];
        break;
      default:
        return [value, unit];        // no conversion in default calse
    }

}

$(document).ready( (e) => {
    (async () => {
        const query_string = window.location.search;
        const url_params = (new URLSearchParams(query_string))

        if(url_params.get('repo') == null || url_params.get('repo') == '' || url_params.get('repo') == 'null') {
            showNotification('No Repo', 'Repo parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }        
        if(url_params.get('branch') == null || url_params.get('branch') == '' || url_params.get('branch') == 'null') {
            showNotification('No Branch', 'Branch parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }
        if(url_params.get('workflow') == null || url_params.get('workflow') == '' || url_params.get('workflow') == 'null') {
            showNotification('No Workflow', 'Workflow parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }

        const repo_link = `https://github.com/${url_params.get('repo')}`;
        const repo_link_node = `<a href="${repo_link}">${url_params.get('repo')}</a>`
        document.querySelector('#ci-data').insertAdjacentHTML('beforeend', `<tr><td><strong>Repository</strong></td><td>${repo_link_node}</td></tr>`)
        document.querySelector('#ci-data').insertAdjacentHTML('beforeend', `<tr><td><strong>Branch</strong></td><td>${url_params.get('branch')}</td></tr>`)
        document.querySelector('#ci-data').insertAdjacentHTML('beforeend', `<tr><td><strong>Workflow</strong></td><td>${url_params.get('workflow')}</td></tr>`)

        try {
            const link_node = document.createElement("a")
            const img_node = document.createElement("img")
            img_node.src = `${API_URL}/v1/ci/badge/get/?repo=${url_params.get('repo')}&branch=${url_params.get('branch')}&workflow=${url_params.get('workflow')}`
            link_node.appendChild(img_node)
            document.querySelector("span.energy-badge-container").appendChild(link_node)
            document.querySelector(".copy-badge").addEventListener('click', copyToClipboard)
        } catch (err) {
            showNotification('Could not get badge data from API', err);
        }

        try {
            api_string=`/v1/ci/badges/?repo=${url_params.get('repo')}&branch=${url_params.get('branch')}&workflow=${url_params.get('workflow')}`;
            var badges_data = await makeAPICall(api_string);
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }

        badges_data.data.forEach(el => {
            const li_node = document.createElement("tr");
            
            [badge_value, badge_unit] = convertValue(el[0], el[1])
            const value = badge_value + ' ' + badge_unit;
            
            const run_id = el[2];
            const run_link = `https://github.com/${url_params.get('repo')}/actions/runs/${run_id}`;
            const run_link_node = `<a href="${run_link}">${run_id}</a>`
            
            const created_at = el[3]

            li_node.innerHTML = `<td class="td-index">${value}</td>\
                                <td class="td-index">${run_link_node}</td>\
                                <td class="td-index"><span title="${created_at}">${formatDateTime(new Date(created_at))}</span></td>`;
            document.querySelector("#badges-table").appendChild(li_node);
        });
       $('table').tablesort();

    })();
});
