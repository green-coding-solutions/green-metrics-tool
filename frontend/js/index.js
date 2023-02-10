(async () => {
    const dateToYMD = (date) => {
        var d = date.getDate();
        var m = date.getMonth() + 1; //Month from 0 to 11
        var y = date.getFullYear();
        return '' + y + '-' + (m<=9 ? '0' + m : m) + '-' + (d <= 9 ? '0' + d : d);
    }

    let content = [];
    try {
        var stats_data = await makeAPICall('/v1/projects')
    } catch (err) {
            showNotification('Could not get data from API', err);
            return;
    }
    stats_data.data.forEach(el => {
        const li_node = document.createElement("tr");
        const link_node = document.createElement('a');
        const id = el[0]
        const name = el[1]
        let uri = el[2]
        let branch = el[3]
        const end_measurement = el[4]
        const last_run = el[5]
        const invalid_project = el[6]

        content.push({ title: name });
        if(end_measurement == null) {
            link_node.innerText =  `${name} (no data yet 🔥)`;
        } else {
            link_node.innerText = name;
        }
        if(invalid_project != null) {
            link_node.innerHTML = `${name} <span class="ui yellow horizontal label" title="${invalid_project}">invalidated</span>`;
        }


        link_node.title = name;
        link_node.href = `/stats.html?id=${id}`;
        li_node.appendChild(link_node);


        if (!branch) {
            if (uri.startsWith("http")) {
                branch = 'main/master'
            }
            else {
                branch = '-'
            }
        }

        // Modify the branch name if the database returned null
        if (uri.startsWith("http")) uri = `<a href="${uri}">${uri}</a>`


        li_node.innerHTML = `<td class="td-index">${li_node.innerHTML}</td><td class="td-index">${uri}</td><td class="td-index">${branch}</td><td class="td-index"><span title="${last_run}">${dateToYMD(new Date(last_run))}</span></td>`;
        document.querySelector("#projects-table").appendChild(li_node);
    });
    $('.ui.search').search({ source: content });
    $('table').tablesort();
    $('#compare-button').on('click', compareButton);


})();
