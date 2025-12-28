# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic?
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from starlette.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import Headers as StarletteHeaders

from api.api_helpers import authenticate

from lib.global_config import GlobalConfig
from lib import error_helpers
from lib.user import User
from lib.db import DB
from lib.secure_variable import SecureVariable

from api.object_specifications import UserSetting

from enum import Enum
ArtifactType = Enum('ArtifactType', ['DIFF', 'COMPARE', 'STATS', 'BADGE'])

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_helpers.log_error(
        'Error in API call - validation_exception_handler',
        url=request.url,
        query_params=request.query_params,
        client=request.client,
        headers=obfuscate_authentication_token(request.headers),
        body=exc.body,
        details=exc.errors(),
        exception=exc,
        previous_exception=exc.__context__
    )
    return ORJSONResponse(
        status_code=422, # HTTP_422_UNPROCESSABLE_ENTITY
        content=jsonable_encoder({'success': False, 'err': exc.errors(), 'body': exc.body}),
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    body = await request.body()
    error_helpers.log_error(
        'Error in API call - http_exception_handler',
        url=request.url,
        query_params=request.query_params,
        client=request.client,
        headers=obfuscate_authentication_token(request.headers),
        body=body,
        details=exc.detail,
        exception=exc,
        previous_exception=exc.__context__
    )
    return ORJSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({'success': False, 'err': exc.detail}),
    )

async def catch_exceptions_middleware(request: Request, call_next):
    #pylint: disable=broad-except
    body = None

    try:
        body = await request.body()
        return await call_next(request)
    except Exception as exc:
        error_helpers.log_error(
            'Error in API call - catch_exceptions_middleware',
            url=request.url,
            query_params=request.query_params,
            client=request.client,
            headers=obfuscate_authentication_token(request.headers),
            body=body,
            exception=exc,
            previous_exception=exc.__context__
        )
        return ORJSONResponse(
            content={
                'success': False,
                'err': 'Technical error with getting data from the API - Please contact us: info@green-coding.io',
            },
            status_code=500,
        )

# Binding the Exception middleware must confusingly come BEFORE the CORS middleware.
# Otherwise CORS will not be sent in response
app.middleware('http')(catch_exceptions_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=GlobalConfig().config['cluster']['cors_allowed_origins'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

def obfuscate_authentication_token(headers: StarletteHeaders):
    headers_mut = headers.mutablecopy()
    if 'X-Authentication' in headers_mut:
        try:
            authentication_token = headers_mut['X-Authentication']
            if not authentication_token or authentication_token.strip() == '': # Note that if no token is supplied this will authenticate as the DEFAULT user, which in FOSS systems has full capabilities
                authentication_token = 'DEFAULT'

            user = User.authenticate(SecureVariable(authentication_token))
            headers_mut['X-Authentication'] = f"****TOKEN REMOVED FOR USER {user._name} ({user._id})****"
        except Exception as exc: # pylint: disable=broad-exception-caught
            error_helpers.log_error(
                'Could not resolve user name for authentication token',
                headers=headers,
                token=headers['X-Authentication'],
                exception=exc,
                previous_exception=exc.__context__
            )

            headers_mut['X-Authentication'] = '****TOKEN REMOVED FOR USER __UNKNOWN__ ****'

    return headers_mut

#############################################################
##### Unauthorized routes. These can be used by any user ####
#############################################################

# Self documentation from FastAPI
@app.get('/')
async def home():
    return RedirectResponse(url='/docs')

@app.get('/robots.txt')
async def robots_txt():
    data =  "User-agent: *\n"
    data += "Disallow: /"
    return Response(content=data, media_type='text/plain')


#####################################################################################################################
##### Authorized routes.                                                                                         ####
##### These routes respect the authentication token and will restrict to visible users (GET) or insert user_id (POST) ####
#####################################################################################################################

# @app.get('/v1/authentication/new')
# This will fail if the DB insert fails but still report 'success': True
# Must be reworked if we want to allow API based token generation
# async def get_authentication_token(name: str = None):
#     if name is not None and name.strip() == '':
#         name = None
#     return ORJSONResponse({'success': True, 'data': User.get_new(name)})

# Read your own authentication token. Used by AJAX requests to test if token is valid and save it in local storage
@app.get('/v1/user/settings')
async def get_user_settings(user: User = Depends(authenticate)):
    return ORJSONResponse({'success': True, 'data': user.to_dict()})

@app.put('/v1/user/setting')
async def update_user_setting(setting: UserSetting, user: User = Depends(authenticate)):

    try:
        user.change_setting(setting.name, setting.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(status_code=202) # No-Content

@app.get('/v1/cluster/status')
async def get_cluster_status(
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):
    query = '''
        SELECT id, message, resolved, created_at
        FROM cluster_status_messages
        WHERE resolved = false
        ORDER BY created_at DESC
    '''

    data = DB().fetch_all(query)

    if data is None or data == []:
        return Response(status_code=204)  # No-Content

    return ORJSONResponse({'success': True, 'data': data})


@app.get('/v1/cluster/status/history')
async def get_cluster_status_history(
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):
    query = '''
        SELECT id, message, resolved, created_at
        FROM cluster_status_messages
        ORDER BY created_at DESC
    '''

    data = DB().fetch_all(query)

    if data is None or data == []:
        return Response(status_code=204)  # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/cluster/changelog')
async def get_cluster_changelog(
    machine_id: int | None = None,
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    params = []
    machine_id_condition = ''

    if machine_id is not None:
        machine_id_condition = 'AND machine_id = %s'
        params.append(machine_id)

    query = f"""
        SELECT id, message, machine_id, created_at
        FROM cluster_changelog
        WHERE
            1=1
            {machine_id_condition}
        ORDER BY created_at DESC
    """

    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204)  # No-Content

    return ORJSONResponse({'success': True, 'data': data})


if GlobalConfig().config.get('activate_scenario_runner', False):
    from api import scenario_runner
    app.include_router(scenario_runner.router)

if GlobalConfig().config.get('activate_eco_ci', False):
    from api import eco_ci
    app.include_router(eco_ci.router)

if GlobalConfig().config.get('activate_power_hog', False):
    from api import power_hog
    app.include_router(power_hog.router)

if GlobalConfig().config.get('activate_carbon_db', False):
    from api import carbondb
    app.include_router(carbondb.router)

if GlobalConfig().config.get('activate_ai_optimisations', False):
    from ee.api import ai_optimisations
    app.include_router(ai_optimisations.router)


if __name__ == '__main__':
    app.run() # pylint: disable=no-member
