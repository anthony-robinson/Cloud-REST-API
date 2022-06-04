from google.cloud import datastore
from flask import Flask, request
import json
import constants
import boat
import load

app = Flask(__name__)


@app.route('/')
def index():
    return "Please navigate to /boats to use this API"

app.register_blueprint(boat.bp)
app.register_blueprint(load.bp)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)