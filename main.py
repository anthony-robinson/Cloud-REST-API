from google.cloud import datastore
from flask import Flask, request, render_template, redirect, session, url_for
import json
import constants
import boat
import load
import uuid
import os
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import google_auth_oauthlib.flow 

client = datastore.Client()

CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/userinfo.profile']
CLIENT_ID = '268406931256-i8ctpko2kel510pn40riv3l89ccebhr3.apps.googleusercontent.com'

app = Flask(__name__)
app.config['SECRET_KEY'] = str(uuid.uuid4())


@app.route('/')
def index():
    return render_template("main.html")

app.register_blueprint(boat.bp)
app.register_blueprint(load.bp)

def credentials_to_dict(credentials):
  return {'token': credentials.token,
          'refresh_token': credentials.refresh_token,
          'id_token': credentials.id_token,
          'token_uri': credentials.token_uri,
          'client_id': credentials.client_id,
          'client_secret': credentials.client_secret,
          'scopes': credentials.scopes}

# Boolean that returns true if the user_id is already in the datastore
def user_exists(id):
    query = client.query(kind=constants.user)
    results = query.fetch()
    for user in results:
        if id == user['user_id']:
            return True
    return False

@app.route('/authorize')
def authorize():
        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES)

  # The URI created here must exactly match one of the authorized redirect URIs
  # for the OAuth 2.0 client, which you configured in the API Console. If this
  # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
  # error.
  flow.redirect_uri = url_for('oauth2callback', _external=True)

  authorization_url, state = flow.authorization_url(
      # Enable offline access so that you can refresh an access token without
      # re-prompting the user for permission. Recommended for web server apps.
      access_type='offline',
      # Enable incremental authorization. Recommended as a best practice.
      include_granted_scopes='true')

  # Store the state so the callback can verify the auth server response.
  session['state'] = state

  return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    authorization_response = request.url
    
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials
    print("credentials")
    print(flow.credentials.to_json())
    session['credentials'] = credentials_to_dict(credentials)
    return redirect(url_for('user_page'))

@app.route('/userinfo')
def user_page():
    if 'credentials' in session:
        token = session['credentials']['id_token']
    else:
        bearer = request.headers.get('Authorization')
        if bearer: 
            token = bearer.split()[1]
        else:
            return("ERROR: User must be logged in, check JWT", 401)
    try:
        idinfo = id_token.verify_oauth2_token(token, grequests.Request(), CLIENT_ID)
        username = 'N/A'
        userid = idinfo['sub']

        #first query the datastore to check if user is already in
        # don't add to the datastore, just return
        if user_exists(userid):
            return render_template('user.html', idToken=token, userName=username, id=userid)

        #add the user to the datastore
        new_user = datastore.entity.Entity(key=client.key(constants.user))
        if 'name' in idinfo:
            username = idinfo['name']
        new_user.update({
            "user_id": userid,
            "name": username
        })
        client.put(new_user)
        return render_template('user.html', idToken=token, userName=username, id=userid)
    except ValueError:
        return ("ERROR: Cannot get userinfo, check JWT", 401)
    
#unprotected endpoint
@app.route('/users', methods=['GET'])
def get_users():
    query = client.query(kind=constants.user)
    results = list(query.fetch())
    return (json.dumps(results, indent=4), 200)


if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(host='127.0.0.1', port=8000, debug=True)