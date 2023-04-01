var display_in_watts = localStorage.getItem('display_in_watts');
if(display_in_watts == 'true') display_in_watts = true;
else display_in_watts = false;

const rescaleCO2Value = (total_CO2_in_kg) => {
    if     (total_CO2_in_kg < 0.0000000001) co2_display = [total_CO2_in_kg*(10**12), 'ng'];
    else if(total_CO2_in_kg < 0.0000001) co2_display = [total_CO2_in_kg*(10**9), 'ug'];
    else if(total_CO2_in_kg < 0.0001) co2_display = [total_CO2_in_kg*(10**6), 'mg'];
    else if(total_CO2_in_kg < 0.1) co2_display = [total_CO2_in_kg*(10**3), 'g'];
    return co2_display;
}

const convertValue = (value, unit) => {
    switch (unit) {
    case 'mJ':
        return [value / 1000, 'J'];
        break;
    case 'mW':
        return [value / 1000, 'W'];
        break;
    case 'Ratio':
        return [value / 100, '%'];
        break;
    case 'centi°C':
        return [value / 100, '°C'];
        break;
    case 'Hz':
        return [value / 1000000, 'GHz'];
        break;
    case 'ns':
        return [value / 1000000000, 's'];
        break;

    case 'Bytes':
        return [value / 1000000, 'MB'];
        break;
    default:
        return [value, unit];        // no conversion in default calse
    }
}