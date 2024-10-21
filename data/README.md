## Import

To import the data to your local DB just run this command from the same directory:

```bash
docker exec -i --user postgres green-coding-postgres-container psql -dgreen-coding -p9573 < ./demo_data.sql
```

## Export
To export data for your local use:

```bash
docker exec -i --user postgres green-coding-postgres-container pg_dump -p9573 -dgreen-coding -t my_table > my_table.sql
```

## Export from remote
```bash
pg_dump -U my_user -h my_host -p9573 -c green-coding -t my_table > my_table.sql
```
