"use strict";
function createVariablesComparisonTable(variablesList, labelPrefix = 'Item', keyHeader = 'Key') {
    // variablesList holds one usage scenario variables object per comparison group
    const allKeys = new Set(variablesList.flatMap(vars => Object.keys(vars)));

    let tableContent = `<table><tr><th>${escapeString(keyHeader)}</th>`;
    variablesList.forEach((_, index) => {
        tableContent += `<th style="text-align: center;">${escapeString(labelPrefix)} ${index + 1}</th>`;
    });
    tableContent += '</tr>';

    allKeys.forEach(key => {
        tableContent += `<tr><td><strong>${escapeString(key)}</strong></td>`;
        variablesList.forEach(vars => {
            const value = Object.hasOwn(vars, key) ? displayUsageScenarioVariableValue(key, vars[key]) : '-';
            tableContent += `<td style="text-align: center;">${escapeString(value)}</td>`;
        });
        tableContent += '</tr>';
    });
    tableContent += '</table>';
    
    return tableContent;
}

async function fetchDiff(run_ids) {
    document.querySelector('#diff-question').remove();
    document.querySelector('#loader-diff').classList.remove('hidden');
    document.querySelector('#diff-container').insertAdjacentHTML('beforebegin', '<h2>Configuration and Settings diff</h2>')
    try {
        const diffString = (await makeAPICall(`/v1/diff?ids=${run_ids.join(',')}`)).data
        const targetElement = document.getElementById('diff-container');
        const configuration = { drawFileList: true, matching: 'lines', highlight: true };

        const diff2htmlUi = new Diff2HtmlUI(targetElement, diffString, configuration);
        diff2htmlUi.draw();
        diff2htmlUi.highlightCode();
    } catch (err) {
        showNotification('Could not get diff data from API', err);
    }
    document.querySelector('#loader-diff').remove();

}

const buildSeries = (ds1, ds2) => {
  const cumulative1 = [];
  const cumulative2 = [];
  const candles = [];
  const labels1 = [];
  const labels2 = [];

  let cum1 = 0;
  let cum2 = 0;

  for (let i = 0; i < ds1.length; i++) {
    cum1 += ds1[i].value;
    cum2 += ds2[i].value;

    cumulative1.push(cum1);
    cumulative2.push(cum2);

    const delta = ds2[i].value - ds1[i].value;
    candles.push([0, delta, Math.min(0, delta), Math.max(0, delta)]);

    labels1.push(ds1[i].label);
    labels2.push(ds2[i].label);

  }

  return { cumulative1, cumulative2, candles, labels1, labels2 };
}

const arraysCompare = (a, b) => {
  if (a.length !== b.length) return { equal: false, differences: 'Lengths differ' };

  const differences = [];
  a.forEach((val, index) => {
    if (val !== b[index]) differences.push({ index, a: val, b: b[index] });
  });

  return { equal: differences.length === 0, differences };
}

