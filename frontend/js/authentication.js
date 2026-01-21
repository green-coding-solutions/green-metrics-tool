(() => {
    $(window).on('load', function() {
        const authentication_token = localStorage.getItem('authentication_token');
        if (authentication_token != null) {
            $("#authentication-token").val(authentication_token);
        }
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

    $('#clear-authentication-token').on('click', function(){
        $('#login-successful-message').hide();
        $('#token-details-message').hide();
        localStorage.removeItem('authentication_token');
        localStorage.removeItem('user_name');
        $('#logout-successful-message').show();
        setTimeout(() => {
          window.location.reload();
        }, 60000);
    })


    $('#save-authentication-token').on('click', async function(){

        const authentication_token = $("#authentication-token").val().trim();
        if (authentication_token == '') {
            showNotification('Please enter a non-empty authentication token');
            return false;
        }
        try {
            $('#logout-successful-message').hide();
            $('#login-successful-message').hide();
            $('#token-details-message').hide();
            const user_data = await makeAPICall('/v1/user/settings', null, authentication_token);

            localStorage.setItem('authentication_token', authentication_token);
            localStorage.setItem('user_name', user_data.data._name);
            localStorage.setItem('show_other_users', 'false'); // default setting on new login different from DEFAULT user

            $('#login-successful-message').show();
            $('#token-details-message').show();
            $('#token-details').text(JSON.stringify(user_data.data, null, 2));
            setTimeout(() => {
              window.location.reload();
            }, 60000);

        } catch (err) {
            showNotification('Could not read authentication token data', err);
        }
    })

})();
