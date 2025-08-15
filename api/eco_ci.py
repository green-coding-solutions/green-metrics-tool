from datetime import date

from fastapi import APIRouter
from fastapi import Request, Response, Depends
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError

from api.api_helpers import authenticate, html_escape_multi, get_connecting_ip, convert_value
from api.object_specifications import CI_Measurement

import anybadge

from xml.sax.saxutils import escape as xml_escape

from lib import error_helpers
from lib.user import User
from lib.db import DB

router = APIRouter()


@router.post('/v1/ci/measurement/add', deprecated=True)
def old_v1_measurement_add_endpoint():
    return ORJSONResponse({'success': False, 'err': 'This endpoint is deprecated. Please migrate to /v2/ci/measurement/add'}, status_code=410)

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

    if measurement.note is not None and measurement.note.strip() == '':
        measurement.note = None
    params.append(measurement.note)

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
                            user_id,
                            note
                            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                {tags_replacer},
                %s, %s, %s)

        """

    DB().query(query=query, params=params)

    if measurement.energy_uj <= 1 or (measurement.carbon_ug and measurement.carbon_ug <= 1):
        error_helpers.log_error(
            'Extremely small energy budget was submitted to Eco CI API',
            measurement=measurement
        )

    return Response(status_code=204)

@router.get('/v1/ci/measurements')
async def get_ci_measurements(repo: str, branch: str, workflow: str, start_date: date, end_date: date, user: User = Depends(authenticate)):

    query = '''
        SELECT energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util_avg,
               (SELECT workflow_name FROM ci_measurements AS latest_workflow
                WHERE latest_workflow.repo = ci_measurements.repo
                AND latest_workflow.branch = ci_measurements.branch
                AND latest_workflow.workflow_id = ci_measurements.workflow_id
                ORDER BY latest_workflow.created_at DESC
                LIMIT 1) AS workflow_name,
               lat, lon, city, carbon_intensity_g, carbon_ug, note
        FROM ci_measurements
        WHERE
            (TRUE = %s OR user_id = ANY(%s::int[]))
            AND repo = %s AND branch = %s AND workflow_id = %s
            AND DATE(created_at) >= TO_DATE(%s, 'YYYY-MM-DD')
            AND DATE(created_at) <= TO_DATE(%s, 'YYYY-MM-DD')
        ORDER BY run_id ASC, created_at ASC
    '''

    params = (user.is_super_user(), user.visible_users(), repo, branch, workflow, str(start_date), str(end_date))
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204)  # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@router.get('/v1/ci/stats')
async def get_ci_stats(repo: str, branch: str, workflow: str, start_date: date, end_date: date, user: User = Depends(authenticate)):


    query = '''
        WITH my_table as (
            SELECT
                SUM(energy_uj) as a,
                SUM(duration_us) as b,
                SUM(cpu_util_avg * duration_us) / NULLIF(SUM(duration_us), 0)  as c, -- weighted average
                SUM(carbon_intensity_g * duration_us) / NULLIF(SUM(duration_us), 0) as d,-- weighted average
                SUM(carbon_ug) as e
            FROM ci_measurements
            WHERE
                (TRUE = %s OR user_id = ANY(%s::int[]))
                AND repo = %s AND branch = %s AND workflow_id = %s
                AND DATE(created_at) >= TO_DATE(%s, 'YYYY-MM-DD') AND DATE(created_at) <= TO_DATE(%s, 'YYYY-MM-DD')
            GROUP BY run_id
        ) SELECT
            -- Cast is to avoid DECIMAL which ORJJSON cannot handle
            AVG(a)::float, SUM(a)::float, STDDEV(a)::float, (STDDEV(a) / NULLIF(AVG(a), 0))::float * 100,
            AVG(b)::float, SUM(b)::float, STDDEV(b)::float, (STDDEV(b) / NULLIF(AVG(b), 0))::float * 100,
            AVG(c)::float, NULL, STDDEV(c)::float, (STDDEV(c) / NULLIF(AVG(c), 0))::float * 100, -- SUM of cpu_util_avg makes no sense
            AVG(d)::float, NULL, STDDEV(d)::float, (STDDEV(d) / NULLIF(AVG(d), 0))::float * 100, -- SUM of carbon_intensity_g makes no sense
            AVG(e)::float, SUM(e)::float, STDDEV(e)::float, (STDDEV(e) / NULLIF(AVG(e), 0))::float * 100,
            COUNT(*)
        FROM my_table;
    '''

    params = (user.is_super_user(), user.visible_users(), repo, branch, workflow, str(start_date), str(end_date))
    totals_data = DB().fetch_one(query, params=params)

    if totals_data is None or totals_data[0] is None: # aggregate query always returns row
        return Response(status_code=204)  # No-Content

    query = '''
        SELECT
            -- Cast is to avoid DECIMAL which ORJJSON cannot handle
            -- Here we do not need a weighted average, even if the times differ, because we specifically want to look per step and duration is not relevant
            AVG(energy_uj)::float, SUM(energy_uj)::float, STDDEV(energy_uj)::float, (STDDEV(energy_uj) / NULLIF(AVG(energy_uj), 0))::float * 100,
            AVG(duration_us)::float, SUM(duration_us)::float, STDDEV(duration_us)::float, (STDDEV(duration_us) / NULLIF(AVG(duration_us), 0))::float * 100,
            AVG(cpu_util_avg)::float, NULL, STDDEV(cpu_util_avg)::float, (STDDEV(cpu_util_avg) / NULLIF(AVG(cpu_util_avg), 0))::float * 100, -- SUM of cpu_util_avg makes no sense
            AVG(carbon_intensity_g)::float, NULL, STDDEV(carbon_intensity_g)::float, (STDDEV(carbon_intensity_g) / NULLIF(AVG(carbon_intensity_g), 0))::float * 100, -- SUM of carbon_intensity_g makes no sense
            AVG(carbon_ug)::float, SUM(carbon_ug)::float, STDDEV(carbon_ug)::float, (STDDEV(carbon_ug) / NULLIF(AVG(carbon_ug), 0))::float * 100,
            COUNT(*), label
        FROM ci_measurements
        WHERE
            (TRUE = %s OR user_id = ANY(%s::int[]))
            AND repo = %s AND branch = %s AND workflow_id = %s
            AND DATE(created_at) >= TO_DATE(%s, 'YYYY-MM-DD') AND DATE(created_at) <= TO_DATE(%s, 'YYYY-MM-DD')
        GROUP BY label
    '''
    params = (user.is_super_user(), user.visible_users(), repo, branch, workflow, str(start_date), str(end_date))
    per_label_data = DB().fetch_all(query, params=params)

    if per_label_data is None or per_label_data[0] is None:
        return Response(status_code=204)  # No-Content

    return ORJSONResponse({'success': True, 'data': {'totals': totals_data, 'per_label': per_label_data}})


@router.get('/v1/ci/repositories')
async def get_ci_repositories(repo: str | None = None, sort_by: str = 'name', user: User = Depends(authenticate)):

    query = '''
        SELECT repo, source, MAX(created_at) as last_run
        FROM ci_measurements
        WHERE
            (TRUE = %s OR user_id = ANY(%s::int[]))
    '''
    params = [user.is_super_user(), user.visible_users()]

    if repo: # filter is currently not used, but may be a feature in the future
        query = f"{query} AND ci_measurements.repo = %s  \n"
        params.append(repo)

    query = f"{query} GROUP BY repo, source"

    if sort_by == 'date':
        query = f"{query} ORDER BY last_run DESC"
    else:
        query = f"{query} ORDER BY repo ASC"

    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data}) # no escaping needed, as it happend on ingest

@router.get('/v1/ci/runs')
async def get_ci_runs(repo: str, user: User = Depends(authenticate)):


    query = '''
        SELECT repo, branch, workflow_id, source, MAX(created_at) as last_run,
                (SELECT workflow_name FROM ci_measurements AS latest_workflow
                WHERE latest_workflow.repo = ci_measurements.repo
                AND latest_workflow.branch = ci_measurements.branch
                AND latest_workflow.workflow_id = ci_measurements.workflow_id
                ORDER BY latest_workflow.created_at DESC
                LIMIT 1) AS workflow_name
        FROM ci_measurements
        WHERE
            (TRUE = %s OR user_id = ANY(%s::int[]))
            AND ci_measurements.repo = %s
            GROUP BY repo, branch, workflow_id, source
            ORDER BY last_run DESC
    '''

    params = (user.is_super_user(), user.visible_users(), repo)

    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data}) # no escaping needed, as it happend on ingest

# Route to display a badge for a CI run
## A complex case to allow public visibility of the badge but restricting everything else would be to have
## User 1 restricted to only this route but a fully populated 'visible_users' array
@router.head('/v1/ci/badge/get')
@router.get('/v1/ci/badge/get')
async def get_ci_badge_get(repo: str, branch: str, workflow:str, mode: str = 'last', metric: str = 'energy', duration_days: int | None = None, unit: str = 'watt-hours', user: User = Depends(authenticate)):
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
    # Do not easily add values like cpu_util or carbon_intensity_g here. They need a weighted average in the SQL query later!
    else:
        raise RequestValidationError('Unsupported metric requested')

    if unit not in ('watt-hours', 'joules'):
        raise RequestValidationError('Requested unit is not in allow list: watt-hours, joules')

    if duration_days and (duration_days < 1 or duration_days > 365):
        raise RequestValidationError('Duration days must be between 1 and 365 days')

    query = f"""
        SELECT SUM({metric})
        FROM ci_measurements
        WHERE
            (TRUE = %s OR user_id = ANY(%s::int[]))
            AND repo = %s AND branch = %s AND workflow_id = %s
    """
    params = [user.is_super_user(), user.visible_users(), repo, branch, workflow]

    if mode == 'avg':
        if not duration_days:
            raise RequestValidationError('Duration days must be set for average')
        query = f"""
            WITH my_table as (
                SELECT SUM({metric}) my_sum
                FROM ci_measurements
                WHERE
                    (TRUE = %s OR user_id = ANY(%s::int[]))
                    AND repo = %s AND branch = %s AND workflow_id = %s AND DATE(created_at) > NOW() - make_interval(days => %s)
                GROUP BY run_id
            ) SELECT AVG(my_sum) FROM my_table;
        """
        params.append(duration_days)
        label = f"Per run moving average ({duration_days} days) {label}"
    elif mode == 'last':
        query = f"{query} GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT 1"
        label = f"Last run {label}"
    elif mode == 'totals' and duration_days:
        query = f"{query} AND DATE(created_at) > NOW() - make_interval(days => %s)"
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
    display_in_joules = (unit == 'joules') # pylint: disable=superfluous-parens
    [transformed_value, transformed_unit] = convert_value(metric_value, metric_unit, display_in_joules)
    badge_value= f"{transformed_value:.2f} {transformed_unit}"

    badge = anybadge.Badge(
        label=label,
        value=xml_escape(badge_value),
        num_value_padding_chars=1,
        default_color=default_color)

    return Response(content=str(badge), media_type="image/svg+xml")


@router.get('/v1/ci/insights')
async def get_insights(user: User = Depends(authenticate)):

    query = '''
            SELECT COUNT(id), DATE(MIN(created_at))
            FROM ci_measurements
            WHERE (TRUE = %s OR user_id = ANY(%s::int[]))
    '''

    params = (user.is_super_user(), user.visible_users())
    data = DB().fetch_one(query, params=params)

    if data is None:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})
