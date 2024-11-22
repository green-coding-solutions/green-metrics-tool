/*
    WebComponent function without ShadowDOM
    to expand the menu in the HTML pages
*/
class GMTMenu extends HTMLElement {
   connectedCallback() {
        this.innerHTML = `
        <div id="menu" class="ui inverted vertical menu">
            <div class="item-container">
                <a class="item" href="/index.html">
                    <b><i class="home icon"></i>Home</b>
                </a>
                <a class="item" href="/repositories.html">
                    <b><i class="code branch icon"></i>Repositories</b>
                </a>
                <a class="item" href="/energy-timeline.html">
                    <b><i class="history icon"></i>Energy Timeline</b>
                </a>
                <a class="item" href="/request.html">
                    <b><i class="bullseye icon"></i>Measure software</b>
                </a>
                <a class="item" href="/data-analysis.html">
                    <b><i class="chartline icon"></i>Data Analysis</b>
                </a>
                <a class="item" href="/ci-index.html">
                    <b><i class="seedling icon"></i>Eco-CI</b>
                </a>
                <a class="item" href="/hog.html">
                    <b><i class="piggy bank icon"></i>Power Hog</b>
                </a>
                <a class="item" href="/carbondb.html">
                    <b><i class="journal whills icon"></i>CarbonDB</b>
                </a>
                <a class="item" href="/status.html">
                    <b><i class="database icon"></i>Status</b>
                </a>
                <a class="item" href="/authentication.html">
                    <b><i class="users icon"></i>Authentication</b>
                </a>
                <a class="item" href="/settings.html">
                    <b><i class="cogs icon"></i>Settings</b>
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
    }
}
customElements.define('gmt-menu', GMTMenu);

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

  if(!uri.startsWith('http')) return uri; // ignore filesystem paths

  const url = new URL(uri);

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
      return uri;
  }
  return `<i class="icon ${iconClass}"></i>` + uri.substring(url.origin.length);
};

const showNotification = (message_title, message_text, type='warning') => {
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
        className: {
            toast: 'ui message'
        }
    });
    return;
}

const copyToClipboard = (e) => {
  e.preventDefault();
  if (navigator && navigator.clipboard && navigator.clipboard.writeText)
    navigator.clipboard.writeText(e.currentTarget.previousElementSibling.innerHTML)
    return false

  alert('Copying badge on local is not working due to browser security models')
  return Promise.reject('The Clipboard API is not available.');
};

const dateToYMD = (date, short=false) => {
    let day = date.getDate().toString().padStart(2, '0');
    let month = (date.getMonth() + 1).toString().padStart(2, '0'); //Month from 0 to 11
    let hours = date.getHours().toString().padStart(2, '0');
    let minutes = date.getMinutes().toString().padStart(2, '0');
    let offset = date.getTimezoneOffset();
    offset = offset < 0 ? `+${-offset/60}` : -offset/60;

    if(short) return `${date.getFullYear().toString()}-${month}-${day}`;
    return ` ${date.getFullYear()}-${month}-${day} <br> ${hours}:${minutes} UTC${offset}`;
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

async function makeAPICall(path, values=null, force_authentication_token=null) {


    if(values != null ) {
        var options = {
            method: "POST",
            body: JSON.stringify(values),
            headers: {
                'Content-Type': 'application/json'
            }
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
    if(localStorage.getItem('remove_idle') == 'true') path += "?remove_idle=true"
    await fetch(API_URL + path, options)
    .then(response => {
        if (response.status == 204) {
            // 204 responses use no body, so json() call would fail
            return {success: false, err: "Data is empty"}
        }
        return response.json()
    })
    .then(my_json => {
        if (my_json.success != true) {
            throw my_json.err
        }
        json_response = my_json
    })
    return json_response;
};

/* Menu toggling */
let openMenu = function(e){
    $(this).removeClass('closed').addClass('opened');
    $('#menu').removeClass('closed').addClass('opened');
    $('#main').removeClass('closed').addClass('opened');
    setTimeout(function(){window.dispatchEvent(new Event('resize'))}, 500) // needed for the graphs to resize
    localStorage.setItem('menu_closed', false)

}

let closeMenu = function(e){
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

$(document).ready(function () {
    $(document).on('click','#menu-toggle.closed', openMenu);
    $(document).on('click','#menu-toggle.opened', closeMenu);

    if ($(window).width() < 960 || localStorage.getItem('menu_closed') == 'true') {
        $('#menu-toggle').removeClass('opened').addClass('closed');
        $('#menu').removeClass('opened').addClass('closed');
        $('#main').removeClass('opened').addClass('closed');
    }
});

$(window).on('load', function() {
    $("body").removeClass("preload"); // activate tranisition CSS properties again
    $('.close')
      .on('click', function() {
        $(this)
          .closest('.ui')
          .transition('fade')
        ;
      })
    ;
});

