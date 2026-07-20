(() => {
    const token_field = $("#authentication-token");

    $(window).on('load', function() {
        const authentication_token = localStorage.getItem('authentication_token');
        if (authentication_token != null) {
            token_field.val(authentication_token);
        }
    })

    $('#togglePassword').on('click', function () {

        if (token_field.attr('type') === 'password') {
            token_field.attr('type', 'text');
            $(this)
                .removeClass('eye slash')
                .addClass('eye');
        } else {
            token_field.attr('type', 'password');
            $(this)
                .removeClass('eye')
                .addClass('eye slash');
        }
    });

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

        const authentication_token = token_field.val().trim();
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
