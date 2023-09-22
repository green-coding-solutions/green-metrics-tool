const convertValue = (value, unit) => {
    // we do not allow a dynamic rescaling here, as we need all the units we feed into
    // to be on the same order of magnitude

    if (value == null) return [value, unit];

    if(unit.startsWith('ugCO2e/')) return [(value/(10**3)).toFixed(2), `m${unit.substr(1)}`]

    switch (unit) {
    case 'mJ':
        return [(value / 1_000).toFixed(2), 'J'];
        break;
    case 'mW':
        return [(value / 1_000).toFixed(2), 'W'];
        break;
    case 'Ratio':
        return [(value / 100).toFixed(2), '%'];
        break;
    case 'centi°C':
        return [(value / 100).toFixed(2), '°C'];
        break;
    case 'Hz':
        return [(value / 1000000).toFixed(2), 'GHz'];
        break;
    case 'ns':
        return [(value / 1_000_000_000).toFixed(2), 's'];
        break;
    case 'us':
        return [(value / 1_000_000).toFixed(2), 's'];
        break;
    case 'ug':
        return [(value/(10**3)).toFixed(2), 'mg']
        break;
    case 'Bytes':
        return [(value / 1_000_000).toFixed(2), 'MB'];
        break;
    default:
        return [value, unit];        // no conversion in default calse
    }
}

const rescaleCO2Value = (value,unit) => {
    if     (value > 1_000_000_000) return [(value/(10**9)).toFixed(2), 'kg'];
    else if(value > 1_000_000) return [(value/(10**6)).toFixed(2), 'g'];
    else if(value > 1_000) return [(value/(10**3)).toFixed(2), 'mg'];
    return [value.toFixed(2) , unit];
}
