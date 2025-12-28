from typing import List
import base64
import zlib
import orjson
from datetime import date, timedelta, datetime

from pydantic import ValidationError

from fastapi import APIRouter, Response, Depends, HTTPException
from fastapi.responses import ORJSONResponse

from api.api_helpers import authenticate
from lib.user import User
from lib.db import DB
from api.object_specifications import HogMeasurement, SimplifiedMeasurement
from api.api_helpers import replace_nan_with_zero

router = APIRouter()

@router.post('/v1/hog/add', deprecated=True)
def old_v1_hog_add_endpoint():
    return ORJSONResponse({'success': False, 'err': 'This endpoint is deprecated. Please migrate to /v2/hog/add'}, status_code=410)

@router.post('/v2/hog/add')
async def add_hog(
    measurements: List[HogMeasurement],
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    for measurement in measurements:
        decoded_data = base64.b64decode(measurement.data)
        decompressed_data = zlib.decompress(decoded_data)
        measurement_data = orjson.loads(decompressed_data.decode()) # pylint: disable=no-member

        # For some reason we sometimes get NaN in the data.
        measurement_data = replace_nan_with_zero(measurement_data)

        # Validate measurement data
        try:
            validated_measurement = SimplifiedMeasurement(**measurement_data)
        except ValidationError as exc:
            print('Caught Exception in Measurement()', exc.__class__.__name__, exc)
            print('Hog parsing error. Missing expected, but non critical key', str(exc))
            # Output is extremely verbose. Please only turn on if debugging manually
            # print(f"Errors are: {exc.errors()}")
            raise HTTPException(status_code=422, detail=f"Invalid measurement data: {str(exc)}") from exc

        query_measurement = """
        INSERT INTO hog_simplified_measurements (
            user_id,
            machine_uuid,
            timestamp,
            timezone,
            grid_intensity_cog,
            combined_energy_uj,
            cpu_energy_uj,
            gpu_energy_uj,
            ane_energy_uj,
            energy_impact,
            operational_carbon_ug,
            hw_model,
            elapsed_ns,
            embodied_carbon_ug,
            thermal_pressure
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """

        validated_operational_carbon_g = validated_measurement.operational_carbon_g or 0.0
        validated_embodied_carbon_g = validated_measurement.embodied_carbon_g or 0.0


        params_measurement = (
            user._id,
            validated_measurement.machine_uuid,
            validated_measurement.timestamp,
            validated_measurement.timezone,
            validated_measurement.grid_intensity_cog,
            validated_measurement.combined_energy_mj * 1000, # Convert to microjoules
            validated_measurement.cpu_energy_mj * 1000,
            validated_measurement.gpu_energy_mj * 1000,
            validated_measurement.ane_energy_mj * 1000,
            validated_measurement.energy_impact,
            validated_operational_carbon_g * 1_000_000, # Convert to micrograms
            validated_measurement.hw_model,
            validated_measurement.elapsed_ns,
            validated_embodied_carbon_g * 1_000_000, # Convert to micrograms
            validated_measurement.thermal_pressure,
        )
        measurement_db_id = DB().fetch_one(query=query_measurement, params=params_measurement)[0]

        query_top_process = """
            INSERT INTO hog_top_processes (
                measurement_id,
                name,
                energy_impact,
                cputime_ms
            )
            VALUES (%s, %s, %s, %s)
        """

        queries = [query_top_process] * len(validated_measurement.top_processes)

        params = []
        for process in validated_measurement.top_processes:
            name = process.get('name')
            energy_impact = process.get('energy_impact')
            cputime_ms = process.get('cputime_ms')

            if measurement_db_id is None or name is None or energy_impact is None or cputime_ms is None:
                raise ValueError(f"None value found: measurement_db_id={measurement_db_id}, "
                                f"name={name}, energy_impact={energy_impact}, cputime_ms={cputime_ms}")

            params.append((measurement_db_id, name, energy_impact, cputime_ms))

        if params:
            DB().query_multi(query=queries, params=params)

    return Response(status_code=202)

@router.get('/v2/hog/top_processes')
async def hog_get_top_processes():
    query = """
        SELECT
            name,
            (SUM(energy_impact)::bigint) AS total_energy_impact
        FROM
            hog_top_processes
        GROUP BY
            name
        ORDER BY
            total_energy_impact DESC
        LIMIT 10;
    """
    data = DB().fetch_all(query)

    if data is None:
        data = []

    query = """
        SELECT COUNT(DISTINCT machine_uuid) FROM hog_simplified_measurements;
    """

    machine_count = DB().fetch_one(query)[0]

    return ORJSONResponse({'success': True, 'process_data': data, 'machine_count': machine_count})


@router.get('/v2/hog/details')
async def user_detail(
    user: User = Depends(authenticate),
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date is None:
        start_epoch = int((datetime.combine(date.today(), datetime.min.time()) - timedelta(days=30)).timestamp() * 1000)
    else:
        start_epoch = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)

    if end_date is None:
        end_epoch = int(datetime.combine(date.today(), datetime.max.time()).timestamp() * 1000)
    else:
        end_epoch = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

    sums_query = """
        SELECT
            COALESCE(SUM(combined_energy_uj), 0)::bigint       AS total_combined_energy,
            COALESCE(SUM(cpu_energy_uj), 0)::bigint            AS total_cpu_energy,
            COALESCE(SUM(gpu_energy_uj), 0)::bigint            AS total_gpu_energy,
            COALESCE(SUM(ane_energy_uj), 0)::bigint            AS total_ane_energy,
            COALESCE(SUM(energy_impact), 0)::bigint            AS total_energy_impact,
            COALESCE(SUM(operational_carbon_ug), 0)::float     AS total_operational_carbon,
            COALESCE(SUM(embodied_carbon_ug), 0)::float        AS total_embodied_carbon
        FROM hog_simplified_measurements
        WHERE timestamp >= %s AND timestamp <= %s AND user_id = %s
    """
    sums_data = DB().fetch_one(sums_query, (start_epoch, end_epoch, user._id))

    if sums_data is None:
        sums_data = [0] * 7

    sums_dict = {
        'total_combined_energy_uj':     sums_data[0],
        'total_cpu_energy_uj':          sums_data[1],
        'total_gpu_energy_uj':          sums_data[2],
        'total_ane_energy_uj':          sums_data[3],
        'total_energy_impact':          sums_data[4],
        'total_operational_carbon_ug':  sums_data[5],
        'total_embodied_carbon_ug':   sums_data[6],
    }

    # ----------------------------------------------------------
    # This will be very slow if the data becomes large. We will need a script that compresses old data.
    # ----------------------------------------------------------
    processes_query = """
        SELECT
            p.name,
            SUM(p.energy_impact)::bigint AS total_energy_impact
        FROM hog_top_processes p
        INNER JOIN hog_simplified_measurements m
            ON p.measurement_id = m.id
        WHERE m.timestamp >= %s AND m.timestamp <= %s  AND user_id = %s
        GROUP BY p.name
        ORDER BY total_energy_impact DESC
        LIMIT 100
    """
    process_data = DB().fetch_all(processes_query, (start_epoch, end_epoch, user._id))
    if process_data is None:
        process_data = []

    return ORJSONResponse({
        'success': True,
        'process_data': process_data,
        **sums_dict,
    })


# @router.get('/v2/hog/details')
# async def user_detail(
#     user: User = Depends(authenticate),
#     start_date: date | None = None, end_date: date | None = None,
#     ):

#     print(start_date, end_date)
#     if start_date is None:
#         start_epoch = int((datetime.combine(date.today(), datetime.min.time()) - timedelta(days=30)).timestamp() * 1000)
#     else:
#         start_epoch = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)

#     if end_date is None:
#         end_epoch = int(datetime.combine(date.today(), datetime.max.time()).timestamp() * 1000)
#     else:
#         end_epoch = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)


#     query = """
#         SELECT
#             name,
#             (SUM(energy_impact)::bigint) AS total_energy_impact
#         FROM
#             hog_top_processes
#         WHERE
#             timestamp >= %s AND timestamp <= %s
#         GROUP BY
#             name
#         ORDER BY
#             total_energy_impact DESC
#         LIMIT 100;
#     """
#     data = DB().fetch_all(query, (start_epoch, end_epoch))

#     if data is None:
#         data = []

#     query = """
#         SELECT COUNT(DISTINCT machine_uuid) FROM hog_simplified_measurements;
#     """

#     machine_count = DB().fetch_one(query)[0]

#     return ORJSONResponse({'success': True, 'process_data': data, 'machine_count': machine_count})


@router.get('/v1/hog/insights')
async def get_insights(user: User = Depends(authenticate)):

    query = '''
            SELECT COUNT(id), DATE(MIN(created_at))
            FROM hog_simplified_measurements
            WHERE (TRUE = %s OR user_id = ANY(%s::int[]))
    '''

    params = (user.is_super_user(), user.visible_users())
    data = DB().fetch_one(query, params=params)

    if data is None:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})
