(async () => {
    if (ACTIVATE_ENERGY_ID == true) {
        document.querySelectorAll('.energy-id').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/insights`)
            document.querySelector('#energy-id-count').innerText = api_data.data[0];
            document.querySelector('#energy-id-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get Energy ID stats from API`, err) }
    }

    if (ACTIVATE_ECO_CI == true) {
        document.querySelectorAll('.eco-ci').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/ci/insights`)
            document.querySelector('#eco-ci-count').innerText = api_data.data[0];
            document.querySelector('#eco-ci-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get Eco CI stats from API`, err) }

    }

    if (ACTIVATE_CARBON_DB == true) {
        document.querySelectorAll('.carbon-db').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/carbondb/insights`)
            document.querySelector('#carbondb-id-count').innerText = api_data.data[0];
            document.querySelector('#carbondb-id-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get CarbonDB stats from API`, err) }

    }

    if (ACTIVATE_POWER_HOG == true) {
        document.querySelectorAll('.power-hog').forEach(el => el.style.setProperty("display", "block", "important"))
        try {
            const api_data = await makeAPICall(`/v1/hog/insights`)
            document.querySelector('#hog-count').innerText = api_data.data[0];
            document.querySelector('#hog-oldest').innerText = api_data.data[1];
        } catch (err) { showNotification(`Could not get PowerHOG stats from API`, err) }

    }
})();
