function createPythonDictTable(dataArray, labelPrefix = 'Item', keyHeader = 'Key') {
    // Parse Python dictionary data into a comparison table
    const items = Array.isArray(dataArray) ? dataArray : [dataArray];
    
    // Collect all unique keys
    const allKeys = new Set();
    const parsedItems = items.map(item => {
        const vars = {};
        const matches = item.match(/'([^']+)':\s*'([^']*)'/g);
        if (matches) {
            matches.forEach(match => {
                const [, key, value] = match.match(/'([^']+)':\s*'([^']*)'/);
                vars[key] = value;
                allKeys.add(key);
            });
        }
        return vars;
    });
    
    // Build simple table
    let tableContent = `<table><tr><th>${keyHeader}</th>`;
    items.forEach((_, index) => {
        tableContent += `<th style="text-align: center;">${labelPrefix} ${index + 1}</th>`;
    });
    tableContent += '</tr>';
    
    allKeys.forEach(key => {
        tableContent += `<tr><td><strong>${escapeString(key)}</strong></td>`;
        parsedItems.forEach(item => {
            tableContent += `<td style="text-align: center;">${escapeString(item[key] || '-')}</td>`;
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

const fetchWarningsForRuns = async (run_ids) => {
    const warnings = [];
    for (const run_id of run_ids) {
        try {
            const data = await makeAPICall('/v1/warnings/' + run_id);
            if (data?.data) warnings.push(...data.data);
        } catch (err) {
            if (err instanceof APIEmptyResponse204) {
                console.log('No warnings where present in API response. Skipping error as this is allowed case.')
            } else {
                showNotification('Could not get warnings data from API', err);
            }
        }
    }
    return warnings;
};

const fillWarnings = (warnings) => {
    if (!warnings || warnings.length === 0) return;
    const warnings_texts = warnings.map(sub => sub[1]);
    const unique_warnings = [...new Set(warnings_texts)];

    const container = document.querySelector('#run-warnings');
    const ul = container.querySelector('ul');
    unique_warnings.forEach(w => {
        ul.insertAdjacentHTML('beforeend', `<li>${escapeString(w)}</li>`);
    });
    container.classList.remove('hidden');
};

const buildSeries = (ds1, ds2) => {
  const cumulative1 = [];
  const cumulative2 = [];
  const candles = [];
  const labels = [];

  let cum1 = 0;
  let cum2 = 0;

  for (let i = 0; i < ds1.length; i++) {
    cum1 += ds1[i].value;
    cum2 += ds2[i].value;

    cumulative1.push(cum1);
    cumulative2.push(cum2);

    const delta = ds2[i].value - ds1[i].value;
    candles.push([0, delta, Math.min(0, delta), Math.max(0, delta)]);

    labels.push(ds1[i].label);
  }

  return { cumulative1, cumulative2, candles, labels };
}

const arraysEqual = (a, b) => {
  if (a.length !== b.length) return false;
  return a.every((val, index) => val === b[index]);
}

const fetchAndShowTimeSeriesNotesHistory = async (run_ids) => {

    if (run_ids.length != 2) {
        document.querySelector('#loader-time-series-notes').classList.add('hidden');
        document.querySelector('#time-series-notes-no-display').classList.remove('hidden');
        document.querySelector('#time-series-notes-no-display .description').textContent = 'Time Series Notes History can only be displayed for exactly two runs. Please reduce comparison to two runs if you want to inspect this graph.'
        document.querySelector('#time-series-notes-chart').remove()
        return
    }

    const notes1 = await fetchTimelineNotes(run_ids[0])
    const notes2 = await fetchTimelineNotes(run_ids[1])

    if (!notes1 || !notes2) {
        document.querySelector('#loader-time-series-notes').classList.add('hidden');
        document.querySelector('#time-series-notes-no-display').classList.remove('hidden');
        document.querySelector('#time-series-notes-no-display .description').textContent = 'Could not fetch notes data for one or both runs.'
        document.querySelector('#time-series-notes-chart').remove()
        return
    }

    const dataset1 = notes1.map((row) => { return {"value": row[4], "label": row[2]} })
    const dataset2 = notes2.map((row) => { return {"value": row[4], "label": row[2]} })

    const labels1 = dataset1.map((row) => { return row['label'] })
    const labels2 = dataset2.map((row) => { return row['label'] })

    if (!arraysEqual(labels1, labels2)) {
        document.querySelector('#loader-time-series-notes').classList.add('hidden');
        document.querySelector('#time-series-notes-no-display').classList.remove('hidden');
        document.querySelector('#time-series-notes-no-display .description').textContent = 'Your two runs have different notes in the time series. This cannot be compared. Their notes must be exactly identical.'
        document.querySelector('#time-series-notes-chart').remove()
        return
    }


    let { cumulative1, cumulative2, candles, labels } = buildSeries(dataset1, dataset2);
    const option = {
    tooltip: {
        trigger: 'axis',
        formatter: function (params) {

          const series1 = params[0];
          const series2 = params[1];
          const candlestick = params[2];          // candlestick series
          const [open, close, low, high] = candlestick.data;
          console.log(series1)
          return `
            ${series1.axisValue}<br/>
            ${series1.marker} ${series1.seriesName}: ${numberFormatter.format(series1.value)} s<br>
            ${series2.marker} ${series2.seriesName}: ${numberFormatter.format(series2.value)} s<br>
            ${candlestick.marker} ${candlestick.seriesName}: ${numberFormatter.format(candlestick.value[2])} s<br>

          `;
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
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: {
            rotate: 45,
            fontSize: 10,
            overflow: 'truncate',
            ellipsis: '…',  // optional, default is '...'
            width: 100          // maximum width in pixels
        }
      },
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
          smooth: true
        },
        {
          name: 'Run 2',
          type: 'line',
          data: cumulative2,
          smooth: true
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
            throw "Error";
        }

        const run_ids = url_params['ids'].split(",");
        const run_count = run_ids.length

        let phase_stats_data = null
        try {
            let url = `/v1/compare?ids=${run_ids}`
            if (url_params['force_mode']?.length) {
                url = `${url}&force_mode=${url_params['force_mode']}`
            }
            phase_stats_data = (await makeAPICall(url)).data
        } catch (err) {
            showNotification('Could not get compare in-repo data from API', err);
            return
        }

        const warnings = await fetchWarningsForRuns(run_ids);
        fillWarnings(warnings);

        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Type</strong></td><td>${escapeString(phase_stats_data.comparison_case)}</td></tr>`)
        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Number of runs compared</strong></td><td>${run_count}</td></tr>`)
        if (phase_stats_data.comparison_case === 'Machine') {
            let comparison_identifiers = phase_stats_data.comparison_identifiers.join(' vs. ')

            const regex = /(\d+)\s+vs\.\s+(\d+)/;
            const match = comparison_identifiers.match(regex);

            if (match) {
                const num1 = parseInt(match[1], 10); // First number
                const num2 = parseInt(match[2], 10); // Second number
                document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${num1} (${GMT_MACHINES[num1]}) vs. ${num2} (${GMT_MACHINES[num2]})</td></tr>`)
            } else {
                document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${GMT_MACHINES[comparison_identifiers] || escapeString(comparison_identifiers)}</td></tr>`)
            }
        } else if (phase_stats_data.comparison_case === 'Usage Scenario Variables') {
            const tableContent = createPythonDictTable(phase_stats_data.comparison_identifiers || comparison_identifiers.split(' vs. '), 'Scenario', 'Variable');
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
        renderCompareChartsForPhase(phase_stats_data, getAndShowPhase(), run_count);
        displayTotalChart(...buildTotalChartData(phase_stats_data));
        fetchAndShowTimeSeriesNotesHistory(run_ids)

        document.querySelectorAll('.ui.steps.phases .step, .runtime-step').forEach(node => node.addEventListener('click', el => {
            const phase = el.currentTarget.getAttribute('data-tab');
            renderCompareChartsForPhase(phase_stats_data, phase, run_count);
        }));

    })();
});

