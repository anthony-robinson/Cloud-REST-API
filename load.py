from flask import Blueprint, request
from google.cloud import datastore
import json
from json2html import *
import constants

client = datastore.Client()

bp = Blueprint('load', __name__, url_prefix='/loads')

@bp.route('', methods=['POST'])
def create_load():
    content = request.get_json()
    new_load = datastore.entity.Entity(key=client.key(constants.load))
    new_load.update({
        "volume": content["volume"],
        "carrier": None,
        "item": content["item"],
        "creation_date": content["creation_date"],
        }
    )
    myRequest = {
        "volume": content["volume"],
        "carrier": None,
        "item": content["item"],
        "creation_date": content["creation_date"]
    }
    client.put(new_load)
    return (json.dumps(myRequest), 201)


@bp.route('/<load_id>', methods=['GET'])
def get_load(load_id):
    query = client.query(kind=constants.load)
    results = list(query.fetch())
    for e in results:
        e["id"] = e.key.id
        e["self"] = request.url + str(e.key.id)
    for e in results:
        if str(e['id']) == str(load_id):
            return(json.dumps(e, indent=4), 200)
    return ('Error: No load with this load_id exists ', 404)

# The following methods are adapted from the lecture notes OSU CS 493
@bp.route('', methods=['GET'])
def get_all_loads():
    query = client.query(kind=constants.load)
    q_limit = int(request.args.get('limit', '3'))
    q_offset = int(request.args.get('offset', '0'))
    g_iterator = query.fetch(limit= q_limit, offset=q_offset)
    pages = g_iterator.pages
    results = list(next(pages))
    if g_iterator.next_page_token:
        next_offset = q_offset + q_limit
        next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
    else:
        next_url = None
    for e in results:
        e["id"] = e.key.id
        e["self"] = request.url + "/" + str(e.key.id)
    output = {"loads": results}
    if next_url:
        output["next"] = next_url
    return json.dumps(output)


@bp.route('/<load_id>', methods=['DELETE'])
def delete_load(load_id):
    load_key = client.key(constants.loads, int(load_id))
    load = client.get(key=load_key)
    if load is not None:
        client.delete(load_key)
        return ('',204)
    return ('Error: No load with this load_id exists', 404)