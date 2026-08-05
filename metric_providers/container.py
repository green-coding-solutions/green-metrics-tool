from metric_providers.base import BaseMetricProvider

class ContainerMetricProvider(BaseMetricProvider):
    def __init__(self, *,
            metric_name,
            metrics,
            sampling_rate,
            unit,
            current_dir,
            folder,
            skip_check,
            containers,
    ):
        super().__init__(
            metric_name=metric_name,
            metrics=metrics,
            sampling_rate=sampling_rate,
            unit=unit,
            current_dir=current_dir,
            folder=folder,
            skip_check=skip_check
        )
        self._cgroup_string_tokens = containers if containers else {}


    def _add_extra_switches(self, call_string):
        return f"{call_string} -s {','.join(self._cgroup_string_tokens.keys())}"

    def add_containers(self, containers):
        self._cgroup_string_tokens.update(containers)

    def _parse_metrics(self, df):
        df['detail_name'] = df.container_id
        for token in self._cgroup_string_tokens:
            df.loc[df.detail_name == token, 'detail_name'] = self._cgroup_string_tokens[token]['name']
        df = df.drop('container_id', axis=1)

        return df
