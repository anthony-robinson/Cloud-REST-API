from flask import request
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from google.cloud import datastore
import constants

CLIENT_ID = '268406931256-i8ctpko2kel510pn40riv3l89ccebhr3.apps.googleusercontent.com'
client = datastore.Client()

# validate the JWT using Google's API.
def validate_jwt():
    bearer = request.headers.get('Authorization')
    if bearer: 
        token = bearer.split()[1]
    else:
        return False
    try:
        idinfo = id_token.verify_oauth2_token(token, grequests.Request(), CLIENT_ID)
        userid = idinfo['sub']
        return userid
    except ValueError:
        return False

# check application/json is set in the Accept header.
def application_json_in_accept_header(request):
    if 'Accept' in request.headers and request.headers['Accept'] == 'application/json':
        return True
    return False

# find a boat in the data store.
def query_datastore_boats(boat_id):
    boat_key = client.key(constants.boat, int(boat_id))
    boat = client.get(key=boat_key)
    return boat

# find a load in the data store
def query_datastore_loads(load_id):
    load_key = client.key(constants.load, int(load_id))
    load = client.get(key=load_key)
    return load

# Returns the total number of entities in the datastore. Expects a valid query_kind
def get_total_items(query_kind, owner_id=None):
    if query_kind == constants.boat:
        query = client.query(kind=query_kind)
        query.add_filter("owner", "=", owner_id)
        return len(list(query.fetch()))
    query = client.query(kind=query_kind)
    return len(list(query.fetch()))