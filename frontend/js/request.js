(() => {
    document.forms[0].onsubmit = async (e) => {
        e.preventDefault();

        const data = new FormData(document.querySelector('form'));
        const values = Object.fromEntries(data.entries());

        makeAPICall('/v1/project/add', (my_json) => {
            document.forms[0].reset()
            $('body')
              .toast({
                class: 'success',
                showProgress: 'bottom',
                classProgress: 'green',
                title: 'Success',
                message: 'Save successful. Check your mail in 10-15 minutes'
            });
        }, values);
    }
})();