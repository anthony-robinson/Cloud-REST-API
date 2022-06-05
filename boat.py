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
ERROR_406 = 'Error: Mimetype not supported by the server'
ERROR_400_INVALID = 'Error: Invalid request - include name, type, length'
ERROR_400_DUP = 'Error: Boat with this name already exists'
ERROR_404 = 'Error: No boat with this boat_id exists'
ERROR_403 = 'ERROR: You are not permitted to access this information, check JWT or login at /'

CLIENT_ID = '268406931256-i8ctpko2kel510pn40riv3l89ccebhr3.apps.googleusercontent.com'

bp = Blueprint('boat', __name__, url_prefix='/boats')

def validate_string(s):
    if len(s) < 1:
        return False
    if len(s) > 20:
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
            return (json.dumps(ERROR_403), 403)
    #only a user should be able to create boats -- protected endpoint
    elif request.method == 'POST':
        id = validate_jwt()
        if not id:
            return(json.dumps(ERROR_403), 403)
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
            'owner': id
        })
        myRequest['owner'] = id
        client.put(new_boat)
        myRequest['id'] = str(new_boat.key.id)
        return(myRequest, 201)

# DELETE and PUT are added here to ensure 405 metho
# @bp.route('', methods=['POST'])
# def create_boat():
#     if request.method == "POST":
#         if request.is_json:
#             content = request.get_json()
#             if not validate(content):
#                 return(ERROR_400_INVALID, 400)
#             if not is_unique_name(content):
#                 return(ERROR_400_DUP, 400)
#             new_boat = datastore.entity.Entity(key=client.key(constants.boat))
#             myRequest = {}
#             for field in content:
#                 new_boat.update({
#                     field: content[field]
#                 })
#                 myRequest[field] = content[field]
#             client.put(new_boat)
#             myRequest['id'] = str(new_boat.key.id)
#             return(myRequest, 201)
#         else:
#             return (ERROR_406, 406)

@bp.route('/<boat_id>', methods=['DELETE', 'PATCH', 'PUT'])
def edit_delete_boat(boat_id):
    if request.method == 'DELETE':
        boat_key = client.key(constants.boat, int(boat_id))
        boat = client.get(key=boat_key)
        if boat is not None:
            client.delete(boat_key)
            return ('',204)
        return ('Error: No boat with this boat_id exists', 404)
    elif request.method == 'PATCH':
        if request.is_json:
            content = request.get_json()
            if 'name' in content:
                if not is_unique_name(content):
                    return (ERROR_400_DUP, 400)
                if not validate_string(content['name']):
                    return (ERROR_400_INVALID, 400)
            if "type" in content:
                if not validate_string(content["type"]):
                    return(ERROR_400_INVALID, 400)
            if "id" in content:
                return (ERROR_400_INVALID, 400)
            boat_key = client.key(constants.boat, int(boat_id))
            boat = client.get(key=boat_key)
            if boat is None:
                return (ERROR_404, 404)
            for field in content:
                boat.update({
                    field: content[field]
                })
            client.put(boat)
            boat["id"] = boat.key.id
            result = client.get(key=boat_key)
            result["id"] = result.key.id
            return json.dumps(result, indent=4)
        else:
            return (ERROR_406, 406)
    elif request.method == 'PUT':
        if request.is_json:
            content = request.get_json()
            if not validate(content):
                return(ERROR_400_INVALID, 400)
            if not is_unique_name(content):
                return(ERROR_400_DUP, 400)
            if "id" in content:
                return (ERROR_400_INVALID, 400)
            boat_key = client.key(constants.boat, int(boat_id))
            boat = client.get(key=boat_key)
            if boat is None:
                return (ERROR_404, 404)
            for field in content:
                boat.update({
                    field: content[field]
                })
            boat.update({
                "name": content['name'],
                "length": content["length"],
                "type": content["type"]
            })
            client.put(boat)
            boat["id"] = boat.key.id
            url = request.base_url 
            obj = client.get(key=boat_key)
            obj["id"] = obj.key.id
            res = Response(json.dumps(obj))
            res.status_code = 303
            res.headers['Location'] = url
            return res
        else:
            return (ERROR_406, 406)


# view a boat 
# protected - only can view boat if this boat_id is in the users boats.
@bp.route('/<boat_id>', methods=['GET'])
def get_boat(boat_id):
    id = validate_jwt()
    if not id:
        return(json.dumps(ERROR_403), 403)
    boat_key = client.key(constants.boat, int(boat_id))
    boat = client.get(key=boat_key)
    if boat is not None:
        return(json.dumps(boat), 200)
    return (ERROR_404, 404)

    