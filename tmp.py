import psycopg2
con = psycopg2.connect("dbname=green_coding user=postgres")
cur = con.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
for row in cur.fetchall(): print(row[0])
con.close()