const fetchAndShowTimeSeriesNotesHistory = async (run_ids) => {

    if (run_ids.length != 2) {
        document.querySelector('#loader-time-series-notes').classList.add('hidden');
        document.querySelector('#time-series-notes-no-display').classList.remove('hidden');
        document.querySelector('#time-series-notes-no-display .description').textContent = 'Time Series Notes History can only be displayed for exactly two runs. Please reduce comparison to two runs if you want to inspect this graph.'
        document.querySelector('#time-series-notes-chart').remove()
        return
    }

    const [notes_data1, notes_data2] = await Promise.all([
        fetchTimelineNotes(run_ids[0]),
        fetchTimelineNotes(run_ids[1])
    ])

    if (!notes_data1 || !notes_data2) {
        document.querySelector('#loader-time-series-notes').classList.add('hidden');
        document.querySelector('#time-series-notes-no-display').classList.remove('hidden');
        document.querySelector('#time-series-notes-no-display .description').textContent = 'Could not fetch notes data for one or both runs.'
        document.querySelector('#time-series-notes-chart').remove()
        return
    }

    const dataset1 = notes_data1.map((row) => { return {"value": row[4], "label": row[2]} })
    const dataset2 = notes_data2.map((row) => { return {"value": row[4], "label": row[2]} })

    const notes1 = dataset1.map((row) => { return row['label'] })
    const notes2 = dataset2.map((row) => { return row['label'] })

    if (notes1.length !=  notes2.length) {
        document.querySelector('#loader-time-series-notes').classList.add('hidden');
        document.querySelector('#time-series-notes-no-display').classList.remove('hidden');
        document.querySelector('#time-series-notes-no-display .description').textContent = 'Your two runs have different amount of notes in the time series. This cannot be compared.'
        document.querySelector('#time-series-notes-chart').remove()
        return
    }

    const comparison = arraysCompare(notes1, notes2)
    if (!comparison.equal) {
        document.querySelector('#loader-time-series-notes').classList.add('hidden');
        document.querySelector('#time-series-notes-no-display').classList.remove('hidden');
        const description = document.querySelector('#time-series-notes-no-display .description')
        description.innerHTML = 'Runs have same amount of notes, but at least one note differed in text. This might only be a small textual change or can be totally different steps. Please check chart for different labels in steps.<br><ul></ul>';
        const description_ul = description.querySelector('ul')
        comparison.differences.forEach(el =>  {description_ul.insertAdjacentHTML('beforeend', `<li>${escapeString(el.a)} -> ${escapeString(el.b)}</li>`)})
    }

    let { cumulative1, cumulative2, candles, labels1, labels2 } = buildSeries(dataset1, dataset2);
    const option = {
    tooltip: {
        trigger: 'axis',
        formatter: function (params) {
          if (!params.length) return '';
          // Series hidden via the legend are missing from params, so never access them by position
          const lines = params.map((p) => {
            // Take the step delta from our own data, as ECharts reshapes candlestick values in params
            const value = p.seriesName === 'Step Delta' ? candles[p.dataIndex][1] : p.value;
            return `${p.marker} ${p.seriesName}: ${numberFormatter.format(value)} s`;
          });
          return `${escapeString(params[0].axisValue)}<br>${lines.join('<br>')}`;
        }
      },
      legend: {
        data: ['Run 1', 'Run 2', 'Step Delta'],
        top: 0,
      },
      grid: {
        top: 60,     // space for legend
        bottom: 135   // space for zoom slider
      },
      dataZoom: [
        {
          type: 'slider',
          xAxisIndex: 0,
          startValue: 0,
          height: 30,
          bottom: 20
        }
      ],
      xAxis: [
          {
            type: 'category',
            data: labels1,
            axisTick: { alignWithLabel: true },
            axisLabel: {
                rotate: 45,
                fontSize: 10,
                overflow: 'truncate',
                ellipsis: '…',  // optional, default is '...'
                width: 100          // maximum width in pixels
            }
          }
      ],
      yAxis: [
        {
          type: 'value',
          name: 'Cumulative Time (s)',
          position: 'left'
        },
        {
          type: 'value',
          name: 'Step Delta (s)',
          position: 'right'
        }
      ],
      series: [
        {
          name: 'Run 1',
          type: 'line',
          data: cumulative1,
          smooth: true,
          markLine: { data: []} // will be filled later
        },
        {
          name: 'Run 2',
          type: 'line',
          data: cumulative2,
          smooth: true,
        },
        {
          name: 'Step Delta',
          type: 'candlestick',
          yAxisIndex: 1,
          data: candles,
          itemStyle: {
            color: '#00c853',     // green (Run 2 faster)
            color0: '#d50000',    // red (Run 2 slower)
            borderColor: '#00c853',
            borderColor0: '#d50000'
          }
        }
      ]
    };

    comparison.differences.forEach(el =>  {
        option.series[0].markLine.data.push(
        {
            xAxis: el.index, // index instead of label, as labels can repeat and ECharts would then mark the first match
            label: {
                show: true,
                formatter: '⚠',
                color: 'orange',
                fontSize: 16,
                position: 'middle',
              },
              lineStyle: {
                color: 'orange',
                type: 'dashed'
              }
        })
    })


    const time_series_notes_history_chart = echarts.init(document.getElementById('time-series-notes-chart'));

    time_series_notes_history_chart.setOption(option);

    document.querySelector('#loader-time-series-notes').classList.add('hidden');

    $(window).on('resize', () =>  {
        time_series_notes_history_chart.resize();
    });

}

