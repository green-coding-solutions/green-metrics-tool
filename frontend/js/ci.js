const copyToClipboard = (e) => {
  if (navigator && navigator.clipboard && navigator.clipboard.writeText)
    return navigator.clipboard.writeText(e.target.parentElement.parentElement.children[0].innerHTML);
  return Promise.reject('The Clipboard API is not available.');
};

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


        try {
            document.querySelectorAll("#badges span.energy-badge-container").forEach(el => {
                const link_node = document.createElement("a")
                const img_node = document.createElement("img")
                img_node.src = `${API_URL}/v1/ci/badge/get/?repo=${url_params.get('repo')}&branch=${url_params.get('branch')}&workflow=${url_params.get('workflow')}`
                link_node.appendChild(img_node)
                el.appendChild(link_node)
            })
            document.querySelectorAll(".copy-badge").forEach(el => {
                el.addEventListener('click', copyToClipboard)
            })

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
            const link_node = document.createElement('a');
            const badge_value = el[0]
            const run_id = el[1]
            const created_at = el[2]
           
            // DM: unsure
            //content.push({ title: name });
            li_node.appendChild(link_node);

            li_node.innerHTML = `<td class="td-index">${badge_value}</td><td class="td-index">${run_id}</td><td class="td-index"><span title="${created_at}">${(new Date(created_at)).toString()}</span></td>`;
            document.querySelector("#badges-table").appendChild(li_node);
        });
        $('table').tablesort();

    })();
});
