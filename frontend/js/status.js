$(document).ready(function () {
    (async () => {
        $('#jobs-table').DataTable({
            ajax: `${API_URL}/v1/jobs`,
            columns: [
                { data: 0, title: 'ID'},
                { data: 1, title: 'Name'},
                { data: 2, title: 'Url'},
                { data: 3, title: 'Filename'},
                { data: 4, title: 'Branch'},
                { data: 5, title: 'Machine'},
                { data: 6, title: 'State'},
                { data: 7, title: 'Last Update', render: (data) => data == null ? '-' : dateToYMD(new Date(data)) },
                { data: 8, title: 'Created at', render: (data) => data == null ? '-' : dateToYMD(new Date(data)) },
            ],
            deferRender: true,
            order: [[7, 'desc']] // API also orders, but we need to indicate order for the user
        });
    })();
});
