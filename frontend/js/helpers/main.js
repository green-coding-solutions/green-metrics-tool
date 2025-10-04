const GMT_MACHINES = JSON.parse(localStorage.getItem('gmt_machines')) || {}; // global variable. dynamically resolved via resolveMachinesToGlobalVariable

class APIEmptyResponse204 extends Error {}

const date_options = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false
};

/*
    WebComponent function without ShadowDOM
    to expand the menu in the HTML pages
*/
class GMTMenu extends HTMLElement {
   connectedCallback() {
        let html_content = `
        <div id="menu" class="ui inverted vertical menu">
            <div class="item-container">
                <a class="item" href="/index.html" aria-label="Home">
                    <b><i class="home icon"></i> Home</b>
                </a>`

        if (ACTIVATE_SCENARIO_RUNNER == true) {
            html_content = `${html_content}
                <a class="item" href="/runs.html" aria-label="ScenarioRunner"><b><i class="tachometer alternate left icon"></i> ScenarioRunner</b></a>
                <a class="item" href="/runs.html" aria-label="Runs / Repos">
                    ⮑&nbsp;&nbsp;<b><i class="code branch icon"></i> Runs / Repos</b>
                </a>
                <a class="item" href="/watchlist.html" aria-label="Watchlist">
                    ⮑&nbsp;&nbsp;<b><i class="list icon"></i> Watchlist</b>
                </a>
                <a class="item" href="/request.html" aria-label="Submit Software">
                    ⮑&nbsp;&nbsp;<b><i class="bullseye icon"></i> Submit Software</b>
                </a>
                <a class="item" href="/cluster-status.html" aria-label="Cluster Status">
                    ⮑&nbsp;&nbsp;<b><i class="database icon"></i> Cluster Status</b>
                </a>`;
        };

        if (ACTIVATE_ECO_CI == true) {
            html_content = `${html_content}
                <a class="item" href="/ci-index.html" aria-label="Eco CI">
                    <b><i class="seedling icon"></i> Eco CI</b>
                </a>`;
        };

        if (ACTIVATE_POWER_HOG == true) {
            html_content = `${html_content}
                <a class="item" href="/hog.html" aria-label="Power HOG">
                    <b><i class="piggy bank icon"></i> Power HOG</b>
                </a>`;
        };

        if (ACTIVATE_CARBON_DB == true) {
            html_content = `${html_content}
                <a class="item" href="/carbondb.html" aria-label="CarbonDB">
                    <b><i class="balance scale icon"></i> CarbonDB</b>
                </a>`;
        };

        html_content = `${html_content}
                <a class="item" href="/data-analysis.html" aria-label="Data Analysis">
                    <b><i class="chartline icon"></i> Data Analysis</b>
                </a>
                <a class="item" href="/authentication.html" aria-label="Authentication">
                    <b><i class="users icon"></i>Authentication</b>
                </a>
                <a class="item" href="/settings.html" aria-label="Settings">
                    <b><i class="cogs icon"></i> Settings</b>
                </a>
            </div>
            <div class="sticky-container">
                <a href="href="https://www.green-coding.io">
                  <img class="ui fluid image menu-logo" src="/images/green-coding-menu-logo-2x.webp"
                       srcset="/images/green-coding-menu-logo.webp 1x,
                               /images/green-coding-menu-logo-2x.webp 2x"
                       alt="Green Coduing Solutions Logo">
                </a>
            </div>

        </div> <!-- end menu -->`;

        this.innerHTML = html_content;
    }
}
customElements.define('gmt-menu', GMTMenu);

// tricky to make this async as some other functions will depend on the value of the variable
// but if it is not set yet it will populate in a later call
const resolveMachinesToGlobalVariable = async () => {
    if (Object.keys(GMT_MACHINES).length === 0) {
        const api_data = await makeAPICall('/v1/machines')
        api_data.data.forEach(el => {
            GMT_MACHINES[el[0]] = el[1];
        })
    }
    localStorage.setItem('gmt_machines', JSON.stringify(GMT_MACHINES));
}


const getClusterStatus = async (status_ok_selector, status_warning_selector) => {
    try {
        cluster_status_data = await makeAPICall('/v1/cluster/status')

        const container = document.querySelector('.cluster-health-message.yellow #cluster-health-warnings');
        cluster_status_data.data.forEach(message => {
            container.insertAdjacentHTML('beforeend', `<p id="message-${message[0]}"><b>${new Date(message[3]).toLocaleDateString('sv-SE', date_options)}</b>: ${message[1]}</p>`);
        })
        document.querySelector('.cluster-health-message.yellow').style.display = 'flex'; // show

    } catch (err) {
        if (err instanceof APIEmptyResponse204) {
            document.querySelector('.cluster-health-message.success').style.display = 'flex'; // show
        } else {
            showNotification('Could not get cluster health status data from API', err); // no return as we want other calls to happen
        }
    }
}

