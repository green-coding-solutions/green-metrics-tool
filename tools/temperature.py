import os
import subprocess
from lib.global_config import GlobalConfig

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_temperature(chip, feature):
    if not feature or not chip:
        raise RuntimeError('You must set "base_temperature_chip" and "base_temperature_feature" in the config file. Please use calibration script to determine value.')

    try:
        output = subprocess.check_output(
            [f"{CURRENT_DIR}/../metric_providers/lmsensors/metric-provider-binary", '-c', chip, '-f', feature, '-n', '1'],
            encoding='UTF-8',
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError('Could not get system temperature. Did you install lmsensors and the corresponding metric provider correctly?') from exc

    return int(output.split(' ')[1])/100

if __name__ == '__main__':
    cur = get_temperature(
        GlobalConfig().config['machine']['base_temperature_chip'],
        GlobalConfig().config['machine']['base_temperature_feature']
    )
    print('Current temperature is', cur)
    print('Base temperature is', GlobalConfig().config['machine']['base_temperature_value'])
