const display_in_joules = localStorage.getItem('display_in_joules') === 'true';

const transformIfNotNull = (value, divide_by) => {
    if (value == null) return null;
    return (value / divide_by);
}

// we do not allow a dynamic rescaling here, as we need all the units we feed into
// to be on the same order of magnitude for comparisons and calcuations
//
// Function furthemore uses .substr instead of just replacing the unit, as some units have demominators like Bytes/s or
// ugCO2e/ page request which we want to retain
const convertValue = (value, unit) => {

    const compare_unit = unit.split('/', 2)[0]

    switch (compare_unit) {
        case 'ugCO2e':
            return [transformIfNotNull(value, 1_000_000), unit.substr(1)]
        case 'mJ':
            if (display_in_joules)
                return [transformIfNotNull(value, 1_000), unit.substr(1)];
            else
                return [transformIfNotNull(value, 3_600), `mWh${unit.substr(2)}`];
        case 'uJ':
            if (display_in_joules)
                return [transformIfNotNull(value, 1_000_000), unit.substr(1)];
            else
                return [transformIfNotNull(value, 1_000 * 3_600), `mWh${unit.substr(2)}`];
        case 'mW':
            return [transformIfNotNull(value, 1_000), unit.substr(1)];
        case 'Ratio':
            return [transformIfNotNull(value, 100), `%${unit.substr(5)}`];
        case 'centi°C':
            return [transformIfNotNull(value, 100), unit.substr(5)];
        case 'Hz':
            return [transformIfNotNull(value, 1_000_000_000), `G${unit}`];
        case 'ns':
            return [transformIfNotNull(value, 1_000_000_000), unit.substr(1)];
        case 'us':
            return [transformIfNotNull(value, 1_000_000), unit.substr(1)];
        case 'ug':
            return [transformIfNotNull(value, 1_000_000), unit.substr(1)]
        case 'Bytes':
            return [transformIfNotNull(value, 1_000_000), `MB${unit.substr(5)}`];
        default:
            return [value, unit];        // no conversion in default case
    }
}

const rescaleCO2Value = (value,unit) => {
    if     (value > 1_000_000_000) return [(value/(10**9)).toFixed(2), 'kg'];
    else if(value > 1_000_000) return [(value/(10**6)).toFixed(2), 'g'];
    else if(value > 1_000) return [(value/(10**3)).toFixed(2), 'mg'];
    return [value.toFixed(2) , unit];
}

