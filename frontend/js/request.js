(() => {
    document.forms[0].onsubmit = async (event) => {
        event.preventDefault();

        const form = document.querySelector('form');
        const data = new FormData(form);
        const values = Object.fromEntries(data.entries());

        try {
            await makeAPICall('/v1/project/add', values);
            form.reset()
            showNotification('Success', 'Save successful. Check your mail in 10-15 minutes', 'success');
        } catch (err) {
            showNotification('Could not get data from API', err);
        }

    }
})();