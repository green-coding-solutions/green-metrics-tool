$(document).ready(function () {
    (async () => {

        let cluster_status_data = null;

        try {
            cluster_status_data = await makeAPICall('/v1/cluster/status/history')
        } catch (err) {
            if (err instanceof APIEmptyResponse204) { // empty data is an OK response
                return
            } else {
                showNotification('Could not get cluster status history data from API', err);
                return; // abort
            }
        }

        $('#status-messages-table').DataTable({
            data: cluster_status_data?.data,
            searching: false,
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Name', render: (el) => escapeString(el)},
                { data: 2, title: 'Resolved', render: function(el) {
                    return (el == true) ? '<i class="ui label mini empty green circular"></i>': '<i class="ui label mini empty red circular"></i>';
                }},

                { data: 3, title: 'Created at', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
            ],
            deferRender: true,
            order: [], // use API default order
        });

    })();
});
