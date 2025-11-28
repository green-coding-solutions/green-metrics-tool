"use strict";

const getData = async () => {
    let start_date = $('#rangestart input').val();
    let end_date = $('#rangeend input').val();

    if (start_date == '') {
        start_date = dateToYMD(new Date((new Date()).setDate((new Date).getDate() -30)), /*short=*/ true);
        $('#rangestart input').val(start_date);
    } else {
        start_date = dateToYMD(new Date(start_date), /*short=*/ true);
    }
    if (end_date == '') {
        end_date = dateToYMD(new Date(), /*short=*/ true);
        $('#rangeend input').val(end_date);
    } else {
        end_date = dateToYMD(new Date(end_date), /*short=*/ true);
    }

    return await makeAPICall(`/v2/hog/details?start_date=${start_date}&end_date=${end_date}`);
}

function uJToKWh(uj) {
    return uj / 3.6e12;
}

const updateData = async () => {
    $('.carbondb-data').hide();

    if ($.fn.DataTable.isDataTable('#process-table')) {
        $('#process-table').DataTable().destroy();
    }

    let data;

    try {
        data = await getData();
    } catch (err) {
        console.log(err);
        showNotification('Could not get data from API', err);
        return;
    }

    if (data.process_data.length == 0){
        showNotification('No data', 'We could not find any data. Please check your date and filter conditions.')
        return;
    }

    $('#process-table').DataTable({
        data: data.process_data,
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
            }
        ],
        deferRender: true,
        order: [] // API determines order
    });

    const total_energy = uJToKWh(data.total_combined_energy_uj);
    const total_cpu_energy = uJToKWh(data.total_cpu_energy_uj);
    const total_gpu_energy = uJToKWh(data.total_gpu_energy_uj);
    const total_operational_carbon_g = data.total_operational_carbon_ug / 1_000_000;
    const total_total_embodied_carbon_g = data.total_embodied_carbon_ug / 1_000_000;

    $('#operational-carbon').html(`<span title="${total_operational_carbon_g}">${total_operational_carbon_g.toFixed(2)}</span>`);
    $('#embodied-carbon').html(`<span title="${total_total_embodied_carbon_g}">${total_total_embodied_carbon_g.toFixed(2)}</span>`);
    $('#total-energy').html(`<span title="${total_energy}">${total_energy.toFixed(2)}</span>`);
    $('#total-cpu-energy').html(`<span title="${total_cpu_energy}">${total_cpu_energy.toFixed(2)}</span>`);
    $('#total-gpu-energy').html(`<span title="${total_gpu_energy}">${total_gpu_energy.toFixed(2)}</span>`);

    $('.carbondb-data').show();

}


$(document).ready(function () {

    $('#rangestart').calendar({
        type: 'date',
        endCalendar: $('#rangeend')
      });
      $('#rangeend').calendar({
        type: 'date',
        startCalendar: $('#rangestart')
      });


    $('#refresh').click(async () => {
        await updateData();
    });

    updateData();
});
