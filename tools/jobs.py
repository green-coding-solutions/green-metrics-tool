from setup_functions import get_config
import error_helpers
import sys, os

sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
import db

def insert_job(conn, job_type, project_id=None):
	query =	"""
			INSERT INTO
				jobs (type, failed, running, created_at, project_id)
			VALUES
				(%s, FALSE, FALSE, NOW(), %s) RETURNING id;
			"""
	params = (job_type, project_id,)
	job_id = db.fetch_one(query, params, conn)
	return job_id

# do the first job you get.
def get_job(conn):


	clear_old_jobs(conn)
	query = "SELECT id, type, project_id FROM jobs WHERE failed=false ORDER BY created_at ASC LIMIT 1"
	data = db.fetch_one(query, conn=conn)
	if(data is None or data == []):
		print("No job to process. Exiting")
		exit(0)

	match data[1]:
		case "mail":
			do_mail_job(conn, data[0], data[2])
		case _:
			error_helpers.log_error("Job w/ id %s has unkown type: %s." % (data[0], data[1]))

def delete_job(conn, job_id):
	query = "DELETE FROM jobs WHERE id=%s AND failed=FALSE"
	params = (job_id,)
	db.call(query, params, conn)

# if there is no job of that type running, set this job to running
def check_job_running(conn, job_type, job_id):
	query = "SELECT FROM jobs WHERE running=true AND type=%s"
	params = (job_type,)
	data = db.fetch_one(query, params, conn)
	if data is not None:
		exit(0) #is this the right way to exit here?
	else:
		query_update = "UPDATE jobs SET running=true WHERE id=%s"
		params_update =  (job_id,)
		db.call(query_update, params_update, conn)

def clear_old_jobs(conn):
	query = "DELETE FROM jobs WHERE created_at < NOW() - INTERVAL '20 minutes' AND failed=false"
	db.call(query,conn=conn)

def do_mail_job(conn, job_id, project_id):
	check_job_running(conn, 'mail', job_id)
	try:
		config = get_config()
		query = "SELECT email FROM projects WHERE id = %s"
		params = (project_id,)
		data = db.fetch_one(query, params)
		if(data is None or data == []):
			raise Exception(f"couldn't find project w/ id: {project_id}")
			
		from send_email import send_report_email
		send_report_email(config, data[0], project_id)
		delete_job(conn, job_id)
	except Exception as e:
		error_helpers.log_error("Exception occured: ", e)
		query_update = "UPDATE jobs SET failed=true WHERE job_id=%s" 
		params_update = (job_id,)
		db.call(query_update, params_update, conn)


if __name__ == "__main__":
	import argparse
	import yaml
	import os
	import sys
	sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
	from setup_functions import get_config, get_db_connection
	from error_helpers import log_error


	config = get_config()
	conn = db.get_db_connection(config)

	p = "87851711-866f-433e-8117-2c54045a90ec"
	insert_job(conn, "mail", p)
	get_job(conn)