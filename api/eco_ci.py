from datetime import date

from fastapi import APIRouter
from fastapi import Request, Response, Depends
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError

from api.api_helpers import authenticate, html_escape_multi, get_connecting_ip, rescale_metric_value
from api.object_specifications import CI_Measurement_Old, CI_Measurement

import anybadge

from xml.sax.saxutils import escape as xml_escape

from lib import error_helpers
from lib.user import User
from lib.db import DB

router = APIRouter()


@router.post('/v1/ci/measurement/add')
async def post_ci_measurement_add_deprecated(
    request: Request,
    measurement: CI_Measurement_Old,
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    measurement = html_escape_multi(measurement)

    used_client_ip = get_connecting_ip(request)

    co2i_transformed = int(measurement.co2i) if measurement.co2i else None

    co2eq_transformed = int(float(measurement.co2eq)*1000000) if measurement.co2eq else None

    query = '''
        INSERT INTO
            ci_measurements (energy_uj,
                            repo,
                            branch,
                            workflow_id,
                            run_id,
                            label,
                            source,
                            cpu,
                            commit_hash,
                            duration_us,
                            cpu_util_avg,
                            workflow_name,
                            lat,
                            lon,
                            city,
                            carbon_intensity_g,
                            carbon_ug,
                            filter_type,
                            filter_project,
                            filter_machine,
                            filter_tags,
                            user_id,
                            ip_address
                            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''

    params = ( measurement.energy_value*1000, measurement.repo, measurement.branch,
            measurement.workflow, measurement.run_id, measurement.label, measurement.source, measurement.cpu,
            measurement.commit_hash, measurement.duration*1000000, measurement.cpu_util_avg, measurement.workflow_name,
            measurement.lat, measurement.lon, measurement.city, co2i_transformed, co2eq_transformed,
            'machine.ci', 'CI/CD', 'unknown', [],
            user._id, used_client_ip)


    DB().query(query=query, params=params)

    if measurement.energy_value <= 1 or (measurement.co2eq and co2eq_transformed <= 1):
        error_helpers.log_error(
            'Extremely small energy budget was submitted to old Eco-CI API',
            measurement=measurement
        )

    return Response(status_code=204)


@router.post('/v2/ci/measurement/add')
async def post_ci_measurement_add(
    request: Request,
    measurement: CI_Measurement,
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    measurement = html_escape_multi(measurement)

    params = [measurement.energy_uj, measurement.repo, measurement.branch,
            measurement.workflow, measurement.run_id, measurement.label, measurement.source, measurement.cpu,
            measurement.commit_hash, measurement.duration_us, measurement.cpu_util_avg, measurement.workflow_name,
            measurement.lat, measurement.lon, measurement.city, measurement.carbon_intensity_g, measurement.carbon_ug,
            measurement.filter_type, measurement.filter_project, measurement.filter_machine]

    tags_replacer = ' ARRAY[]::text[] '
    if measurement.filter_tags:
        tags_replacer = f" ARRAY[{','.join(['%s']*len(measurement.filter_tags))}] "
        params = params + measurement.filter_tags

    used_client_ip = measurement.ip # If an ip has been given with the data. We prioritize that
    if used_client_ip is None:
        used_client_ip = get_connecting_ip(request)

    params.append(used_client_ip)
    params.append(user._id)

    query = f"""
        INSERT INTO
            ci_measurements (energy_uj,
                            repo,
                            branch,
                            workflow_id,
                            run_id,
                            label,
                            source,
                            cpu,
                            commit_hash,
                            duration_us,
                            cpu_util_avg,
                            workflow_name,
                            lat,
                            lon,
                            city,
                            carbon_intensity_g,
                            carbon_ug,
                            filter_type,
                            filter_project,
                            filter_machine,
                            filter_tags,
                            ip_address,
                            user_id
                            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                {tags_replacer},
                %s, %s)

        """

    DB().query(query=query, params=params)

    if measurement.energy_uj <= 1 or (measurement.carbon_ug and measurement.carbon_ug <= 1):
        error_helpers.log_error(
            'Extremely small energy budget was submitted to Eco-CI API',
            measurement=measurement
        )

    return Response(status_code=204)

@router.get('/v1/ci/measurements')
async def get_ci_measurements(repo: str, branch: str, workflow: str, start_date: date, end_date: date):

    query = """
        SELECT energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util_avg,
               (SELECT workflow_name FROM ci_measurements AS latest_workflow
                WHERE latest_workflow.repo = ci_measurements.repo
                AND latest_workflow.branch = ci_measurements.branch
                AND latest_workflow.workflow_id = ci_measurements.workflow_id
                ORDER BY latest_workflow.created_at DESC
                LIMIT 1) AS workflow_name,
               lat, lon, city, carbon_intensity_g, carbon_ug
        FROM ci_measurements
        WHERE
            repo = %s AND branch = %s AND workflow_id = %s
            AND DATE(created_at) >= TO_DATE(%s, 'YYYY-MM-DD')
            AND DATE(created_at) <= TO_DATE(%s, 'YYYY-MM-DD')
        ORDER BY run_id ASC, created_at ASC
    """
    params = (repo, branch, workflow, str(start_date), str(end_date))
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204)  # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@router.get('/v1/ci/repositories')
async def get_ci_repositories(repo: str | None = None, sort_by: str = 'name'):

    params = []
    query = """
        SELECT repo, source, MAX(created_at) as last_run
        FROM ci_measurements
        WHERE 1=1
    """

    if repo: # filter is currently not used, but may be a feature in the future
        query = f"{query} AND ci_measurements.repo = %s  \n"
        params.append(repo)

    query = f"{query} GROUP BY repo, source"

    if sort_by == 'date':
        query = f"{query} ORDER BY last_run DESC"
    else:
        query = f"{query} ORDER BY repo ASC"

    data = DB().fetch_all(query, params=tuple(params))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data}) # no escaping needed, as it happend on ingest


@router.get('/v1/ci/runs')
async def get_ci_runs(repo: str, sort_by: str = 'name'):

    params = []
    query = """
        SELECT repo, branch, workflow_id, source, MAX(created_at) as last_run,
                (SELECT workflow_name FROM ci_measurements AS latest_workflow
                WHERE latest_workflow.repo = ci_measurements.repo
                AND latest_workflow.branch = ci_measurements.branch
                AND latest_workflow.workflow_id = ci_measurements.workflow_id
                ORDER BY latest_workflow.created_at DESC
                LIMIT 1) AS workflow_name
        FROM ci_measurements
        WHERE 1=1
    """

    query = f"{query} AND ci_measurements.repo = %s  \n"
    params.append(repo)
    query = f"{query} GROUP BY repo, branch, workflow_id, source"

    if sort_by == 'date':
        query = f"{query} ORDER BY last_run DESC"
    else:
        query = f"{query} ORDER BY repo ASC"

    data = DB().fetch_all(query, params=tuple(params))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data}) # no escaping needed, as it happend on ingest

@router.get('/v1/ci/badge/get')
async def get_ci_badge_get(repo: str, branch: str, workflow:str, mode: str = 'last', metric: str = 'energy', duration_days: int | None = None):
    if metric == 'energy':
        metric = 'energy_uj'
        metric_unit = 'uJ'
        label = 'energy used'
        default_color = 'orange'
    elif metric == 'carbon':
        metric = 'carbon_ug'
        metric_unit = 'ug'
        label = 'carbon emitted'
        default_color = 'black'
    else:
        raise RequestValidationError('Unsupported metric requested')


    if duration_days and (duration_days < 1 or duration_days > 365):
        raise RequestValidationError('Duration days must be between 1 and 365 days')

    params = [repo, branch, workflow]


    query = f"""
        SELECT SUM({metric})
        FROM ci_measurements
        WHERE repo = %s AND branch = %s AND workflow_id = %s
    """

    if mode == 'avg':
        if not duration_days:
            raise RequestValidationError('Duration days must be set for average')
        query = f"""
            WITH my_table as (
                SELECT SUM({metric}) my_sum
                FROM ci_measurements
                WHERE repo = %s AND branch = %s AND workflow_id = %s AND created_at > NOW() - make_interval(days => %s)
                GROUP BY run_id
            ) SELECT AVG(my_sum) FROM my_table;
        """
        params.append(duration_days)
        label = f"Per run moving average ({duration_days} days) {label}"
    elif mode == 'last':
        query = f"{query} GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT 1"
        label = f"Last run {label}"
    elif mode == 'totals' and duration_days:
        query = f"{query} AND created_at > NOW() - make_interval(days => %s)"
        params.append(duration_days)
        label = f"Last {duration_days} days total {label}"
    elif mode == 'totals':
        label = f"All runs total {label}"
    else:
        raise RuntimeError('Unknown mode')


    data = DB().fetch_one(query, params=params)

    if data is None or data == [] or data[0] is None: # special check for SUM element as this is aggregate query which always returns result
        return Response(status_code=204) # No-Content

    metric_value = data[0]

    [metric_value, metric_unit] = rescale_metric_value(metric_value, metric_unit)
    badge_value= f"{metric_value:.2f} {metric_unit}"

    badge = anybadge.Badge(
        label=label,
        value=xml_escape(badge_value),
        num_value_padding_chars=1,
        default_color=default_color)

    return Response(content=str(badge), media_type="image/svg+xml")
