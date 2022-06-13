from flask import Blueprint, request
from google.cloud import datastore
import json
import constants
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import google_auth_oauthlib.flow 

from service import application_json_in_accept_header, validate_jwt, query_datastore_boats, query_datastore_loads, get_total_items

client = datastore.Client()
boat_properties = ["name", "type", "length"]
APP_JSON = 'application/json'
ERROR_406 = {'ERROR_406': 'application/json must be in Accept header'}
ERROR_400_INVALID = {'ERROR_400': 'Invalid request - include name, type, length'}
ERROR_400_DUP = 'ERROR 400: Boat with this name already exists'
ERROR_401 = {'ERROR_401': 'The client has provided either no or invalid credentials. Check your JWT and login at /'}
ERROR_404 = {'ERROR_404':'No boat with this boat_id found'}
ERROR_403 = {'ERROR_403': 'You are not permitted to perform this action'}
ALREADY_ASSIGNED = {'ERROR_403': 'Load is already on a boat'}

LOAD_ERROR_404 = {'ERROR_404':'No load with this load_id found on boat'}


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

# function to check if boat's owner and id match else 403 error
def validate_boat_owner(boat, id):
    if boat is not None and boat['owner'] != id:
        return False
    return True

def get_user_boats(owner_id, request):
    if application_json_in_accept_header(request):
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
        output['length'] = get_total_items(constants.boat, owner_id)
        return output
    else:
        return(json.dumps(ERROR_406), 406)

def is_boat_property(prop):
    return prop in boat_properties

#/boats is protected endpoint should only show users boats
@bp.route('', methods=['GET', 'POST'])
def get_post_boats():
    if request.method == 'GET':
        if not application_json_in_accept_header(request):
            return(json.dumps(ERROR_406), 406)
        id = validate_jwt()
        if id:
            res = get_user_boats(id, request)
            return (json.dumps(res, indent = 4), 200)
        else:
            return (json.dumps(ERROR_401), 401)
    #only a user should be able to create boats -- protected endpoint
    elif request.method == 'POST':
        if 'Accept' in request.headers and request.headers['Accept'] == 'application/json':
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
            myRequest['id'] = int(new_boat.key.id)
            myRequest['self'] = request.base_url + "/" + str(new_boat.key.id)
            return(myRequest, 201)
        else:
            return(json.dumps(ERROR_406), 406)

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
            #unload all loads on boat
            if 'loads' in boat and len(boat['loads']):
                for item in boat['loads']:
                    if 'id' in item:
                        load_key = client.key(constants.load, int(item['id']))
                        load = client.get(key=load_key)
                        if load is not None:
                            load.update({
                                'carrier': None
                            })
                            client.put(load)
            client.delete(boat_key)
            return ('',204)
        return (json.dumps(ERROR_404), 404)
    elif request.method == 'PATCH':
        if application_json_in_accept_header(request):
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
            return (json.dumps(ERROR_406), 406)
    elif request.method == 'PUT':
        if application_json_in_accept_header(request):
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
            return (json.dumps(ERROR_406), 406)


# view a boat 
# protected - only can view boat if this boat_id is in the users boats.
@bp.route('/<boat_id>', methods=['GET'])
def get_boat(boat_id):
    if not application_json_in_accept_header(request):
        return(json.dumps(ERROR_406), 406)
    id = validate_jwt()
    if not id:
        return(json.dumps(ERROR_401), 401)
    boat_key = client.key(constants.boat, int(boat_id))
    boat = client.get(key=boat_key)
    if not validate_boat_owner(boat, id):
        return(json.dumps(ERROR_403), 403)
    res = {}
    if boat is not None:
        res = boat
        res['id'] = boat.key.id
        return(json.dumps(res), 200)
    return (ERROR_404, 404)

@bp.route('/<boat_id>/loads/<load_id>', methods = ['PUT'])
def add_load_to_boat(boat_id, load_id):
    if not application_json_in_accept_header(request):
        return (json.dumps(ERROR_406), 406)
    id = validate_jwt()
    if not id:
        return(json.dumps(ERROR_401), 401)
    boat = query_datastore_boats(boat_id)
    if boat is None:
        return (json.dumps(ERROR_404), 404)
    if not validate_boat_owner(boat, id):
        return(json.dumps(ERROR_403), 403)
    load = query_datastore_loads(load_id)
    if load is None:
        return (json.dumps(LOAD_ERROR_404), 404)
    if 'carrier' in load and load['carrier'] is not None:
        return (json.dumps(ALREADY_ASSIGNED), 403)
    boatinfo = {}
    for field in boat:
        if field == 'loads':
            continue
        boatinfo[field] = boat[field]
    boatinfo['self'] = request.host_url + constants.boat + "/" + str(boat.key.id)
    boatinfo['id'] = int(boat.key.id)
    if boat is not None and load is not None:
        if 'loads' in boat.keys():
            # check if load already on boat
            for item in boat['loads']:
                if item['id'] == load.key.id:
                    # load has already been added
                    result = {}
                    for field in boat:
                        result[field] = boat[field]
                    result['self'] = request.host_url + constants.boat + "/" + str(boat.key.id)
                    result['id'] = int(boat.key.id)
                    return(json.dumps(result, indent=5), 200)
            boat['loads'].append({
                'id': load.key.id,
                'self': request.host_url + constants.load + "/" + str(load.key.id)
            })
        else:
            boat['loads'] =  [{
                'id': load.key.id,
                'self': request.host_url + constants.load + "/" + str(load.key.id)
            }]
    client.put(boat)
    load['carrier'] = boatinfo
    client.put(load)
    result = {}
    for field in boat:
        result[field] = boat[field]
    result['self'] = request.host_url + constants.boat + "/" + str(boat.key.id)
    result['id'] = int(boat.key.id)
    return (json.dumps(result, indent=5), 200)

@bp.route('/<boat_id>/loads/<load_id>', methods = ['DELETE'])
def remove_load_from_boat(boat_id, load_id):
    id = validate_jwt()
    if not id:
        return(json.dumps(ERROR_401), 401)
    boat = query_datastore_boats(boat_id)
    if boat is None:
        return (json.dumps(ERROR_404), 404)
    if not validate_boat_owner(boat, id):
        return(json.dumps(ERROR_403), 403)
    load = query_datastore_loads(load_id)
    if load is None:
        return (json.dumps(LOAD_ERROR_404), 404)
    if boat is not None and load is not None:
        if 'loads' in boat.keys():
            # check if load already on boat
            for item in boat['loads']:
                if item['id'] == load.key.id:
                    boat['loads'].remove(item)
                    load['carrier'] = None
                    client.put(boat)
                    client.put(load)
                    return('', 204)
    return (json.dumps(ERROR_404), 404)
        
    

    