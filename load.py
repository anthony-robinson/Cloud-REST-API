from flask import Blueprint, request
from google.cloud import datastore
import json
from json2html import *
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from datetime import date
import constants
from boat import application_json_in_accept_header

client = datastore.Client()

bp = Blueprint('load', __name__, url_prefix='/loads')

ERROR_406 = {'ERROR_406': 'ERROR 406: application/json must be in Accept header'}
ERROR_400_INVALID = {'ERROR_400': 'Error: Invalid request - include name, type, length'}
ERROR_400_DUP = 'ERROR 400: Load with this name already exists'
ERROR_401 = {'ERROR_401': 'ERROR 401: The client has provided either no or invalid credentials. Check your JWT and login at /'}
ERROR_404 = {'ERROR_404':'ERROR 404: No load with this load_id exists'}
ERROR_403 = {'ERROR_403': 'ERROR 403: You are not permitted to perform this action'}

load_properties = ['volume', 'item']

# validates the load POST request
def validate_load_req(content):
    if any(prop not in content for prop in load_properties):
        return False
    return True


def get_loads(request):
    query = client.query(kind=constants.load)

    qlimit = int(request.args.get('limit', '5'))
    qoffset = int(request.args.get('offset', '0'))
    load_iterator = query.fetch(limit=qlimit, offset=qoffset)
    pages = load_iterator.pages
    next_url = None
    results = list(next(pages))
    if load_iterator.next_page_token:
        next_offset = qoffset + qlimit
        next_url = request.base_url + "?limit=" + str(qlimit) + "&offset=" + str(next_offset)

    for load in results:
        load['id'] = load.key.id
        load['self'] = request.base_url + "/" + str(load.key.id)
    output = {"loads": results}
    if next_url:
        output['next'] = next_url
    return output

@bp.route('', methods=['GET', 'POST'])
def create_load():
    if request.method == 'POST':
        if not application_json_in_accept_header(request):
            return(json.dumps(ERROR_406), 406)
        content = request.get_json()
        if not validate_load_req(content):
            return (json.dumps(ERROR_400_INVALID), 400)
        current_day = date.today()
        formatted_date = date.strftime(current_day, "%m/%d/%Y")
        new_load = datastore.entity.Entity(key=client.key(constants.load))
        new_load.update({
            "volume": content["volume"],
            "carrier": None,
            "item": content["item"],
            "load_creation_date": formatted_date
            }
        )
        myRequest = {
            "volume": content["volume"],
            "carrier": None,
            "item": content["item"],
            "load_creation_date": formatted_date
        }
        client.put(new_load)
        myRequest['id'] = str(new_load.key.id)
        myRequest['self'] = request.base_url + "/" + str(new_load.key.id)
        return (json.dumps(myRequest, indent=5), 201)
    elif request.method == 'GET':
        if not application_json_in_accept_header(request):
            return (json.dumps(ERROR_406), 406)
        res = get_loads(request)
        return (json.dumps(res, indent=5), 200)


@bp.route('/<load_id>', methods=['GET'])
def get_load(load_id):
    if not application_json_in_accept_header(request):
        return(json.dumps(ERROR_406), 406)
    load_key = client.key(constants.load, int(load_id))
    load = client.get(key=load_key)
    if load is None:
        return (json.dumps(ERROR_404), 404)
    res = load
    res['id'] = load.key.id
    res['self'] = request.base_url
    if load is not None:
        return(json.dumps(res), 200)
    return (json.dumps(ERROR_404), 404)

@bp.route('/<load_id>', methods=['PUT', 'PATCH','DELETE'])
def edit_delete_load(load_id):
    if request.method == 'DELETE':
        load_key = client.key(constants.load, int(load_id))
        load = client.get(key=load_key)
        if load and 'carrier' in load and load['carrier'] is not None:
            boat_key = client.key(constants.boat, int(load['carrier']['id']))
            boat = client.get(key=boat_key)
            if boat is not None and 'loads' in boat:
                for item in boat['loads']:
                    if item['id'] == load.key.id:
                        boat['loads'].remove(item)
                        client.put(boat)
        
        if load is not None:
            client.delete(load_key)
            return ('',204)
        return (json.dumps(ERROR_404), 404)