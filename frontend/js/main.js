let showNotification = (message_title, message_text, type='warning') => {
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


async function makeAPICall(path, values=null) {
    if (document.location.host.indexOf('metrics.green-coding.local') === 0)
        api_url = "http://api.green-coding.local:9142";
    else
        api_url = "https://api.green-coding.berlin";

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
    await fetch(api_url + path, options)
        .then(response => response.json())
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
