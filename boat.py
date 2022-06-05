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

    

def get_user_boats(id):
    query = client.query(kind=constants.boat)
    results = list(query.fetch())
    res = []
    for boat in results:
        if 'owner' in boat and boat['owner'] == id:
            res.append(boat)
    return res

def is_boat_property(prop):
    return prop in boat_properties

#/boats is protected endpoint should only show users boats
@bp.route('', methods=['GET', 'POST'])
def get_post_boats():
    if request.method == 'GET':
        id = validate_jwt()
        if id:
            res = get_user_boats(id)
            return (json.dumps(res), 200)
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

# def get_post_boats():
#     if request.method == 'GET':
#         #query the datastore
#         if 'credentials' not in session:
#             res = get_public_boats()
#             return (json.dumps(res), 200)
#         else:
#             token = session['credentials']['id_token']
#             idinfo = id_token.verify_oauth2_token(token, grequests.Request(), CLIENT_ID)
#             ownerid = idinfo['sub']
#             res = get_boats_from_owner(ownerid)
#             return (json.dumps(res, indent=4), 200)
#     elif request.method == 'POST':
#         #make sure jwt authenticated
#         try:
#             bearer = request.headers.get('Authorization')
#             if bearer:
#                 token = bearer.split()[1]
#             else:
#                 return("Error: unable to create boat, check JWT", 401)
#             idinfo = id_token.verify_oauth2_token(token, grequests.Request(), CLIENT_ID)
#             userid = idinfo['sub']
#             #put in the datastore
#             content = request.get_json()
#             new_boat = datastore.entity.Entity(key=client.key(constants.boat))
#             myRequest = {}
#             for field in content:
#                 new_boat.update({
#                     field: content[field]
#                 })
#                 myRequest[field] = content[field]
#             new_boat.update({
#                 'owner': userid
#             })
#             myRequest['owner'] = new_boat['owner']
#             client.put(new_boat)
#             myRequest['id'] = str(new_boat.key.id)
#             return(myRequest, 201)
#         except ValueError:
#             return("ERROR: Cannot POST /boats, check JWT", 401)


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
@bp.route('/<boat_id>', methods=['GET'])
def get_boat(boat_id):
    query = client.query(kind=constants.boat)
    results = list(query.fetch())
    for e in results:
        e["id"] = e.key.id
    for e in results:
        if str(e['id']) == str(boat_id):
            if 'application/json' in request.accept_mimetypes:
                return(json.dumps(e, indent=4), 200)
            elif 'text/html' in request.accept_mimetypes:
                res = Response(json2html.json2html.convert(json=json.dumps(e)))
                res.headers.set('Content-Type', 'text/html')
                return res
    return (ERROR_404, 404)

    