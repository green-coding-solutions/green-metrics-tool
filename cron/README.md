## What is in here?

The cron folder contains all scripts that are either invoked by an actual *cron job* or by a newer
style of a *systemd* service.

For instance `jobs.py` is used to start an email or runner job in a one-off fashion.

While `client.py` is designed to be used as a continously running service.

Some files may include a `__main__` guard clause and can also be directly executed. This is however only
to test the file manually and not the intended production use.

## Recommended cron job and services setups

Please refer to the documentation under https://docs.green-coding.io/docs/cron-jobs-and-services