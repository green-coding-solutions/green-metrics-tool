import orjson

from fastapi import APIRouter
from fastapi import Response, Depends, HTTPException

from api.api_helpers import authenticate, CustomORJSONResponse, get_artifact, store_artifact
from api.object_specifications import ArtifactType

from lib.user import User
from lib.db import DB

router = APIRouter()


@router.get('/v1/software/categories')
async def get_software_categories(
    # Endpoint without user restriction on DB. But authenticate() must be present to check if route is allowed in general
    user: User = Depends(authenticate), # pylint: disable=unused-argument
    ):

    query = '''
        SELECT
            c.name,
            COALESCE(sw_counts.cnt, 0) AS count
        FROM categories c
        LEFT JOIN (
            SELECT
                unnest(s.category_ids)  AS cat_id,
                COUNT(DISTINCT s.id)    AS cnt
            FROM softwares s
            WHERE s.category_ids IS NOT NULL
            GROUP BY cat_id
        ) sw_counts ON sw_counts.cat_id = c.id
        ORDER BY count DESC, c.name ASC
    '''

    data = DB().fetch_all(query) or []
    if not data:
        return Response(status_code=204)

    result = [{'name': row[0], 'count': int(row[1])} for row in data]
    return CustomORJSONResponse({'success': True, 'data': result})


@router.get('/v1/software')
async def get_softwares(
    category: str | None = None,
    page: int = 1,
    # Endpoint without user restriction on DB. But authenticate() must be present to check if route is allowed in general
    user: User = Depends(authenticate), # pylint: disable=unused-argument
    ):

    page = max(page, 1) # disallow negative pages

    # category may be comma-separated ("Web,JavaScript") → AND-filter: software must match ALL
    cat_list = [c.strip() for c in category.split(',') if c.strip()] if category else None
    cat_count = len(cat_list) if cat_list else None

    query = '''
        SELECT
            s.id,
            s.name,
            s.image_src,
            s.created_at,
            s.updated_at,
            (
                SELECT STRING_AGG(c.name, ', ')
                FROM unnest(s.category_ids) AS el
                LEFT JOIN categories AS c ON c.id = el
            ) AS categories
        FROM softwares s
        WHERE
            %s::int IS NULL
            OR (
                SELECT COUNT(DISTINCT c.name)
                FROM categories c
                WHERE c.name = ANY(%s::text[])
                  AND c.id = ANY(s.category_ids)
            ) = %s::int
        ORDER BY s.name ASC
    '''
    params = (cat_count, cat_list, cat_count)

    rows = DB().fetch_all(query, params=params, fetch_mode='dict') or []
    if not rows:
        return Response(status_code=204)

    offset = (page - 1) * 50
    return CustomORJSONResponse({
        'success': True,
        'data': rows[offset:offset + 50],
        'pagination': {'page': page, 'page_size': 50, 'total_count': len(rows)},
    })


