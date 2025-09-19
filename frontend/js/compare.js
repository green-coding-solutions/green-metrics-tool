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

async function fetchDiff() {
    document.querySelector('#diff-question').remove();
    document.querySelector('#loader-diff').style.display = '';
    document.querySelector('#diff-container').insertAdjacentHTML('beforebegin', '<h2>Configuration and Settings diff</h2>')
    try {
        const url_params = getURLParams();
        const diffString = (await makeAPICall(`/v1/diff?ids=${url_params['ids']}`)).data
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

const fetchWarningsForRuns = async (ids) => {
    const warnings = [];
    for (const id of ids) {
        try {
            const data = await makeAPICall('/v1/warnings/' + id);
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

$(document).ready( () => {
    (async () => {
        const url_params = getURLParams();

        if(url_params['ids'] == null
            || url_params['ids'] == ''
            || url_params['ids'] == 'null') {
            showNotification('No ids', 'ids parameter in URL is empty or not present. Did you follow a correct URL?');
            throw "Error";
        }


        const run_count = url_params['ids'].split(",").length
        let phase_stats_data = null
        try {
            let url = `/v1/compare?ids=${url_params['ids']}`
            if (url_params['force_mode']?.length) {
                url = `${url}&force_mode=${url_params['force_mode']}`
            }
            phase_stats_data = (await makeAPICall(url)).data
        } catch (err) {
            showNotification('Could not get compare in-repo data from API', err);
            return
        }

        const warnings = await fetchWarningsForRuns(url_params['ids'].split(','));
        fillWarnings(warnings);

        let comparison_identifiers = phase_stats_data.comparison_identifiers.map((el) => replaceRepoIcon(el));
        comparison_identifiers = comparison_identifiers.join(' vs. ')
        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Comparison Type</strong></td><td>${escapeString(phase_stats_data.comparison_case)}</td></tr>`)
        document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>Number of runs compared</strong></td><td>${run_count}</td></tr>`)
        if (phase_stats_data.comparison_case === 'Machine') {
            const regex = /(\d+)\s+vs\.\s+(\d+)/;
            const match = comparison_identifiers.match(regex);

            if (match) {
                const num1 = parseInt(match[1], 10); // First number
                const num2 = parseInt(match[2], 10); // Second number
                document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${num1} (${escapeString(GMT_MACHINES[num1])}) vs. ${num2} (${escapeString(GMT_MACHINES[num2])})</td></tr>`)
            } else {
                document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${escapeString(GMT_MACHINES[comparison_identifiers] || comparison_identifiers)}</td></tr>`)
            }
        } else if (phase_stats_data.comparison_case === 'Usage Scenario Variables') {
            const tableContent = createPythonDictTable(phase_stats_data.comparison_identifiers || comparison_identifiers.split(' vs. '), 'Scenario', 'Variable');
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${tableContent}</td></tr>`)
        } else {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(phase_stats_data.comparison_case)}</strong></td><td>${escapeString(comparison_identifiers)}</td></tr>`)
        }
        Object.keys(phase_stats_data['common_info']).forEach(function(key) {
            document.querySelector('#run-data-top').insertAdjacentHTML('beforeend', `<tr><td><strong>${escapeString(key)}</strong></td><td>${escapeString(phase_stats_data['common_info'][key])}</td></tr>`)
          });

        document.querySelector('#loader-compare-meta').remove();
        document.querySelector('#loader-compare-run').remove();
        document.querySelector('#diff-question').style.display = '';


        document.querySelector('#fetch-diff').addEventListener('click', fetchDiff);

        buildPhaseTabs(phase_stats_data)
        renderCompareChartsForPhase(phase_stats_data, getAndShowPhase(), run_count);
        displayTotalChart(...buildTotalChartData(phase_stats_data));

        document.querySelectorAll('.ui.steps.phases .step, .runtime-step').forEach(node => node.addEventListener('click', el => {
            const phase = el.currentTarget.getAttribute('data-tab');
            renderCompareChartsForPhase(phase_stats_data, phase, run_count);
        }));

    })();
});

