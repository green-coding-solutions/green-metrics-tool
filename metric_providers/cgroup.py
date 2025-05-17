from lib import utils
from metric_providers.base import BaseMetricProvider

class CgroupMetricProvider(BaseMetricProvider):
    def __init__(self, *,
            metric_name,
            metrics,
            sampling_rate,
            unit,
            current_dir,
            skip_check,
            cgroups,
    ):
        super().__init__(
            metric_name=metric_name,
            metrics=metrics,
            sampling_rate=sampling_rate,
            unit=unit,
            current_dir=current_dir,
            skip_check=skip_check
        )
        self._cgroup_string_tokens = cgroups.copy() if cgroups else {} # because it can be a frozen dict, we need to copy
        self._cgroup_string_tokens[utils.find_own_cgroup_name()] = {'name': 'GMT Overhead'} # we also find the cgroup that the GMT process belongs to. It will be a user session

    def _add_extra_switches(self, call_string):
        return f"{call_string} -s {','.join(self._cgroup_string_tokens.keys())}"

    def _parse_metrics(self, df):
        df['detail_name'] = df.cgroup_str
        for token in self._cgroup_string_tokens:
            df.loc[df.detail_name == token, 'detail_name'] = self._cgroup_string_tokens[token]['name']
        df = df.drop('cgroup_str', axis=1)

        return df
