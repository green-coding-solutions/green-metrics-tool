const compareButton = () => {
    let checkedBoxes = document.querySelectorAll('input[name=chbx-proj]:checked');

    let link = '/compare.html?ids=';
    checkedBoxes.forEach(checkbox => {
        link = `${link}${checkbox.value},`;
    });
    window.location = link.substr(0,link.length-1);
}
(async () => {
    const dateToYMD = (date) => {
        let day = date.getDate();
        day = day <= 9 ? '0' + day : day;

        let month = date.getMonth() + 1; //Month from 0 to 11
        month = month<=9 ? '0' + month : month;
        let offset = new Date().getTimezoneOffset();
        offset = offset < 0 ? `+${-offset/60}` : -offset/60;


        return ` ${date.getFullYear()}-${month}-${day} <br> ${date.getHours()}:${date.getMinutes()} UTC${offset}`;
    }

    let search = [];
    try {
        var api_data = await makeAPICall('/v1/projects')
    } catch (err) {
            showNotification('Could not get data from API', err);
            return;
    }
    api_data.data.forEach(el => {

        const id = el[0]
        let name = el[1]
        const uri = el[2]
        let branch = (el[3] == null) ? 'main/master' : el[3]
        const end_measurement = el[4]
        const last_run = el[5]
        const invalid_project = el[6]
        const filename = el[7]
        const machine = el[8]

        let uri_link = replaceRepoIcon(uri);

        if (uri.startsWith("http")) {
            uri_link = `${uri_link} <a href="${uri}"><i class="icon external alternate"></i></a>`;
        }


        // insert new accordion row if repository not known
        let td_node = document.querySelector(`td[data-uri='${uri}_${branch}']`)
        if (td_node == null || td_node == undefined) {
            let row = document.querySelector('#projects-table tbody').insertRow()
            row.innerHTML = `
                <td data-uri="${uri}_${branch}">
                    <div class="ui accordion" style="width: 100%;">
                      <div class="title">
                        <i class="dropdown icon"></i> ${uri_link}
                      </div>
                      <div class="content">
                      </div>
                    </div>
                </td>
                <td>${branch}</td>
                <td><input type="checkbox" class="toggle-checkbox"></td>`;
            let content = document.querySelector(`#projects-table td[data-uri='${uri}_${branch}'] div.content`);
            content.innerHTML = `
                <table class="ui table">
                    <thead class="full-width">
                        <tr>
                            <th>Name</th>
                            <th>Filename</th>
                            <th>Machine</th>
                            <th>Last run</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>`;
        }



        search.push({ title: name });


        if(end_measurement == null) name = `${name} (no data yet 🔥)`;
        if(invalid_project != null) name = `${name} <span class="ui yellow horizontal label" title="${invalid_project}">invalidated</span>`;

        let inner_row = document.querySelector(`#projects-table td[data-uri='${uri}_${branch}'] div.content table tbody`).insertRow();

        inner_row.innerHTML = `
            <td class="td-index"><a href="/stats.html?id=${id}">${name}</a></td>
            <td class="td-index" title="${filename}">${filename}</td>
            <td class="td-index">${machine}</td>
            <td class="td-index" style="width: 120px"><span title="${last_run}">${dateToYMD(new Date(last_run))}</span></td>
            <td><input type="checkbox" value="${id}" name="chbx-proj"/>&nbsp;</td>`;

    });

    $('.ui.search').search({ source: search });
    $('.ui.accordion').accordion();
    $('#projects-table table').tablesort();


    document.querySelectorAll('.toggle-checkbox').forEach((e) => {
        e.addEventListener('click', (e1) => {
            e1.currentTarget.closest('tr').querySelectorAll('td:first-child input').forEach((e2) => {
                e2.checked = e1.currentTarget.checked
            })
        })
    })



})();
