(async () => {

    function populateFieldsFromURL() {
        const urlParams = new URLSearchParams(window.location.search);

        if (urlParams.has('name')) {
            document.querySelector('input[name="name"]').value = escapeString(urlParams.get('name'));
        }
        if (urlParams.has('email')) {
            document.querySelector('input[name="email"]').value = escapeString(urlParams.get('email'));
        }
        if (urlParams.has('url')) {
            document.querySelector('input[name="url"]').value = escapeString(urlParams.get('url'));
        }
        if (urlParams.has('filename')) {
            document.querySelector('input[name="filename"]').value = escapeString(urlParams.get('filename'));
        }
        if (urlParams.has('branch')) {
            document.querySelector('input[name="branch"]').value = escapeString(urlParams.get('branch'));
        }
        if (urlParams.has('machine_id')) {
            document.querySelector('select[name="machine_id"]').value = escapeString(urlParams.get('machine_id'));
        }
        if (urlParams.has('schedule_mode')) {
            document.querySelector('select[name="schedule_mode"]').value = escapeString(urlParams.get('schedule_mode'));
        }
    }


    try {
        var machines_json = await makeAPICall('/v1/machines');

        machines_json.data.forEach(machine => {
                if(machine[2] == false) return;
                let newOption = new Option(machine[1],machine[0]);
                const select = document.querySelector('select');
                select.add(newOption,undefined);
            })

        populateFieldsFromURL();

    } catch (err) {
        showNotification('Could not get machines data from API', err);
    }


    document.forms[0].onsubmit = async (event) => {
        event.preventDefault();

        const form = document.querySelector('form');
        const data = new FormData(form);
        const values = Object.fromEntries(data.entries());

        for (let key in values) {
            if (typeof values[key] === 'string') {
                values[key] = values[key].trim();
            }
        }

        try {
            await makeAPICall('/v1/software/add', values);
            form.reset()
            showNotification('Success', 'Save successful. Check your mail in 10-15 minutes', 'success');
        } catch (err) {
            showNotification('Could not get data from API', err);
        }

    }


})();