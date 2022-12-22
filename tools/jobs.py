import sys, os
import runner
import subprocess
import faulthandler

faulthandler.enable() # will catch segfaults and write to STDERR

sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
import error_helpers
import email_helpers
from global_config import GlobalConfig

from db import DB
from runner import Runner

def insert_job(job_type, project_id=None):
    query = """
            INSERT INTO
                jobs (type, failed, running, created_at, project_id)
            VALUES
                (%s, FALSE, FALSE, NOW(), %s) RETURNING id;
            """
    params = (job_type, project_id,)
    job_id = DB().fetch_one(query, params=params)[0]
    return job_id

# do the first job you get.
def get_job(job_type):
    clear_old_jobs()
    query = "SELECT id, type, project_id FROM jobs WHERE failed=false AND type=%s ORDER BY created_at ASC LIMIT 1"

    return DB().fetch_one(query, (job_type,))


def delete_job(job_id):
    query = "DELETE FROM jobs WHERE id=%s"
    params = (job_id,)
    DB().query(query, params=params)

# if there is no job of that type running, set this job to running
def check_job_running(job_type, job_id):
    query = "SELECT FROM jobs WHERE running=true AND type=%s"
    params = (job_type,)
    data = DB().fetch_one(query, params=params)
    if data is not None:
        error_helpers.log_error('Job was still running: ', job_type, job_id) # No email here, only debug
        exit(1) #is this the right way to exit here?
    else:
        query_update = "UPDATE jobs SET running=true, last_run=NOW() WHERE id=%s"
        params_update =  (job_id,)
        DB().query(query_update, params=params_update)


def clear_old_jobs():
    query = "DELETE FROM jobs WHERE last_run < NOW() - INTERVAL '20 minutes' AND failed=false"
    DB().query(query)

def get_project(project_id):
    data = DB().fetch_one("SELECT uri,email FROM projects WHERE id = %s LIMIT 1", (project_id, ))

    if(data is None or data == []):
        raise RuntimeError(f"couldn't find project w/ id: {project_id}")

    return data

def process_job(job_id, job_type, project_id):
    try:
        if job_type == "email":
            _do_email_job(job_id, project_id)
        elif job_type ==  "project":
            _do_project_job(job_id, project_id)
        else:
            raise RuntimeError(f"Job w/ id {job_id} has unkown type: {job_type}.")
    except Exception as e:
        DB().query("UPDATE jobs SET failed=true, running=false WHERE id=%s", params=(job_id,))
        raise e

def _do_email_job(job_id, project_id): # should not be called without enclosing try-except block
    check_job_running('email', job_id)

    [uri, email] = get_project(project_id)

    email_helpers.send_report_email(email, project_id)
    delete_job(job_id)

def _do_project_job(job_id, project_id): # should not be called without enclosing try-except block
    check_job_running('project', job_id)

    [uri, email] = get_project(project_id)

    runner = Runner(skip_unsafe=True)
    try:
        runner.run(uri=uri, uri_type='URL', project_id=project_id) # Start main code. Only URL is allowed for cron jobs
        runner.cleanup()
        insert_job("email", project_id=project_id)
        delete_job(job_id)
    except Exception as e:
        runner.cleanup() # catch so we can cleanup
        raise e

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("type", help="Select the operation mode.", choices=['email', 'project'])
    args = parser.parse_args() # script will exit if type is not present

    # Debug
    #p = "8a4384d7-19a7-4d48-ac24-132d7db52671"
    #print("Inserted Job ID: ", insert_job("project", p))

    project_id = None
    try:
        job = get_job(args.type)
        if(job is None or job == []):
            print("No job to process. Exiting")
            exit(0)
        project_id = job[2]
        process_job(*job)
        print("Successfully processed jobs queue item.")
    except Exception as e:
        error_helpers.log_error("Base exception occured in jobs.py: ", e)
        email_helpers.send_error_email(GlobalConfig().config['admin']['email'], error_helpers.format_error("Base exception occured in jobs.py: ", e), project_id=project_id)
        if project_id is not None:
            [uri, email] = get_project(project_id)
            email_helpers.send_error_email(email, e, project_id=project_id) # reduced error message to client


