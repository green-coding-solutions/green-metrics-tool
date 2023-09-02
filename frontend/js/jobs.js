(async () => {

    $('#jobs-table').DataTable({
        ajax: `${API_URL}/v1/jobs`,
        colums: [
            { data: 0, title: 'ID'},
            { data: 2, title: 'Machine Description'},
            { data: 3, title: 'Failed'},
            { data: 4, title: 'Running'},
            { data: 5, title: 'Last Run'},
            { data: 6, title: 'Created at'},
        ],
        deferRender: true,
        order: [] // API determines order
    });


})();
