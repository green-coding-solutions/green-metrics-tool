import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../lib")

import error_helpers
import setup_functions

def insert_job(conn, job_type, project_id=None):
	cur = conn.cursor()
	cur.execute("""
		INSERT INTO
			jobs (type, failed, running, created_at, project_id)
		VALUES
			(%s, FALSE, FALSE, NOW(), %s) RETURNING id;
		""",
		(job_type, project_id,))
	conn.commit()
	job_id = cur.fetchone()[0]
	cur.close()
	return job_id

# do the first job you get.
# main function to be called by cron job
def get_job(conn):
	cur = conn.cursor()

	clear_old_jobs(conn)

	cur.execute("SELECT id, type, project_id FROM jobs WHERE failed=false ORDER BY created_at ASC LIMIT 1")
	data = cur.fetchone()
	if(data is None or data == []):
		print("No job to process. Exiting")
		exit(0)

	match data[1]:
		case "mail":
			do_mail_job(conn, data[0], data[2])
		case _:
			error_helpers.log_error("Job w/ id %s has unkown type: %s." % (data[0], data[1]))
	cur.close()

def delete_job(conn, job_id):
	cur = conn.cursor()
	cur.execute("DELETE FROM jobs WHERE id=%s AND failed=FALSE", (job_id,))
	conn.commit()
	cur.close()

# if there is no job of that type running, set this job to running
def check_job_running(conn, job_type, job_id):
	cur = conn.cursor()
	cur.execute("SELECT FROM jobs WHERE running=true AND type=%s", (job_type,))
	data = cur.fetchone()
	if data is not None:
		exit(0) #is this the right way to exit here?
	else:
		cur.execute("UPDATE jobs SET running=true WHERE id=%s", (job_id,))
		conn.commit()
	cur.close()

def clear_old_jobs(conn):
	cur = conn.cursor()
	cur.execute( "DELETE FROM jobs WHERE created_at < NOW() - INTERVAL '20 minutes' AND failed=false")
	conn.commit()
	cur.close()

def do_mail_job(conn, job_id, project_id):
	check_job_running(conn, 'mail', job_id)
	cur = conn.cursor()
	try:
		config = setup_functions.get_config()
		cur.execute("SELECT email FROM projects WHERE id = %s", (project_id,))
		data = cur.fetchone()
		if(data is None or data == []):
			raise Exception(f"couldn't find project w/ id: {project_id}")
			
		from send_email import send_report_email
		#print(data[0])
		send_report_email(config, data[0], project_id)
		delete_job(conn, job_id)
	except Exception as e:
		error_helpers.log_error("Exception occured: ", e)
		cur.execute("UPDATE jobs SET failed=true WHERE job_id=%s", (job_id,))
		conn.commit()
	finally:
		cur.close()


if __name__ == "__main__":
	import argparse
	import yaml
	import os
	import sys
	sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
	from setup_functions import get_config, get_db_connection
	from errors import log_error


	config = get_config()
	conn = get_db_connection(config)

	p = "87851711-866f-433e-8117-2c54045a90ec"
	insert_job(conn, "mail", p)
	get_job(conn)