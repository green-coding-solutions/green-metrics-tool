const populateFieldsFromURL = () => {
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has('name')) {
        document.querySelector('input[name="name"]').value = escapeString(urlParams.get('name'));
    }
    if (urlParams.has('email')) {
        document.querySelector('input[name="email"]').value = escapeString(urlParams.get('email'));
    }
    if (urlParams.has('url')) {
        document.querySelector('input[name="repo_url"]').value = escapeString(urlParams.get('url'));
    }
    if (urlParams.has('repo_url')) { // precedence
        document.querySelector('input[name="repo_url"]').value = escapeString(urlParams.get('repo_url'));
    }
    if (urlParams.has('repo_to_watch_url')) {
        document.querySelector('input[name="repo_to_watch_url"]').value = escapeString(urlParams.get('repo_to_watch_url'));
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
    if (urlParams.has('usage_scenario_variables')) {
        try {
            const variables = JSON.parse(urlParams.get('usage_scenario_variables'));
            const variablesContainer = document.getElementById('variables-container');
            variablesContainer.innerHTML = '';

            for (const key in variables) {
                if (Object.hasOwnProperty.call(variables, key)) {
                    const match = key.match(/^__GMT_VAR_([\w]+)__$/);
                    if (match) {
                        addVariableField(match[1], variables[key]);
                    }
                }
            }
        } catch (e) {
            console.error('Failed to parse usage_scenario_variables from URL:', e);
        }
    }
}

const addVariableField = (keyPart = '', value = '') => {
    const variablesContainer = document.getElementById('variables-container');
    const newVariableRow = document.createElement('div');
    newVariableRow.classList.add('variable-row', 'ui', 'grid', 'middle', 'aligned',  'stackable');

  newVariableRow.innerHTML = `
        <div class="seven wide column">
                <div class="ui right labeled input fluid">
                    <div class="ui label">__GMT_VAR_</div>
                    <input type="text" placeholder="Key (Variables are optional. Leave empty if not needed)" class="variable-key" pattern="[\\w]+" title="Only alphanumeric characters and underscores are allowed." value="${escapeString(keyPart)}">
                    <div class="ui label">__</div>
                </div>
        </div>
        <div class="one wide column computer only tablet only" style="text-align: center; padding: 0;">
            =
        </div>
        <div class="eight wide column">
                <div class="ui action input fluid">
                    <input type="text" placeholder="Value (Variables are optional. Leave empty if not needed)" class="variable-value" value="${escapeString(value)}">
                    <button type="button" class="ui red mini icon button remove-variable">
                        <i class="times icon"></i>
                    </button>
                </div>
        </div>
    `;

    variablesContainer.appendChild(newVariableRow);
    
    const divider = document.createElement('div');
    divider.classList.add('ui', 'divider', 'custom-mobile-divider');
    variablesContainer.appendChild(divider);

    updateRemoveButtonsVisibility();
};

const updateRemoveButtonsVisibility = () => {
    const variableRows = document.querySelectorAll('#variables-container .variable-row');
    variableRows.forEach(row => {
        row.querySelector('.remove-variable').style.display = 'inline-block';
    });
    
};


(async () => {

    await getClusterStatus();

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

    $('#add-variable').on('click', () => addVariableField());
    addVariableField() // always add one empty row

    $('#variables-container').on('click', '.remove-variable', function (e) {
        $(this).closest('.variable-row').remove();
        updateRemoveButtonsVisibility();
    });


    $('#variables-container').on('click', '.remove-variable', function (e) {
        $(this).closest('.variable-row').remove();
        updateRemoveButtonsVisibility();
    });

    const toggleWatchRepoVisibility = () => {
        const scheduleModeSelect = document.getElementById('schedule-mode-select');
        const watchRepoDiv = document.getElementById('watch-different-repo');
        const commitModes = ['commit', 'commit-variance', 'tag', 'tag-variance'];

        if (commitModes.includes(scheduleModeSelect.value)) {
            watchRepoDiv.classList.remove('hidden');
        } else {
            watchRepoDiv.classList.add('hidden');
        }
    };

    toggleWatchRepoVisibility();
    $('#schedule-mode-select').on('change', toggleWatchRepoVisibility);

    document.forms[0].onsubmit = async (event) => {
        event.preventDefault();

        const form = document.querySelector('form');
        const data = new FormData(form);
        const values = Object.fromEntries(data.entries());

        const usageScenarioVariables = {};
        let validationError = false;
        document.querySelectorAll('#variables-container .variable-row').forEach(row => {
            const keyPart = row.querySelector('.variable-key').value.trim();
            const value = row.querySelector('.variable-value').value.trim();
            if (keyPart) {
                if (!/^[\w]+$/.test(keyPart)) {
                    showNotification('Validation Error', `Variable part "${keyPart}" must only contain alphanumeric characters.`, 'error');
                    validationError = true;
                    return;
                }
                const key = `__GMT_VAR_${keyPart}__`;
                usageScenarioVariables[key] = value;
            }
        });

        if (validationError) {
            return;
        }

        values.usage_scenario_variables = usageScenarioVariables;

        for (let key in values) {
            if (typeof values[key] === 'string') {
                values[key] = values[key].trim();
            }
        }

        try {
            await makeAPICall('/v1/software/add', values);
            form.reset()
            document.getElementById('variables-container').innerHTML = '';
            showNotification('Success', 'Save successful. Check your mail in 10-15 minutes', 'success');
        } catch (err) {
            showNotification('Could not get data from API', err);
        }

    }
})();