const dateTimePicker = (days_before=30, url_params=null) => {

    $('#rangestart').calendar({
        type: 'date',
        endCalendar: $('#rangeend'),
        initialDate: (url_params['start_date'] != null) ? url_params['start_date'] : new Date((new Date()).setDate((new Date).getDate() - days_before)),
    });

    $('#rangeend').calendar({
        type: 'date',
        startCalendar: $('#rangestart'),
        initialDate: (url_params['end_date'] != null) ? url_params['end_date'] : new Date(),
    });

}

const getURLParams = () => {
    const url_params = new URLSearchParams(window.location.search);
    if (!url_params.size) return {};
    return Object.fromEntries(url_params.entries())
}

const getPretty = (metric_name, key)  => {
    if (METRIC_MAPPINGS[metric_name] == null || METRIC_MAPPINGS[metric_name][key] == null) {
        console.log(metric_name, ' is undefined in METRIC_MAPPINGS or has no key');
        return `${metric_name}_${key}`;
    }
    return METRIC_MAPPINGS[metric_name][key];
}

// We are using now the STDDEV of the sample for two reasons:
// It is required by the Blue Angel for Software
// We got many debates that in cases where the average is only estimated through measurements and is not absolute
// one MUST use the sample STDDEV.
// Still one could argue that one does not want to characterize the measured software but rather the measurement setup
// it is safer to use the sample STDDEV as it is always higher
const calculateStatistics = (data, object_access=false) => {
    let sum = null;
    let stddev = null;
    let mean = null;
    if (object_access == true) {
        sum = data.reduce((sum, value) => sum + value.value, 0)
        mean = sum / data.length;
        if (data.length < 2) {
            stddev = 0
        } else {
            stddev = Math.sqrt(data.reduce((sum, value) => sum + Math.pow(value.value - mean, 2), 0) / (data.length - 1) );
        }
    } else {
        sum = data.reduce((sum, value) => sum + value, 0)
        mean = sum / data.length;
        if (data.length < 2) {
            stddev = 0
        } else {
            stddev = Math.sqrt(data.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / (data.length - 1) );
        }
    }
    const stddev_rel = (stddev / mean) * 100;

    return [ mean, stddev, sum, stddev_rel ];
}


const replaceRepoIcon = (uri) => {

  uri = String(uri)
  if(!uri.startsWith('http')) return escapeString(uri); // ignore filesystem paths, but escape them for HTML

  let url;
  try {
    url = new URL(uri);
  } catch (error) {
    // If URL parsing fails (malicious or malformed URI), safely escape and return
    return escapeString(uri);
  }

  let iconClass = "";
  switch (url.host) {
    case "github.com":
    case "www.github.com":
      iconClass = "github";
      break;
    case "bitbucket.com":
    case "www.bitbucket.com":
      iconClass = "bitbucket";
      break;
    case "gitlab.com":
    case "www.gitlab.com":
      iconClass = "gitlab";
      break;
    default:
      return escapeString(uri);
  }
  return `<i class="icon ${iconClass}"></i>` + escapeString(uri.substring(url.origin.length));
};

const createExternalIconLink = (url) => {
    // Creates a safe external icon link with protocol validation to prevent XSS attacks
    // Only allows http/https protocols, returns empty string for non-HTTP URLs
    if (url && url.startsWith('http')) {
        return `<a href="${url}" target="_blank"><i class="icon external alternate"></i></a>`;
    }
    return '';
}

const showNotification = (message_title, message_text, type='error') => {
    if (typeof message_text === 'object') console.log(message_text); // this is most likey an error. We need it in the console

    const message = (typeof message_text === 'string' || typeof message_text === 'object') ? message_text : JSON.stringify(message_text);
    $('body')
      .toast({
        class: type,
        showProgress: 'top',
        position: 'top right',
        displayTime: 5000,
        title: message_title,
        message: message,
    });
    return;
}

const copyToClipboard = async (e) => {
  e.preventDefault();
  
  if (!navigator?.clipboard?.writeText) {
    alert('Clipboard API not supported');
    return;
  }
  
  try {
    const htmlContent = e.currentTarget.previousElementSibling.innerHTML;
    await navigator.clipboard.writeText(htmlContent);
  } catch (err) {
    alert('Failed to copy HTML content to clipboard!');
  }
};

