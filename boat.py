from flask import Blueprint, request, Response, session
from google.cloud import datastore
import json2html
import json
import constants
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import google_auth_oauthlib.flow 

client = datastore.Client()
boat_properties = ["name", "type", "length"]
APP_JSON = 'application/json'
ERROR_406 = 'ERROR 406: Mimetype not supported by the server'
ERROR_400_INVALID = 'Error: Invalid request - include name, type, length'
ERROR_400_DUP = 'ERROR 400: Boat with this name already exists'
ERROR_401 = 'ERROR 401: The client has provided either no or invalid credentials. Check your JWT and login at /'
ERROR_404 = 'ERROR 404: No boat with this boat_id exists'
ERROR_403 = 'ERROR 403: You are not permitted to perform this action'


CLIENT_ID = '268406931256-i8ctpko2kel510pn40riv3l89ccebhr3.apps.googleusercontent.com'

bp = Blueprint('boat', __name__, url_prefix='/boats')

def validate_string(s):
    if len(s) < 1:
        return False
    return True


def validate(content):
    if any(prop not in content for prop in boat_properties):
        return False
    if not validate_string(content['name']) or not validate_string(content['type']):
        return False
    if "id" in content: return False
    return True

def is_unique_name(content):
    query = client.query(kind=constants.boat)
    results = list(query.fetch())
    for e in results:
        if content["name"] == e["name"]:
            return False
    return True

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

# function to check if boat's owner and id match else 403 error
def validate_boat_owner(boat, id):
    if boat is not None and boat['owner'] != id:
        return False
    return True

    

def get_user_boats(owner_id, request):
    query = client.query(kind=constants.boat)

    qlimit = int(request.args.get('limit', '5'))
    qoffset = int(request.args.get('offset', '0'))
    query.add_filter("owner", "=", owner_id)
    boat_iterator = query.fetch(limit=qlimit, offset=qoffset)
    pages = boat_iterator.pages
    next_url = None
    results = list(next(pages))
    if boat_iterator.next_page_token:
        next_offset = qoffset + qlimit
        next_url = request.base_url + "?limit=" + str(qlimit) + "&offset=" + str(next_offset)

    for boat in results:
        boat['id'] = boat.key.id
        boat['self'] = request.base_url + "/" + str(boat.key.id)
    output = {"boats": results}
    if next_url:
        output['next'] = next_url
    return output

def is_boat_property(prop):
    return prop in boat_properties

#/boats is protected endpoint should only show users boats
@bp.route('', methods=['GET', 'POST'])
def get_post_boats():
    if request.method == 'GET':
        id = validate_jwt()
        if id:
            res = get_user_boats(id, request)
            return (json.dumps(res, indent = 4), 200)
        else:
            return (json.dumps(ERROR_401), 401)
    #only a user should be able to create boats -- protected endpoint
    elif request.method == 'POST':
        id = validate_jwt()
        if not id:
            return(json.dumps(ERROR_401), 401)
        content = request.get_json()
        if not validate(content):
            return (json.dumps(ERROR_400_INVALID), 400)
        myRequest = {}
        new_boat = datastore.entity.Entity(key=client.key(constants.boat))
        for field in content:
            new_boat.update({
                field: content[field]
            })
            myRequest[field] = content[field]
        new_boat.update({
            'owner': id,
            'loads': []
        })
        myRequest['owner'] = id
        myRequest['loads'] = []
        client.put(new_boat)
        myRequest['id'] = str(new_boat.key.id)
        return(myRequest, 201)

@bp.route('/<boat_id>', methods=['DELETE', 'PATCH', 'PUT'])
def edit_delete_boat(boat_id):
    # DELETE /:boat_id is a protected endpoint -- only user can delete a boat
    if request.method == 'DELETE':
        id = validate_jwt()
        if not id:
            return(json.dumps(ERROR_401), 401)
        boat_key = client.key(constants.boat, int(boat_id))
        boat = client.get(key=boat_key)
        if boat is not None and boat['owner'] != id:
            return(json.dumps(ERROR_403), 403)
        if boat is not None:
            client.delete(boat_key)
            return ('',204)
        return (json.dumps(ERROR_404), 404)
    elif request.method == 'PATCH':
        if request.is_json:
            id = validate_jwt()
            if not id:
                return(json.dumps(ERROR_401), 401)
            content = request.get_json()
            boat_key = client.key(constants.boat, int(boat_id))
            boat = client.get(key=boat_key)
            if boat is None:
                return (ERROR_404, 404)
            if not validate_boat_owner(boat, id):
                return(json.dumps(ERROR_403), 403)
            for field in content:
                boat.update({
                    field: content[field]
                })
            client.put(boat)
            boat["id"] = boat.key.id
            result = client.get(key=boat_key)
            result["id"] = result.key.id
            result['owner'] = boat['owner']
            result['self'] = request.base_url
            return (json.dumps(result, indent=5), 200)
        else:
            return (ERROR_406, 406)
    elif request.method == 'PUT':
        if request.is_json:
            id = validate_jwt()
            if not id:
                return(json.dumps(ERROR_401), 401)
            content = request.get_json()
            boat_key = client.key(constants.boat, int(boat_id))
            boat = client.get(key=boat_key)
            res = {}
            if boat is None:
                return (ERROR_404, 404)
            if not validate_boat_owner(boat, id):
                return(json.dumps(ERROR_403), 403)
            for field in content:
                boat.update({
                    field: content[field]
                })
                res[field] = content[field]
            boat.update({
                "name": content['name'],
                "length": content["length"],
                "type": content["type"]
            })
            client.put(boat)
            boat["id"] = boat.key.id
            res['id'] = boat.key.id
            res['self'] = request.base_url
            res['owner'] = boat['owner']
            return (json.dumps(res, indent=5), 200)
        else:
            return (ERROR_406, 406)


# view a boat 
# protected - only can view boat if this boat_id is in the users boats.
@bp.route('/<boat_id>', methods=['GET'])
def get_boat(boat_id):
    id = validate_jwt()
    if not id:
        return(json.dumps(ERROR_401), 401)
    boat_key = client.key(constants.boat, int(boat_id))
    boat = client.get(key=boat_key)
    if not validate_boat_owner(boat, id):
        return(json.dumps(ERROR_403), 403)
    if boat is not None:
        return(json.dumps(boat), 200)
    return (ERROR_404, 404)

    