# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python38_app]
# [START gae_python3_app]
from flask import Flask, session, abort
from flask_session import Session
import os.path

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)

@app.route('/ping/')
def hello():
    if(not os.path.exists("/tmp/sample.txt")):
        return 'Hello World!'

    with open("/tmp/sample.txt") as file:
        content = file.read()
        if(content == "0"):
            abort(404)
        else:
            return 'Hello World!'

@app.route('/manage/<signal>')
def manage(signal):
    print(signal)
    if(signal == "turnOn"):
        with open("/tmp/sample.txt","w") as file:
            file.write("1")
            file.close()
        return 'Signal understood'
    if(signal == "turnOff"):
        with open("/tmp/sample.txt","w") as file:
            file.write("0")
            file.close()
        return 'Signal understood'
    return 'Signal not understood'

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. You
    # can configure startup instructions by adding `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python3_app]
# [END gae_python38_app]
