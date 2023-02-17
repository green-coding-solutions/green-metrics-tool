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
    })();
});
