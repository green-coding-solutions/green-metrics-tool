
const makeAPICall = (path, callback, values=null) => {
    try {
        if (document.location.host.indexOf('metrics.green-coding.org') === 0)
            api_url = "https://api.green-coding.org";
        else
            api_url = "http://api.green-coding.local:8000";

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

        fetch(api_url + path, options)
            .then(response => response.json())
            .then(my_json => {
                if (my_json.success != true) {
                    alert(my_json.err);
                    return;
                }
                callback(my_json);
            })
    } catch (e) {
        alert("Fetch failed: " + e)
    }
};

(() => {
    /* Menu toggling */
    let openMenu = function(e){
        $(this).removeClass('closed').addClass('opened');
        $(this).find('i').removeClass('right').addClass('left');
        $('#menu').removeClass('collapsed');
        $('#main').removeClass('collapsed');

    }
    $(document).on('click','#menu-toggle.closed', openMenu);

    let closeMenu = function(e){
        $(this).removeClass('opened').addClass('closed');
        $(this).find('i').removeClass('left').addClass('right');
        $('#menu').addClass('collapsed');
        $('#main').addClass('collapsed');
    }

    $(document).on('click','#menu-toggle.opened', closeMenu);
})();