@router.get('/v1/software/{software_id}/tasks')
async def get_software_tasks(
    software_id: int,
    user: User = Depends(authenticate),
    ):

    cache_key = f"{user._id}_software_tasks_{software_id}"
    if artifact := get_artifact(ArtifactType.SOFTWARE, cache_key):
        return CustomORJSONResponse({'success': True, 'data': orjson.loads(artifact)}) # pylint: disable=no-member

    # LATERAL JOIN picks the latest matching run per task, then aggregates its phase metrics.
    # regexp_replace strips the numeric ordering prefix (e.g. "001_") from phase_stats.phase
    # so it matches the plain phase name stored in software_tasks.phase.
    query = '''
        WITH task_runs AS (
            SELECT
                st.id          AS task_id,
                st.name        AS task_name,
                st.uri,
                st.branch,
                st.filename,
                st.phase,
                st.machine_id,
                m.description  AS machine_name,
                st.created_at,
                r.run_id,
                r.run_created_at
            FROM software_tasks st
            JOIN machines m ON m.id = st.machine_id
            LEFT JOIN LATERAL (
                SELECT r.id AS run_id, r.created_at AS run_created_at
                FROM runs r
                WHERE r.uri = st.uri
                    AND r.branch = st.branch
                    AND r.filename = st.filename
                    AND r.machine_id = st.machine_id
                    AND r.failed = FALSE
                    AND r.archived = FALSE
                    AND r.end_measurement IS NOT NULL
                    AND (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
                ORDER BY r.created_at DESC
                LIMIT 1
            ) r ON TRUE
            WHERE st.software_id = %s
        )
        SELECT
            tr.task_id, tr.task_name, tr.uri, tr.branch, tr.filename,
            tr.phase, tr.machine_id, tr.machine_name, tr.created_at,
            tr.run_id, tr.run_created_at,
            p.metric, SUM(p.value)::bigint AS value, p.unit, p.type
        FROM task_runs tr
        LEFT JOIN phase_stats p ON p.run_id = tr.run_id
            AND regexp_replace(p.phase, '^[0-9]+_', '') = tr.phase
            AND p.hidden = false
            AND (
                p.metric LIKE '%%power%%'
                OR p.metric LIKE '%%energy%%'
                OR p.metric LIKE '%%carbon%%'
                OR p.metric LIKE 'network_%%'
                OR p.metric = 'phase_time_syscall_system'
            )
        GROUP BY
            tr.task_id, tr.task_name, tr.uri, tr.branch, tr.filename,
            tr.phase, tr.machine_id, tr.machine_name, tr.created_at,
            tr.run_id, tr.run_created_at, p.metric, p.unit, p.type
        ORDER BY tr.task_id, p.metric
    '''
    params = (user.is_super_user(), user.visible_users(), software_id)

    rows = DB().fetch_all(query, params=params) or []
    if not rows:
        return Response(status_code=204)

    tasks = {}
    task_order = []
    for row in rows:
        task_id = row[0]
        if task_id not in tasks:
            tasks[task_id] = {
                'id': task_id,
                'name': row[1],
                'uri': row[2],
                'branch': row[3],
                'filename': row[4],
                'phase': row[5],
                'machine_id': row[6],
                'machine_name': row[7],
                'created_at': row[8].isoformat() if row[8] else None,
                'run_id': str(row[9]) if row[9] else None,
                'run_created_at': row[10].isoformat() if row[10] else None,
                'phase_metrics': {},
            }
            task_order.append(task_id)
        metric, value, unit, type_ = row[11], row[12], row[13], row[14]
        if metric:
            tasks[task_id]['phase_metrics'][metric] = {'value': value, 'unit': unit, 'type': type_}

    result = [tasks[tid] for tid in task_order]
    store_artifact(ArtifactType.SOFTWARE, cache_key, orjson.dumps(result)) # pylint: disable=no-member
    return CustomORJSONResponse({'success': True, 'data': result})


