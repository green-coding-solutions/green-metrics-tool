(async () => {

    $('#timeline-projects-table').DataTable({
        ajax: `${API_URL}/v1/timeline-projects`,
        columns: [
            { data: 0, title: 'ID'},
            { data: 1, title: 'Url'},
            { data: 2, title: 'Categories'},
            { data: 3, title: 'Branch'},
            { data: 4, title: 'Filename'},
            { data: 5, title: 'Machine'},
            { data: 6, title: 'Schedule Mode'},
            { data: 7, title: 'Last Scheduled'},
            { data: 8, title: 'Created At'},
            { data: 9, title: 'Updated At'},

        ],
        deferRender: true,
        order: [] // API determines order
    });
})();
