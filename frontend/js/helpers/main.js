/*
    WebComponent function without ShadowDOM
    to expand the menu in the HTML pages
*/
class GMTMenu extends HTMLElement {
   connectedCallback() {
        this.innerHTML = `
        <div id="menu" class="ui inverted vertical menu">
            <div>
                <img class="ui fluid image menu-logo" src="/images/logo.png">
            </div>
            <div class="item">
                <i>&lt;Green Metrics Tool&gt;</i>
            </div>
            <a class="item" href="/index.html">
                <b><i class="home icon"></i>Home</b>
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
            <a class="item" href="/settings.html">
                <b><i class="cogs icon"></i>Settings</b>
            </a>
        </div> <!-- end menu -->`;
    }
}
customElements.define('gmt-menu', GMTMenu);

const replaceRepoIcon = (uri) => {
    if (uri.startsWith("https://www.github.com") || uri.startsWith("https://github.com")) {
        uri = uri.replace("https://www.github.com", '<i class="icon github"></i>');
        uri = uri.replace("https://github.com", '<i class="icon github"></i>');
    } else if (uri.startsWith("https://www.bitbucket.com") || uri.startsWith("https://bitbucket.com")) {
        uri = uri.replace("https://www.bitbucket.com", '<i class="icon bitbucket"></i>');
        uri = uri.replace("https://bitbucket.com", '<i class="icon bitbucket"></i>');
    } else if (uri.startsWith("https://www.gitlab.com") || uri.startsWith("https://gitlab.com")) {
        uri = uri.replace("https://www.gitlab.com", '<i class="icon gitlab"></i>');
        uri = uri.replace("https://gitlab.com", '<i class="icon gitlab"></i>');
    }
    return uri;
}

const showNotification = (message_title, message_text, type='warning') => {
    $('body')
      .toast({
        class: type,
        showProgress: 'top',
        position: 'top right',
        displayTime: 5000,
        title: message_title,
        message: message_text,
        className: {
            toast: 'ui message'
        }
    });
    return;
}

const copyToClipboard = (e) => {
  if (navigator && navigator.clipboard && navigator.clipboard.writeText)
    return navigator.clipboard.writeText(e.currentTarget.closest('div.inline.field').querySelector('span').innerHTML)

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

    if(short) return `${date.getFullYear().toString().substr(-2)}.${month}.${day}`;
    return ` ${date.getFullYear()}-${month}-${day} <br> ${hours}:${minutes} UTC${offset}`;
}

const escapeString = (string) =>{
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#x27;'
    };
    const reg = /[&<>"']/ig;
    return string.replace(reg, (match) => map[match]);
  }

async function makeAPICall(path, values=null) {

    if(values != null ) {
        var options = {
            method: "POST",
            body: JSON.stringify(values),
            headers: {
                'Content-Type': 'application/json'
            }
        }
    }  else {
        var options = { method: 'GET' }
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

(() => {
    /* Menu toggling */
    let openMenu = function(e){
        $(this).removeClass('closed').addClass('opened');
        $(this).find('i').removeClass('right').addClass('left');
        $('#menu').removeClass('closed').addClass('opened');
        $('#main').removeClass('closed').addClass('opened');
        setTimeout(function(){window.dispatchEvent(new Event('resize'))}, 500) // needed for the graphs to resize
    }
    $(document).on('click','#menu-toggle.closed', openMenu);

    let closeMenu = function(e){
        $(this).removeClass('opened').addClass('closed');
        $(this).find('i').removeClass('left').addClass('right');
        $('#menu').removeClass('opened').addClass('closed');
        $('#main').removeClass('opened').addClass('closed');
        setTimeout(function(){window.dispatchEvent(new Event('resize'))}, 500) // needed for the graphs to resize
    }

    $(document).on('click','#menu-toggle.opened', closeMenu);
    $(document).ready(function () {
        if ($(window).width() < 960) {
            $('#menu-toggle').removeClass('opened').addClass('closed');
        }
    });

    $(window).on('load', function() {
      $("body").removeClass("preload"); // activate tranisition CSS properties again
    });

})();
