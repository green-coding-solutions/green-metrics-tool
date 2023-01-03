(async () => {
    const compareButton = () => {
        var checkedBoxes = document.querySelectorAll('input[name=chbx-proj]:checked');
        console.log(checkedBoxes.length);
        var link = "";
        if (checkedBoxes.length == 2) {
            link = "/multi.html?dummy=dummy";
        }
        else if (checkedBoxes.length > 2) {
            link = "/compare.html?dummy=dummy";
        }
        else {
            showNotification('Note', 'Please select at least two projects to compare');
            return;
        }

        checkedBoxes.forEach(checkbox => {
            link += "&pids[]=" + checkbox.value;
        });
        //console.log(link);
        window.location = link;
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
        content.push({ title: el[1] });
        if(el[3] == null) {
            link_node.innerText =  el[1] + " (no data yet 🔥)";
        } else {
            link_node.innerText = el[1];
        }
        link_node.title = el[1];
        link_node.href = "/stats.html?id=" + el[0];
        li_node.appendChild(link_node);
        li_node.innerHTML = '<td class="td-index">' + li_node.innerHTML + '</td><td class="td-index">' + el[2] + '</td><td class="td-index">' + el[4] + '</td><td><input type="checkbox" value="' + el[0] + '" name="chbx-proj" />&nbsp;</td>';
        document.querySelector("#projects-table").appendChild(li_node);
    });
    $('.ui.search').search({ source: content });
    $('table').tablesort();
    $('#compare-button').on('click', compareButton);


})();
