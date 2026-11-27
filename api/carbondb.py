import time
from datetime import date

from fastapi import APIRouter
from fastapi import Request, Response, Depends, HTTPException

from api.api_helpers import authenticate, get_connecting_ip, CustomORJSONResponse, FUTURE_TIMESTAMP_TOLERANCE_S
from api.object_specifications import EnergyData

from lib.global_config import GlobalConfig
from lib.user import User
from lib.db import DB

router = APIRouter()

@router.post('/v1/carbondb/add')
async def add_carbondb_deprecated():
    return Response("This endpoint is not supported anymore. Please migrate to /v3/carbondb/add !", status_code=410)

@router.post('/v2/carbondb/add')
async def add_carbondb_v2_deprecated():
    return Response("This endpoint is not supported anymore. Carbon is now split into operational and embodied carbon, and embodied carbon is mandatory. Please migrate to /v3/carbondb/add !", status_code=410)

@router.post('/v3/carbondb/add')
async def add_carbondb(
    request: Request,
    energydata: EnergyData,
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    merge_window_max = GlobalConfig().config['cluster']['carbondb_merge_window_days']
    current_time_us = int(time.time_ns()  / 1e3)
    if energydata.time < current_time_us - merge_window_max * 24 * 60 * 60 * 1e6 : # microseconds
        raise HTTPException(status_code=422, detail=f"CarbonDB is configured to not accept values older than {merge_window_max} days. Your timestamp was: {energydata.time}")
    if energydata.time > current_time_us + FUTURE_TIMESTAMP_TOLERANCE_S * 1e6: # microseconds
        raise HTTPException(status_code=422, detail=f"CarbonDB does not accept timestamps in the future. Your timestamp was: {energydata.time}. API timestamp was: {current_time_us}")

    energy_kwh = energydata.energy_uj / 1e6 / (3_600*1_000)

    # Operational carbon can be derived from energy and carbon intensity. If neither carbon nor intensity is given
    # it stays NULL and cron/backfill_carbon_intensity.py fills it. Embodied carbon is mandatory and never backfilled
    if energydata.operational_carbon_ug is not None:
        operational_carbon_kg = energydata.operational_carbon_ug / 1e9
    elif energydata.carbon_intensity_g is not None:
        operational_carbon_kg = (energy_kwh * energydata.carbon_intensity_g) / 1_000
    else:
        operational_carbon_kg = None

    used_client_ip = energydata.ip if energydata.ip is not None else get_connecting_ip(request) # An ip given with the data is prioritized

    DB().query(
        query='''
            INSERT INTO carbondb_data_raw
                ("type", "project", "machine", "source", "tags", "time", "energy_kwh", "operational_carbon_kg", "embodied_carbon_kg", "carbon_intensity_g", "ip_address", "user_id", "created_at")
            VALUES
                (%s, %s, %s, 'CUSTOM', %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ''',
        params=(
            energydata.type, energydata.project, energydata.machine, energydata.tags, energydata.time,
            energy_kwh, operational_carbon_kg, energydata.embodied_carbon_ug / 1e9, energydata.carbon_intensity_g,
            used_client_ip, user._id))

    return Response(status_code=202)


@router.get('/v1/carbondb/')
async def get_carbondb_deprecated():
    return Response("This endpoint is not supported anymore. Please migrate to /v2/carbondb/ !", status_code=410)

@router.get('/v2/carbondb')
async def carbondb_get(
    user: User = Depends(authenticate),
    start_date: date | None = None, end_date: date | None = None,
    tags_include: str | None = None, tags_exclude: str | None = None,
    types_include: str | None = None, types_exclude: str | None = None,
    projects_include: str | None = None, projects_exclude: str | None = None,
    machines_include: str | None = None, machines_exclude: str | None = None,
    sources_include: str | None = None, sources_exclude: str | None = None,
    users_include: str | None = None, users_exclude: str | None = None,
    ):

    params = []

    start_date_condition = ''
    if start_date is not None:
        start_date_condition =  "AND DATE(cedd.date) >= %s"
        params.append(start_date)

    end_date_condition = ''
    if end_date is not None:
        end_date_condition =  "AND DATE(cedd.date) <= %s"
        params.append(end_date)

    tags_include_condition = ''
    if tags_include:
        tags_include_list = tags_include.split(',')
        tags_include_condition = ' AND cedd.tags && %s::int[]'
        params.append(tags_include_list)

    tags_exclude_condition = ''
    if tags_exclude:
        tags_exclude_list = tags_exclude.split(',')
        tags_exclude_condition = ' AND NOT (cedd.tags && %s::int[])'
        params.append(tags_exclude_list)

    machines_include_condition = ''
    if machines_include:
        machines_include_list = machines_include.split(',')
        machines_include_condition = ' AND cedd.machine = ANY(%s::int[])'
        params.append(machines_include_list)

    machines_exclude_condition = ''
    if machines_exclude:
        machines_exclude_list = machines_exclude.split(',')
        machines_exclude_condition = ' AND cedd.machine != ANY(%s::int[])'
        params.append(machines_exclude_list)

    types_include_condition = ''
    if types_include:
        types_include_list = types_include.split(',')
        types_include_condition = ' AND cedd.type = ANY(%s::int[])'
        params.append(types_include_list)

    types_exclude_condition = ''
    if types_exclude:
        types_exclude_list = types_exclude.split(',')
        types_exclude_condition = ' AND cedd.type != ANY(%s::int[])'
        params.append(types_exclude_list)

    projects_include_condition = ''
    if projects_include:
        projects_include_list = projects_include.split(',')
        projects_include_condition = ' AND cedd.project = ANY(%s::int[])'
        params.append(projects_include_list)

    projects_exclude_condition = ''
    if projects_exclude:
        projects_exclude_list = projects_exclude.split(',')
        projects_exclude_condition = ' AND cedd.project != ANY(%s::int[])'
        params.append(projects_exclude_list)

    sources_include_condition = ''
    if sources_include:
        sources_include_list = sources_include.split(',')
        sources_include_condition = ' AND cedd.source = ANY(%s::int[])'
        params.append(sources_include_list)

    sources_exclude_condition = ''
    if sources_exclude:
        sources_exclude_list = sources_exclude.split(',')
        sources_exclude_condition = ' AND cedd.source != ANY(%s::int[])'
        params.append(sources_exclude_list)

    users_include_condition = ''
    if users_include:
        users_include_list = { int(el) for el in users_include.split(',') } # set comprehension ... hate this overloaded syntax ...
        if not user.is_super_user() and not users_include_list.issubset(set(user.visible_users())):
            raise HTTPException(status_code=422, detail='You cannot filter for these other users than yourself. Missing visibility permissions.')

        users_include_condition = ' AND cedd.user_id = ANY(%s::int[])'
        params.append(list(users_include_list))
    else:
        users_include_condition = ' AND cedd.user_id = %s'
        params.append(user._id)


    users_exclude_condition = ''
    if users_exclude:
        users_exclude_list = { int(el) for el in users_exclude.split(',') } # set comprehension ... hate this overloaded syntax ...
        if not user.is_super_user() and not users_exclude_list.issubset(set(user.visible_users())):
            raise HTTPException(status_code=422, detail='You cannot filter for these other users than yourself. Missing visibility permissions.')

        users_exclude_condition = ' AND cedd.user_id != ANY(%s::int[])'
        params.append(list(users_exclude_list))


    query = f"""
        SELECT
            type, project, machine, source, tags, date, energy_kwh_sum, operational_carbon_kg_sum, embodied_carbon_kg_sum, carbon_intensity_g_avg, record_count, user_id
        FROM
            carbondb_data as cedd
        WHERE
            1=1
            {start_date_condition}
            {end_date_condition}
            {tags_include_condition}
            {tags_exclude_condition}
            {machines_include_condition}
            {machines_exclude_condition}
            {types_include_condition}
            {types_exclude_condition}
            {projects_include_condition}
            {projects_exclude_condition}
            {sources_include_condition}
            {sources_exclude_condition}
            {users_include_condition}
            {users_exclude_condition}

        ORDER BY
            cedd.date ASC
        ;
    """
    data = DB().fetch_all(query, params)

    return CustomORJSONResponse({'success': True, 'data': data})


@router.get('/v2/carbondb/filters')
async def carbondb_get_filters(
    user: User = Depends(authenticate)
    ):

    results = {}
    elements = ['type', 'tag', 'machine', 'project', 'source']

    for el in elements:
        query = f"SELECT jsonb_object_agg(id, {el}) FROM carbondb_{el}s WHERE (TRUE = %s OR user_ids && %s::int[])"
        results[f"{el}s"] = DB().fetch_one(query, (user.is_super_user(), user.visible_users()))[0]

    query = 'SELECT jsonb_object_agg(id, name) FROM users WHERE (TRUE = %s OR id = ANY(%s::int[]))'
    visible_users = DB().fetch_one(query, (user.is_super_user(), user.visible_users()))[0]


    return CustomORJSONResponse({'success': True, 'data': {'types': results['types'], 'tags': results['tags'], 'machines': results['machines'], 'projects': results['projects'], 'sources': results['sources'], 'users': visible_users}})

@router.get('/v1/carbondb/insights')
async def get_insights(user: User = Depends(authenticate)):

    query = '''
            SELECT COUNT(id), DATE(MIN(date))
            FROM carbondb_data
            WHERE (TRUE = %s OR user_id = ANY(%s::int[]))
    '''

    params = (user.is_super_user(), user.visible_users())
    data = DB().fetch_one(query, params=params)

    if data is None:
        return Response(status_code=204) # No-Content

    return CustomORJSONResponse({'success': True, 'data': data})
