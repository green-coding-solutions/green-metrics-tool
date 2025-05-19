from lib import utils

class DiskIoParseMixin:
    def _parse_metrics_splitup_helper(self, df):

        df = df.sort_values(by=['detail_name', 'time'], ascending=True)

        df['written_bytes_intervals'] = df.groupby(['detail_name'])['written_bytes'].diff()
        df['written_bytes_intervals'] = df.groupby('detail_name')['written_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        df['read_bytes_intervals'] = df.groupby(['detail_name'])['read_bytes'].diff()
        df['read_bytes_intervals'] = df.groupby('detail_name')['read_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        if (df['read_bytes_intervals'] < 0).any():
            raise ValueError(f"{self.__class__.__name__} data column read_bytes_intervals had negative values.")

        if (df['written_bytes_intervals'] < 0).any():
            raise ValueError(f"{self.__class__.__name__} data column written_bytes_intervals had negative values.")

        base_cols = ['time', 'detail_name']

        df_read = (
            df[base_cols + ["read_bytes_intervals"]]
            .rename(columns={"read_bytes_intervals": "value"})
            .copy()
        )
        df_read["value"] = df_read["value"].astype('int64')
        df_read['unit'] = self._unit
        df_read['metric'] = self._sub_metrics_name[0]

        df_written = (
            df[base_cols + ["written_bytes_intervals"]]
            .rename(columns={"written_bytes_intervals": "value"})
            .copy()
        )
        df_written["value"] = df_written["value"].astype('int64')
        df_written['unit'] = self._unit
        df_written['metric'] = self._sub_metrics_name[1]

        return [df_read, df_written]
