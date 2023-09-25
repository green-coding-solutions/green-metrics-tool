$(document).ready(function () {
    function getURLParameter(name) {
        return new URLSearchParams(window.location.search).get(name);
    }

    (async () => {
        var mData

        try {
            var machine_id = getURLParameter('machine_id')
            var measurements = await makeAPICall(`/v1/hog/machine_details/${machine_id}`);
        } catch (err) {
            showNotification('Could not get data from API', err);
            return;
        }
        mData = measurements.data.map(item => {
            item[0] = new Date(item[0]);
            return item;
        });
        mData.unshift(['time', 'combined_energy', 'cpu_energy', 'gpu_energy','ane_energy','energy_impact', 'id'])

        const myChart = echarts.init(document.getElementById('chart-container'));

        options = {
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
                const dataZoomOption = myChart.getOption().dataZoom[0];
                const startPercent = dataZoomOption.start;
                const endPercent = dataZoomOption.end;
                const totalDataPoints = mData.length;
                const startIndex = Math.floor(startPercent / 100 * totalDataPoints);
                const endIndex = Math.ceil(endPercent / 100 * totalDataPoints) - 1;
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
                    energy_html = `
                        <div class="ui relaxed horizontal divided list">
                            <div class="item">
                                <div class="content">
                                <div class="header">Combined System Energy</div>
                                ${coalitions.energy_data[0].toLocaleString()} mJ
                                </div>
                            </div>
                            <div class="item">
                                <div class="content">
                                <div class="header">Cpu Energy</div>
                                ${coalitions.energy_data[1].toLocaleString()} mJ
                                </div>
                            </div>
                            <div class="item">
                                <div class="content">
                                <div class="header">Gpu Energy</div>
                                ${coalitions.energy_data[2].toLocaleString()} mJ
                                </div>
                            </div>
                            <div class="item">
                                <div class="content">
                                <div class="header">Ane Energy</div>
                                ${coalitions.energy_data[3].toLocaleString()} mJ
                                </div>
                            </div>
                            <div class="item">
                                <div class="content">
                                <div class="header">Energy Impact</div>
                                ${coalitions.energy_data[4].toLocaleString()}
                                </div>
                            </div>
                        </div>
                    `
                    $("#energy_segment").html(energy_html)
                    $('#process-table').DataTable({
                        autoWidth: false,
                        destroy: true,
                        data: coalitions.data,
                        columns: [
                            { data: 0, title: 'Name'},
                            {
                                data: 1,
                                title: 'Energy Impact',
                                className: "dt-body-right",
                                render: function(data, type, row) {
                                    if (type === 'display' || type === 'filter') {
                                        return (data.toLocaleString())
                                    }
                                    return data;
                                }
                            },
                            {
                                data: 2,
                                title: 'Mb Read',
                                className: "dt-body-right",
                                render: function(data, type, row) {
                                    if (type === 'display' || type === 'filter') {
                                        return Math.trunc(data / 1048576).toLocaleString();
                                    }
                                    return data;
                                }
                            },
                            {
                                data: 3,
                                title: 'Mb Written',
                                className: "dt-body-right",
                                render: function(data, type, row) {
                                    if (type === 'display' || type === 'filter') {
                                        return Math.trunc(data / 1048576).toLocaleString();
                                    }
                                    return data;
                                }
                            },
                            { data: 4, title: 'Intr Wakeups',className: "dt-body-right"},
                            { data: 5, title: 'Idle Wakeups', className: "dt-body-right"},
                            { data: 6, title: 'Avg cpu time %', className: "dt-body-right"},

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

                        $("#coaliton-segment").addClass("loading")
                        $("#task-segment").addClass("loading")

                        $('#task-details').modal('show');

                        var tasks = await makeAPICall(`/v1/hog/tasks_details/${$(this).data('start')}/${$(this).data('end')}/${$(this).data('name')}`);

                        coalition_string=`
                        <h3>${tasks.coalitions_data[0]}</h3>
                        <div class="ui list">
                            <div class="item"><b>total_energy_impact</b>:${tasks.coalitions_data[1]}</div>
                            <div class="item"><b>total_diskio_bytesread</b>:${tasks.coalitions_data[2]}</div>
                            <div class="item"><b>total_diskio_byteswritten</b>:${tasks.coalitions_data[3]}</div>
                            <div class="item"><b>total_intr_wakeups</b>:${tasks.coalitions_data[4]}</div>
                            <div class="item"><b>total_idle_wakeups</b>:${tasks.coalitions_data[5]}</div>
                        </div>
                        `
                        const tasks_string = tasks.tasks_data.map(subArr => `
                        <h3>${subArr[0]}</h3>
                        <div class="ui list">
                            <div class="item"><b>Name</b>:${subArr[1]}</div>
                            <div class="item"><b>Occurrence</b>:${subArr[2]}</div>
                            <div class="item"><b>total_energy_impact</b>:${subArr[3]}</div>
                            <div class="item"><b>cputime_ns</b>:${subArr[4]}</div>
                            <div class="item"><b>bytes_received</b>:${subArr[5]}</div>
                            <div class="item"><b>bytes_sent</b>:${subArr[6]}</div>
                            <div class="item"><b>diskio_bytesread</b>:${subArr[7]}</div>
                            <div class="item"><b>diskio_byteswritten</b>:${subArr[8]}</div>
                            <div class="item"><b>intr_wakeups</b>:${subArr[9]}</div>
                            <div class="item"><b>idle_wakeups</b>:${subArr[10]}</div>
                        </div>
                        `).join(' ');
                        $("#coaliton-segment").html(coalition_string)
                        $("#coaliton-segment").removeClass("loading")

                        $("#task-segment").html(tasks_string)
                        $("#task-segment").removeClass("loading")


                    });

                } catch (err) {
                    showNotification('Could not get data from API', err);
                    return;
                }
            }, 1000);

        }

        function focusOnBar(dataIndex) {
            const zoomFactor = 8;
            const dataLength = mData.length -1 ;
            const startPercent = (dataIndex - zoomFactor / 2) / dataLength * 100;
            const endPercent = (dataIndex + zoomFactor / 2) / dataLength * 100;

            myChart.setOption({
                dataZoom: [{
                    start: Math.max(0, startPercent),
                    end: Math.min(100, endPercent)
                }]
            });
        }
        myChart.setOption(options);
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

        window.addEventListener('resize', function() {
            myChart.resize();
        });


    })();
});
