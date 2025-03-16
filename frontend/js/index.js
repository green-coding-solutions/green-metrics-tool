(async () => {
    if (ACTIVATE_METRIC_RUNNER === true) {
        document.querySelectorAll('.metric-runner').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/insights`)
            document.querySelector('#metric-runner-count').innerText = api_data.data[0];
            document.querySelector('#metric-runner-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get MetricRunner stats from API`, err) }
    }

    if (ACTIVATE_ECO_CI === true) {
        document.querySelectorAll('.eco-ci').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/ci/insights`)
            document.querySelector('#eco-ci-count').innerText = api_data.data[0];
            document.querySelector('#eco-ci-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get Eco CI stats from API`, err) }

    }

    if (ACTIVATE_CARBON_DB === true) {
        document.querySelectorAll('.carbondb').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/carbondb/insights`)
            document.querySelector('#carbondb-count').innerText = api_data.data[0];
            document.querySelector('#carbondb-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get CarbonDB stats from API`, err) }

    }

    if (ACTIVATE_POWER_HOG === true) {
        document.querySelectorAll('.power-hog').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/hog/insights`)
            document.querySelector('#hog-count').innerText = api_data.data[0];
            document.querySelector('#hog-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get PowerHOG stats from API`, err) }

    }
})();
