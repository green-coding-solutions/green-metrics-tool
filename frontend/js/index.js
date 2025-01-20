(async () => {
    if (ACTIVATE_ENERGY_ID == true) {
        document.querySelectorAll('.energy-id').forEach(el => el.style.display = 'block')
    };

    if (ACTIVATE_ECO_CI == true) {
        document.querySelectorAll('.eco-ci').forEach(el => el.style.display = 'block')
    };

    if (ACTIVATE_CARBON_DB == true) {
        document.querySelectorAll('.carbon-db').forEach(el => el.style.display = 'block')
    };

    if (ACTIVATE_POWER_HOG == true) {
        document.querySelectorAll('.power-hog').forEach(el => el.style.display = 'block')
    };

})();
