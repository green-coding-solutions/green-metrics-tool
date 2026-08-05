import pandas

def expand_to_sampling_rate(self, df):
    if df.empty or self._sampling_rate is None:
        return df

    if self._sampling_rate <= 0:
        return df

    if self._start_time is None or self._end_time is None:
        return df

    step_us = int(self._sampling_rate) * 1_000
    if step_us <= 0:
        raise RuntimeError(f"Invalid sampling_rate configured for {self._metric_name}: {self._sampling_rate}")

    start_us = int(self._start_time.timestamp() * 1_000_000)
    end_us = int(self._end_time.timestamp() * 1_000_000)

    if end_us < start_us:
        return df

    expanded_records = []
    provider_values = df['provider'].drop_duplicates().tolist()

    for provider_name in provider_values:
        if pandas.isna(provider_name):
            provider_df = df[df['provider'].isna()]
        else:
            provider_df = df[df['provider'] == provider_name]

        provider_df = provider_df.sort_values(by='time', ascending=True)
        source_times = provider_df['time'].tolist()
        source_values = provider_df['value'].tolist()

        if not source_times:
            continue

        current_index = 0
        while current_index + 1 < len(source_times) and source_times[current_index + 1] <= start_us:
            current_index += 1

        change_times = []
        last_change_time = None
        for source_time in source_times:
            if source_time < start_us or source_time > end_us:
                continue
            if source_time == last_change_time:
                continue
            change_times.append(source_time)
            last_change_time = source_time

        sample_time = start_us
        change_idx = 0

        while sample_time <= end_us or change_idx < len(change_times):
            next_grid_time = sample_time if sample_time <= end_us else None
            next_change_time = change_times[change_idx] if change_idx < len(change_times) else None

            if next_grid_time is None or (next_change_time is not None and next_change_time < next_grid_time):
                emit_time = next_change_time
                change_idx += 1
            elif next_change_time is not None and next_change_time == next_grid_time:
                emit_time = next_grid_time
                change_idx += 1
                sample_time += step_us
            else:
                emit_time = next_grid_time
                sample_time += step_us

            while current_index + 1 < len(source_times) and source_times[current_index + 1] <= emit_time:
                current_index += 1

            expanded_records.append({
                'time': emit_time,
                'value': int(source_values[current_index]),
                'provider': provider_name,
            })

    if not expanded_records:
        return df.iloc[0:0].copy()

    return (
        pandas.DataFrame.from_records(expanded_records)
        .sort_values(by=['time', 'provider'], kind='stable')
        .reset_index(drop=True)
    )
