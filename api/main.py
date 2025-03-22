# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic?
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from fastapi import FastAPI, Request, Response, Depends
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
        headers_mut['X-Authentication'] = '****OBFUSCATED****'
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
##### These must have Authentication token set and will restrict to visible users (GET) or insert user_id (POST) ####
#####################################################################################################################

# @app.get('/v1/authentication/new')
# This will fail if the DB insert fails but still report 'success': True
# Must be reworked if we want to allow API based token generation
# async def get_authentication_token(name: str = None):
#     if name is not None and name.strip() == '':
#         name = None
#     return ORJSONResponse({'success': True, 'data': User.get_new(name)})

# Read your own authentication token. Used by AJAX requests to test if token is valid and save it in local storage
@app.get('/v1/authentication/data')
async def read_authentication_token(user: User = Depends(authenticate)):
    return ORJSONResponse({'success': True, 'data': user.to_dict()})

if GlobalConfig().config.get('activate_scenario_runner', False):
    from api import scenario_runner
    app.include_router(scenario_runner.router)

if GlobalConfig().config.get('activate_eco_ci', False):
    from api import eco_ci
    app.include_router(eco_ci.router)

if GlobalConfig().config.get('activate_power_hog', False):
    from ee.api import power_hog
    app.include_router(power_hog.router)

if GlobalConfig().config.get('activate_carbon_db', False):
    from ee.api import carbondb
    app.include_router(carbondb.router)


if __name__ == '__main__':
    app.run() # pylint: disable=no-member