$(document).ready( () => {
    (async () => {
        const url_params = getURLParams();

        if(url_params['ids'] == null
            || url_params['ids'] == ''
            || url_params['ids'] == 'null') {
            showNotification('No ids', 'ids parameter in URL is empty or not present. Did you follow a correct URL?');
            return;
        }

        const run_ids = url_params['ids'].split(",");
        if (!run_ids.every(isValidUUID)) {
            showNotification('Invalid ids', 'ids parameter in URL contains at least one invalid run ID. Did you follow a correct URL?');
            return;
        }

        let phase_stats_data = null
        try {
            let url = `/v1/compare?ids=${run_ids}`
            if (url_params['force_mode']?.length) {
                url = `${url}&force_mode=${encodeURIComponent(url_params['force_mode'])}`
            }
            phase_stats_data = (await makeAPICall(url)).data
        } catch (err) {
            if (err instanceof APIHTTPError && err.status === 409) {
                console.log('Endpoint cannot handle request. Will redirect to simple table.')
                window.location.href = `/compare-simple.html?ids=${run_ids}&redirect_from_auto=true`;
                return
            }

            showNotification('Could not get compare in-repo data from API', err);
            return
        }

        const warnings = await fetchWarningsForRuns(run_ids);
        fillWarnings(warnings);

        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Type</strong></td><td>${escapeString(phase_stats_data.comparison_case)}</td></tr>`)
        // count the runs the API resolved and not the URL ids, as these can contain duplicates or runs not visible to the user
        const run_count = phase_stats_data.comparison_details.flat().length
        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Number of runs compared</strong></td><td>${run_count}</td></tr>`)
        if (phase_stats_data.comparison_case === 'Machine') {
            let comparison_identifiers = phase_stats_data.comparison_identifiers.join(' vs. ')

            const regex = /(\d+)\s+vs\.\s+(\d+)/;
            const match = comparison_identifiers.match(regex);

            if (match) {
                const num1 = parseInt(match[1], 10); // First number
                const num2 = parseInt(match[2], 10); // Second number
                document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${num1} (${escapeString(GMT_MACHINES[num1] || num1)}) vs. ${num2} (${escapeString(GMT_MACHINES[num2] || num2)})</td></tr>`)
            } else {
                document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${escapeString(GMT_MACHINES[comparison_identifiers] || comparison_identifiers)}</td></tr>`)
            }
        } else if (phase_stats_data.comparison_case === 'Usage Scenario Variables') {
            // comparison_details has one list of runs per comparison identifier. All runs in a group share the same variables
            const variablesList = phase_stats_data.comparison_details.map(runs => runs[0]?.usage_scenario_variables || {});
            const tableContent = createVariablesComparisonTable(variablesList, 'Scenario', 'Variable');
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${tableContent}</td></tr>`)
        } else if (phase_stats_data.comparison_case === 'IDs') {
            document.querySelector('#compare-mode-ids').classList.remove('hidden');

        } else {
            let comparison_identifiers = phase_stats_data.comparison_identifiers.map((el) => replaceRepoIcon(el)).join(' vs. ');
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${comparison_identifiers}</td></tr>`)
        }
        Object.keys(phase_stats_data['common_info']).forEach(function(key) {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(key)}</strong></td><td>${escapeString(phase_stats_data['common_info'][key])}</td></tr>`)
          });

        document.querySelector('#loader-compare-meta').remove();
        document.querySelector('#loader-compare-run').remove();
        document.querySelector('#diff-question').classList.remove('hidden');
        document.querySelector('#fetch-diff').addEventListener('click', (event) => { fetchDiff(run_ids) })

        buildPhaseTabs(phase_stats_data)
        renderCompareChartsForPhase(phase_stats_data, getAndShowPhase());
        displayTotalChart(...buildTotalChartData(phase_stats_data));
        // comparison_details is ordered by created_at ASC, same as the comparison tables. The ids from the URL are newest first
        fetchAndShowTimeSeriesNotesHistory(phase_stats_data.comparison_details.flat().map(el => el.run_id))

        document.querySelectorAll('.ui.steps.phases .step, .runtime-step').forEach(node => node.addEventListener('click', el => {
            const phase = el.currentTarget.getAttribute('data-tab');
            renderCompareChartsForPhase(phase_stats_data, phase);
        }));

    })();
});

