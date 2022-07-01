import sys, os
from setup_functions import get_config
import error_helpers

sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
from db import DB

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
def get_job():


    clear_old_jobs()
    query = "SELECT id, type, project_id FROM jobs WHERE failed=false ORDER BY created_at ASC LIMIT 1"
    data = DB().fetch_one(query)
    if(data is None or data == []):
        print("No job to process. Exiting")
        exit(0)

    match data[1]:
        case "mail":
            do_mail_job(data[0], data[2])
        case _:
            error_helpers.log_error("Job w/ id %s has unkown type: %s." % (data[0], data[1]))

def delete_job(job_id):
    query = "DELETE FROM jobs WHERE id=%s AND failed=FALSE"
    params = (job_id,)
    DB().query(query, params=params)

# if there is no job of that type running, set this job to running
def check_job_running(job_type, job_id):
    query = "SELECT FROM jobs WHERE running=true AND type=%s"
    params = (job_type,)
    data = DB().fetch_one(query, params=params)
    if data is not None:
        exit(0) #is this the right way to exit here?
    else:
        query_update = "UPDATE jobs SET running=true WHERE id=%s"
        params_update =  (job_id,)
        DB().query(query_update, params=params_update)

def clear_old_jobs():
    query = "DELETE FROM jobs WHERE created_at < NOW() - INTERVAL '20 minutes' AND failed=false"
    DB().query(query)

def do_mail_job(job_id, project_id):
    check_job_running('mail', job_id)
    try:
        config = get_config()
        query = "SELECT email FROM projects WHERE id = %s"
        params = (project_id,)
        data = DB().fetch_one(query, params=params)
        if(data is None or data == []):
            raise Exception(f"couldn't find project w/ id: {project_id}")

        from send_email import send_report_email
        send_report_email(config, data[0], project_id)
        delete_job(job_id)
    except Exception as e:
        error_helpers.log_error("Exception occured: ", e)
        query_update = "UPDATE jobs SET failed=true WHERE job_id=%s"
        params_update = (job_id,)
        DB().query(query_update, params=params_update)


if __name__ == "__main__":
    import argparse
    import yaml
    from setup_functions import get_config

    config = get_config()

    p = "87851711-866f-433e-8117-2c54045a90ec"
    insert_job("mail", p)
    get_job()