const compareButton = () => {
    let checkedBoxes = document.querySelectorAll('input[name=chbx-proj]:checked');

    let link = '/compare.html?ids=';
    checkedBoxes.forEach(checkbox => {
        link = `${link}${checkbox.value},`;
    });
    window.location = link.substr(0,link.length-1);
}
const updateCompareCount = () => {
    const countButton = document.getElementById('compare-button');
    const checkedCount = document.querySelectorAll('input[name=chbx-proj]:checked').length;
    countButton.textContent = `Compare: ${checkedCount} Run(s)`;
}

function allow_group_select_checkboxes(checkbox_wrapper_id){
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

(async () => {
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
        let branch = el[3]
        const end_measurement = el[4]
        const last_run = el[5]
        const invalid_project = el[6]
        const filename = el[7]
        const machine = el[8]
        const commit_hash = el[9]
        const commit_hash_short = commit_hash == null ? null : `${commit_hash.substr(0,3)}...${commit_hash.substr(-3,3)}`



        let uri_link = replaceRepoIcon(uri);

        if (uri.startsWith("http")) {
            uri_link = `${uri_link} <a href="${uri}"><i class="icon external alternate"></i></a>`;
        }


        // insert new accordion row if repository not known
        let td_node = document.querySelector(`td[data-uri='${uri}']`)
        if (td_node == null || td_node == undefined) {
            let row = document.querySelector('#projects-table tbody').insertRow()
            row.innerHTML = `
                <td data-uri="${uri}">
                    <div class="ui accordion" style="width: 100%;">
                      <div class="title">
                        <i class="dropdown icon"></i> ${uri_link}
                      </div>
                      <div class="content">
                      </div>
                    </div>
                </td>`;
            let content = document.querySelector(`#projects-table td[data-uri='${uri}'] div.content`);
            content.innerHTML = `
                <table class="ui table">
                    <thead class="full-width">
                        <tr>
                            <th>Name</th>
                            <th><i class="icon file alternate"></i>Filename</th>
                            <th><i class="icon laptop code"></i>Machine</th>
                            <th><i class="icon code branch"></i>Branch</th>
                            <th><i class="icon history"></i>Commit</th>
                            <th><i class="icon calendar"></i>Last run</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>`;
        }

        if(end_measurement == null) name = `${name} (no data yet 🔥)`;
        if(invalid_project != null) name = `${name} <span class="ui yellow horizontal label" title="${invalid_project}">invalidated</span>`;

        let inner_row = document.querySelector(`#projects-table td[data-uri='${uri}'] div.content table tbody`).insertRow();

        inner_row.innerHTML = `
            <td class="td-index"><a href="/stats.html?id=${id}">${name}</a></td>
            <td class="td-index" title="${filename}">${filename}</td>
            <td class="td-index">${machine}</td>
            <td class="td-index">${branch}</td>
            <td class="td-index" title="${commit_hash}">${commit_hash_short}</td>
            <td class="td-index"><span title="${last_run}">${dateToYMD(new Date(last_run))}</span></td>
            <td><input type="checkbox" value="${id}" name="chbx-proj"/>&nbsp;</td>`;
    });



    $('.ui.accordion').accordion();
    setTimeout(function() {
        $('#projects-table table').DataTable({
//            searchPanes: {
//              initCollapsed: true,
//            },
            "order": [[5, 'desc']], // sort by last_run by default
        });

    }, 1000); // Delay of 2000 milliseconds (2 seconds)

    /*
    This code would be most efficient. But it has bad UI experience due to lag
    $('.ui.accordion').accordion({
        onOpen: function(value, text) {
            table = this.querySelector('table')
            if(!$.fn.DataTable.isDataTable(table)) {
                $(table).DataTable({
        //            searchPanes: {
        //              initCollapsed: true,
        //            },
                    "order": [[5, 'desc']], // sort by last_run by default
                });
            }
    }});
    */


    document.querySelectorAll('input[name=chbx-proj]').forEach((e) =>{
        e.addEventListener('change', updateCompareCount);
    })
  
    allow_group_select_checkboxes('#projects-table input[type="checkbox"]');

})();
