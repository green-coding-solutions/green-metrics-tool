(() => {
    var authentication_token = localStorage.getItem('authentication_token');
    if(authentication_token == null) authentication_token = 'DEFAULT';

    $(window).on('load', function() {
        $("#authentication-token").val(authentication_token);
    })

    // $('#create-authentication-token').on('click', async function(){
    //     try {
    //         $('#new-token-message').hide();
    //         var new_authentication_token = await makeAPICall(`/v1/authentication/new?name=${$("#new-token-name").val()}`);
    //         $('#new-token-message').show();
    //         $('#new-token').text(new_authentication_token.data);
    //     } catch (err) {
    //         showNotification('Could not create new authentication token', err);
    //     }
    // })

    $('#save-authentication-token').on('click', async function(){
        localStorage.setItem('authentication_token', $("#authentication-token").val());
        try {
            $('#token-details-message').hide();
            var user_data = await makeAPICall('/v1/authentication/data');

            $('#token-details-message').show();
            $('#token-details').text(JSON.stringify(user_data.data, null, 2));
        } catch (err) {
            showNotification('Could not read authentication token data', err);
        }
    })

})();