@router.get('/v1/software/similar')
async def get_similar_software(
    name: str,
    exclude_software_id: int | None = None,
    categories: str | None = None,
    limit: int = 3,
    user: User = Depends(authenticate),
    ):

    if not name or not name.strip():
        raise HTTPException(status_code=422, detail='name is required')
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=422, detail='limit must be between 1 and 50')

    cat_set = {c.strip() for c in categories.split(',') if c.strip()} if categories else set()

    def _cat_score(item):
        item_cats = {c.strip() for c in (item.get('software_categories') or '').split(',') if c.strip()}
        return len(item_cats & cat_set)

    def _prepare(result):
        result = [item for item in result if item['name'] == name]
        if exclude_software_id is not None:
            result = [item for item in result if item['software_id'] != exclude_software_id]
        if cat_set:
            result.sort(key=_cat_score, reverse=True)
        return result[:limit]

    # Cache the full unfiltered set for this task name; sorting/limiting is done in Python per request
    cache_key = f"{user._id}_software_similar_{name}"
    if artifact := get_artifact(ArtifactType.SOFTWARE, cache_key):
        result = _prepare(orjson.loads(artifact)) # pylint: disable=no-member
        if not result:
            return Response(status_code=204)
        return CustomORJSONResponse({'success': True, 'data': result})

    query = '''
        WITH task_runs AS (
            SELECT
                sw.id          AS software_id,
                sw.name        AS software_name,
                sw.image_src   AS software_image_src,
                (
                    SELECT STRING_AGG(c.name, ', ')
                    FROM unnest(sw.category_ids) AS el
                    LEFT JOIN categories c ON c.id = el
                ) AS software_categories,
                st.id          AS task_id,
                st.name        AS task_name,
                st.uri,
                st.branch,
                st.filename,
                st.phase,
                st.machine_id,
                m.description  AS machine_name,
                st.created_at,
                r.run_id,
                r.run_created_at
            FROM software_tasks st
            JOIN softwares sw ON sw.id = st.software_id
            JOIN machines m ON m.id = st.machine_id
            LEFT JOIN LATERAL (
                SELECT r.id AS run_id, r.created_at AS run_created_at
                FROM runs r
                WHERE r.uri = st.uri
                    AND r.branch = st.branch
                    AND r.filename = st.filename
                    AND r.machine_id = st.machine_id
                    AND r.failed = FALSE
                    AND r.archived = FALSE
                    AND r.end_measurement IS NOT NULL
                    AND (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
                ORDER BY r.created_at DESC
                LIMIT 1
            ) r ON TRUE
            WHERE st.name = %s
        )
        SELECT
            tr.software_id, tr.software_name, tr.software_image_src, tr.software_categories,
            tr.task_id, tr.task_name, tr.uri, tr.branch, tr.filename,
            tr.phase, tr.machine_id, tr.machine_name, tr.created_at,
            tr.run_id, tr.run_created_at,
            p.metric, SUM(p.value)::bigint AS value, p.unit, p.type
        FROM task_runs tr
        LEFT JOIN phase_stats p ON p.run_id = tr.run_id
            AND regexp_replace(p.phase, '^[0-9]+_', '') = tr.phase
            AND p.hidden = false
            AND (
                p.metric LIKE '%%power%%'
                OR p.metric LIKE '%%energy%%'
                OR p.metric LIKE '%%carbon%%'
                OR p.metric LIKE 'network_%%'
                OR p.metric = 'phase_time_syscall_system'
            )
        GROUP BY
            tr.software_id, tr.software_name, tr.software_image_src, tr.software_categories,
            tr.task_id, tr.task_name, tr.uri, tr.branch, tr.filename,
            tr.phase, tr.machine_id, tr.machine_name, tr.created_at,
            tr.run_id, tr.run_created_at, p.metric, p.unit, p.type
        ORDER BY tr.software_name, tr.task_id, p.metric
    '''
    params = (user.is_super_user(), user.visible_users(), name)

    rows = DB().fetch_all(query, params=params) or []
    if not rows:
        return Response(status_code=204)

    tasks_map = {}
    task_order = []
    for row in rows:
        task_id = row[4]
        if task_id not in tasks_map:
            tasks_map[task_id] = {
                'software_id':         row[0],
                'software_name':       row[1],
                'software_image_src':  row[2],
                'software_categories': row[3],
                'id':                  task_id,
                'name':                row[5],
                'uri':                 row[6],
                'branch':              row[7],
                'filename':            row[8],
                'phase':               row[9],
                'machine_id':          row[10],
                'machine_name':        row[11],
                'created_at':          row[12].isoformat() if row[12] else None,
                'run_id':              str(row[13]) if row[13] else None,
                'run_created_at':      row[14].isoformat() if row[14] else None,
                'phase_metrics':       {},
            }
            task_order.append(task_id)
        metric, value, unit, type_ = row[15], row[16], row[17], row[18]
        if metric:
            tasks_map[task_id]['phase_metrics'][metric] = {'value': value, 'unit': unit, 'type': type_}

    result = [tasks_map[tid] for tid in task_order]
    store_artifact(ArtifactType.SOFTWARE, cache_key, orjson.dumps(result)) # pylint: disable=no-member

    result = _prepare(result)
    if not result:
        return Response(status_code=204)

    return CustomORJSONResponse({'success': True, 'data': result})
