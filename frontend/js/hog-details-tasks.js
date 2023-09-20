$(document).ready(function () {
    var mData
    function getURLParameter(name) {
        return new URLSearchParams(window.location.search).get(name);
    }

    (async () => {

        try {
            var machine_id = getURLParameter('machine_id')
            var start_id = getURLParameter('start_id')
            var end_id = getURLParameter('end_id')

            var measurements = await makeAPICall(`/v1/hog/coalitions/${machine_id}/${start_id}/${end_id}`);
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }
        mData = measurements.data.map(item => {
            item[0] = new Date(item[0]);
            return item;
        });
        mData.unshift(['time', 'combined_energy', 'cpu_energy', 'gpu_energy','ane_energy','energy_impact', 'id'])

        var myChart = echarts.init(document.getElementById('chart-container'));

        var myChart = echarts.init(document.getElementById('chart-container'));

        option = {
            legend: {
                orient: 'horizontal',
                top: 'top',
                data: ['combined_energy', 'cpu_energy', 'gpu_energy', 'ane_energy','energy_impact'],
                selected: {
                    'combined_energy': false,
                    'cpu_energy': false,
                    'gpu_energy': false,
                    'ane_energy': false,
                    'energy_impact': true
                }

              },
              tooltip: {
                trigger: 'axis',
                axisPointer: {
                  type: 'shadow',
                  label: {
                    show: true
                  }
                }
              },
                    dataset: {
              source: mData
            },
            grid: {
                top: '12%',
                left: '1%',
                right: '10%',
                containLabel: true
              },

            xAxis: {
                type: 'category',
                name: 'Time'
            },

            yAxis: [
                {
                    type: 'value',
                    name: 'mJ',
                    position: 'left',
                },
                {
                  type: 'value',
                  name: 'energy_impact',
                  position: 'right',
                },
              ],
            series: [
                { type: 'bar', yAxisIndex: 0 },
                { type: 'bar', yAxisIndex: 0  },
                { type: 'bar', yAxisIndex: 0  },
                { type: 'bar', yAxisIndex: 0  },
                { type: 'bar', yAxisIndex: 1  }],
            calculable: true,
            dataZoom: [
                {
                  show: true,
                  start: 0,
                  end: 100
                },
                {
                  type: 'inside',
                  start: 0,
                  end: 100
                },
                {
                  show: true,
                  yAxisIndex: 0,
                  filterMode: 'empty',
                  width: 30,
                  height: '80%',
                  showDataShadow: false,
                  left: '93%'
                }
              ],
              toolbox: {
                show: true,
                feature: {
                  mark: { show: true },
                  magicType: { show: true, type: ['line', 'bar', 'stack'] },
                  restore: { show: true },
                  saveAsImage: { show: true },
                  dataZoom: { yAxisIndex: false},
                }
              },

          };


        function handleZoomEvent(){
            let zoomTimeout;
            $('#table-loader').addClass('active');

            clearTimeout(zoomTimeout);

            zoomTimeout = setTimeout(async function() {
                let dataZoomOption = myChart.getOption().dataZoom[0];
                let startPercent = dataZoomOption.start;
                let endPercent = dataZoomOption.end;
                let totalDataPoints = mData.length;
                let startIndex = Math.floor(startPercent / 100 * totalDataPoints);
                let endIndex = Math.ceil(endPercent / 100 * totalDataPoints) - 1;
                let firstValue = mData[startIndex];
                let lastValue = mData[endIndex];
                if (firstValue[6] == 'id'){
                    firstValue[6] = 1;
                }
                if(typeof lastValue === "undefined"){
                    lastValue =[1,1,1,1,1,1,1];
                }
                try {

                    var coalitions = await makeAPICall(`/v1/hog/coalitions_tasks/${firstValue[6]}/${lastValue[6]}`);

                    $('#process-table').DataTable({
                        destroy: true,
                        data: coalitions.data,
                        columns: [
                            { data: 0, title: 'Name'},
                            { data: 1, title: 'Energy Impact'},
                            {
                                data: 2,
                                title: 'Mb Read',
                                render: function(data, type, row) {
                                    if (type === 'display' || type === 'filter') {
                                        return (data / 1048576).toFixed(2);
                                    }
                                    return data;
                                }
                            },
                            {
                                data: 3,
                                title: 'Mb Written',
                                render: function(data, type, row) {
                                    if (type === 'display' || type === 'filter') {
                                        return (data / 1048576).toFixed(2);
                                    }
                                    return data;
                                }
                            },
                            { data: 4, title: 'Intr Wakeups'},
                            { data: 5, title: 'Idle Wakeups'},
                            {
                                data: null,
                                title: '',
                                render: function(data, type, row) {
                                    return `<button class="ui icon button js-task-info" data-name="${row[0]}" data-start="${firstValue[6]}" data-end="${lastValue[6]}"><i class="info icon"></i></button>`;
                                },
                                orderable: false,
                                searchable: false
                            }
                        ],
                        deferRender: true,
                        order: [],
                    });
                    $('#table-loader').removeClass('active');

                    $('.js-task-info').click(async function() {
                        console.log("Follow button clicked!", );
                        $('#task-details').modal('show');
                        var tasks = await makeAPICall(`/v1/hog/tasks_details/${$(this).data('start')}/${$(this).data('end')}/${$(this).data('name')}`);
                        console.log(tasks);
                        $('#process-detail-table').on( 'init.dt', function () {
                                $("#task-loading").removeClass('active');
                        }).DataTable({
                            paging: false,
                            destroy: true,
                            data: tasks.tasks_data,
                            columns: [
                                { data: 0, title: 'Name'},
                                { data: 1, title: 'Occurrence'},
                                { data: 2, title: 'total_energy_impact'},
                                { data: 3, title: 'cputime_ns'},
                                { data: 4, title: 'bytes_received'},
                                { data: 5, title: 'bytes_sent'},
                                { data: 6, title: 'diskio_bytesread'},
                                { data: 7, title: 'diskio_byteswritten'},
                                { data: 8, title: 'intr_wakeups'},
                                { data: 9, title: 'idle_wakeups'},
                            ],
                            deferRender: true,
                            order: [],

                        });

                    });

                } catch (err) {
                    showNotification('Could not get data from API', err);
                    return;
                }
            }, 1000);

        }

        function focusOnBar(dataIndex) {
            let zoomFactor = 4;
            let dataLength = mData.length -1 ;
            let startPercent = (dataIndex - zoomFactor / 2) / dataLength * 100;
            let endPercent = (dataIndex + zoomFactor / 2) / dataLength * 100;

            myChart.setOption({
                dataZoom: [{
                    start: Math.max(0, startPercent),
                    end: Math.min(100, endPercent)
                }]
            });
        }
        myChart.setOption(option);
        handleZoomEvent();

        myChart.on('click', function(params) {
            if (params.componentType === 'series' && params.seriesType === 'bar') {
                focusOnBar(params.dataIndex);
                handleZoomEvent();
            }
        });

        myChart.on('datazoom', function() {
            handleZoomEvent();
        });

        myChart.on('restore', function() {
            handleZoomEvent();
        });

    })();
});


