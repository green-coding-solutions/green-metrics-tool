$(document).ready(function () {
    (async () => {

        let cluster_changelog = null;

        try {
            cluster_changelog = await makeAPICall('/v1/cluster/changelog')
        } catch (err) {
            if (err instanceof APIEmptyResponse204) { // empty data is an OK response
                return
            } else {
                showNotification('Could not get cluster changelog data from API', err);
                return; // abort
            }
        }

        $('#changelog-table').DataTable({
            data: cluster_changelog?.data,
            searching: false,
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Name', render: (el) => escapeString(el)},
                { data: 2, title: 'Machine ID'},
                { data: 3, title: 'Created at', render: (el) => el == null ? '-' : dateToYMD(new Date(el)) },
            ],
            deferRender: true,
            order: [], // use API default order
        });

    })();
});
