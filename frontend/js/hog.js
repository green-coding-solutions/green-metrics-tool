$(document).ready(function () {

    (async () => {
        try {
            var measurements = await makeAPICall('/v1/hog/top_processes');
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }
        $('#process-table').DataTable({
            data: measurements.process_data,
            autoWidth: false,
            columns: [
                { data: 0, title: 'Name'},
                {
                    data: 1,
                    title: 'Energy Impact',
                    className: "dt-body-right",
                    render: function(el, type, row) {
                        if (type === 'display' || type === 'filter') {
                            return (el.toLocaleString())
                        }
                        return el;
                    }
                },
            ],
            deferRender: true,
            order: [] // API determines order
        });
        $('#machine_count').text(measurements.machine_count);
    })();
});
