(() => {
    let content = [];
    makeAPICall('/v1/projects', (my_json) => {
        my_json.data.forEach(el => {

            const li_node = document.createElement("tr");
            const link_node = document.createElement('a');
            content.push({ title: el[1] });
            link_node.innerText = el[1];
            link_node.title = el[1];
            link_node.href = "/stats.html?id=" + el[0];
            li_node.appendChild(link_node);
            li_node.innerHTML = '<td class="td-index">' + li_node.innerHTML + '</td><td class="td-index">' + el[2] + '</td><td class="td-index">' + el[3] + '</td><td><input type="checkbox" value="' + el[0] + '" name="chbx-proj" />&nbsp;</td>';
            document.getElementById("projects-table").appendChild(li_node);
        });
        $('.ui.search').search({ source: content });
    });

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
            $('body')
              .toast({
                class: 'warning',
                showProgress: 'bottom',
                classProgress: 'warning',
                title: 'Note',
                message: 'Please select at least two projects to compare'
            });
            return;
        }

        checkedBoxes.forEach(checkbox => {
            link += "&pid[]=" + checkbox.value;
        });
        //console.log(link);
        window.location = link;
    }

    $(document).ready(function () {
        $('table').tablesort();
        $('#compare-button').on('click', compareButton);
    });

})();