const dateToYMD = (date, short=false, no_break=false) => {
    let day = date.getDate().toString().padStart(2, '0');
    let month = (date.getMonth() + 1).toString().padStart(2, '0'); //Month from 0 to 11
    let hours = date.getHours().toString().padStart(2, '0');
    let minutes = date.getMinutes().toString().padStart(2, '0');
    let offset = date.getTimezoneOffset();
    offset = offset < 0 ? `+${-offset/60}` : -offset/60;

    if(short) return `${date.getFullYear().toString()}-${month}-${day}`;
    const breaker = (no_break === true) ? '' : '<br>';
    return ` ${date.getFullYear()}-${month}-${day} ${breaker} ${hours}:${minutes} UTC${offset}`;
}

const escapeString = (string) =>{
    let my_string = String(string)
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#x27;'
    };
    const reg = /[&<>"']/ig;
    return my_string.replace(reg, (match) => map[match]);
  }

async function makeAPICall(path, values=null, force_authentication_token=null, force_put=false) {

    if(values != null ) {
        var options = {
            method: "POST",
            body: JSON.stringify(values),
            headers: {
                'Content-Type': 'application/json'
            }
        }
        if (force_put == true) {
            options.method = 'PUT';
        }
    }  else {
        var options = { method: 'GET', headers: {} }
    }

    if (force_authentication_token != null && force_authentication_token != '') {
        options.headers['X-Authentication'] = force_authentication_token;
    } else {
        const authentication_token = localStorage.getItem('authentication_token');
        if (authentication_token != null && authentication_token != '') {
            options.headers['X-Authentication'] = authentication_token;
        }
    }

    let json_response = null;
    if(localStorage.getItem('remove_idle') === 'true') path += (path.includes('?') ? '&' : '?') + 'remove_idle=true'

    await fetch(API_URL + path, options)
    .then(response => {
        if (response.status == 204) {
            // 204 responses use no body, so json() call would fail
            throw new APIEmptyResponse204('No data to display. API returned empty response (HTTP 204)')
        }
        if (response.status == 202) {
            return
        }

        return response.json()
    })
    .then(my_json => {
        if (my_json != null && my_json.success != true) {
            if (Array.isArray(my_json.err) && my_json.err.length !== 0)
                throw my_json.err[0]?.msg
            else
                throw my_json.err
        }
        json_response = my_json
    })
    return json_response;
};

/* Menu toggling */
let openMenu = function(){
    $(this).removeClass('closed').addClass('opened');
    $('#menu').removeClass('closed').addClass('opened');
    $('#main').removeClass('closed').addClass('opened');
    setTimeout(function(){window.dispatchEvent(new Event('resize'))}, 500) // needed for the graphs to resize
    localStorage.setItem('menu_closed', false)

}

let closeMenu = function(){
    $(this).removeClass('opened').addClass('closed');
    $('#menu').removeClass('opened').addClass('closed');
    $('#main').removeClass('opened').addClass('closed');
    setTimeout(function(){window.dispatchEvent(new Event('resize'))}, 500) // needed for the graphs to resize
    localStorage.setItem('menu_closed', true)
}

async function sortDate() {
    const button = document.querySelector('#sort-button')
    button.removeEventListener('click', sortDate);
    button.addEventListener('click', sortName);
    button.innerHTML = '<i class="font icon"></i>Sort name';
    await getRepositories('date');
}

async function sortName() {
    const button = document.querySelector('#sort-button')
    button.removeEventListener('click', sortName);
    button.addEventListener('click', sortDate);
    button.innerHTML = '<i class="clock icon"></i>Sort date';
    await getRepositories('name');
}

const numberFormatter = new Intl.NumberFormat('en-US', {
  style: 'decimal', // You can also use 'currency', 'percent', or 'unit'
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const numberFormatterLong = new Intl.NumberFormat('en-US', {
  style: 'decimal',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

$(document).ready(function () {
    $(document).on('click','#menu-toggle.closed', openMenu);
    $(document).on('click','#menu-toggle.opened', closeMenu);

    if ($(window).width() < 960 || localStorage.getItem('menu_closed') === 'true') {
        $('#menu-toggle').removeClass('opened').addClass('closed');
        $('#menu').removeClass('opened').addClass('closed');
        $('#main').removeClass('opened').addClass('closed');
    }
});

if (localStorage.getItem('closed_descriptions') == null) {
    localStorage.setItem('closed_descriptions', '');
}

$(document).ready(() => {
    $("body").removeClass("preload"); // activate tranisition CSS properties again
    const closed_descriptions = localStorage.getItem('closed_descriptions');
    $('.close').on('click', function() {
        $(this).closest('.ui').transition('fade');
        localStorage.setItem('closed_descriptions', `${closed_descriptions},${window.location.pathname}`)
    });
    if (closed_descriptions.indexOf(window.location.pathname) !== -1) {
        document.querySelectorAll('i.close.icon').forEach(el => { el.closest('.ui').remove()}
        )
    }
    resolveMachinesToGlobalVariable();
});

