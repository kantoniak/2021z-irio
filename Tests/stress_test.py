# from main import entrypoint
import logging
import requests
import os
import sys
from google.cloud import logging as cloudlogging
import time
import requests
import uuid

cloudlogging.Client().setup_logging()
logger = logging.getLogger()

DB_CONN_NAME = os.getenv('DB_CONN_NAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')
PROJECT_NAME = os.getenv('PROJECT_NAME')
REGION = os.getenv('REGION')
FUNC_TO_MARK_AS_BEING_WORKED_ON = os.getenv('FUNC_TO_MARK_AS_BEING_WORKED_ON')


ALLOWED_RESPONSE_TIME = os.getenv('ALLOWED_RESPONSE_TIME')
ALERTING_WINDOW_SEC = os.getenv('ALERTING_WINDOW_SEC')
FREQUENCY = os.getenv('FREQUENCY')

if DB_CONN_NAME is None:
    raise RuntimeError('Missing environment variable: DB_CONN_NAME')
if DB_USERNAME is None:
    raise RuntimeError('Missing environment variable: DB_USERNAME')
if DB_PASSWORD is None:
    raise RuntimeError('Missing environment variable: DB_PASSWORD')
if DB_DATABASE is None:
    raise RuntimeError('Missing environment variable: DB_DATABASE')
if PROJECT_NAME is None:
    raise RuntimeError('Missing environment variable: PROJECT_NAME')
if REGION is None:
    raise RuntimeError('Missing environment variable: REGION')
if FUNC_TO_MARK_AS_BEING_WORKED_ON is None:
    raise RuntimeError('Missing environment variable: FUNC_TO_MARK_AS_BEING_WORKED_ON')



if ALLOWED_RESPONSE_TIME is None:
    raise RuntimeError('Missing environment variable: ALLOWED_RESPONSE_TIME')
else:
    ALLOWED_RESPONSE_TIME = int(ALLOWED_RESPONSE_TIME)
if ALERTING_WINDOW_SEC is None:
  raise RuntimeError('Missing environment variable: ALERTING_WINDOW_SEC')
else:
  ALERTING_WINDOW_SEC = int(ALERTING_WINDOW_SEC)
if FREQUENCY is None:
  raise RuntimeError('Missing environment variable: FREQUENCY')
else:
  FREQUENCY = int(FREQUENCY)


MOCK_PAGE = "https://" + PROJECT_NAME + ".appspot.com"

def generate_SQL(how_many, filename):
    already_present_uuids = [uuid.uuid4().hex for i in range(int(how_many / 4))] 

    query = ""
    query += "DELETE FROM services;\n"
    query += """INSERT INTO "services" ("id", "name", "url", "primary_admin_email", "secondary_admin_email", "last_time_responsive", "being_worked_on", "primary_admin_key") VALUES\n"""
             
    for i in range(how_many):
        real_or_not_real_uuid = "NULL"
        if (i < len(already_present_uuids)):
            real_or_not_real_uuid = "'" + str(already_present_uuids[i]) + "'"

        query += "({}, '{}', '{}', 'admin1@example.com', 'admin2@example.com', NULL, FALSE, {})".format(i, "example" + str(i), MOCK_PAGE + "/ping/", real_or_not_real_uuid)
        if i != how_many - 1:
            query += ",\n"
        else:
            query += ";\n"

    with open(filename + ".sql", 'w') as file:
        original_stdout = sys.stdout
        sys.stdout = file
        print(query)
        sys.stdout = original_stdout

    return already_present_uuids

NOTIFYING_URL = "https://" + REGION + "-" + PROJECT_NAME + ".cloudfunctions.net/" + FUNC_TO_MARK_AS_BEING_WORKED_ON + "?key="

if __name__ == "__main__":
    if sys.argv[1] == "0":
        uiuds = generate_SQL(int(sys.argv[2]), sys.argv[3])
        with open("uuids.txt", 'w') as file:
            original_stdout = sys.stdout
            sys.stdout = file
            print(",".join(str(uuid) for uuid in uiuds))
            sys.stdout = original_stdout
    else:
        with open("uuids.txt", 'r') as file:
            uuids = file.read()
            uuids = uuids.split(",")
        requests.get(
            MOCK_PAGE + "/manage/turnOn",
        )
        print("Mock service is up and running. Waiting for functions to see that")
        time.sleep(2 * FREQUENCY)
        requests.get(
            MOCK_PAGE + "/manage/turnOff",
        )
        print("Mock service stops respoding. Collecting data...")
        time.sleep(FREQUENCY + ALERTING_WINDOW_SEC + 10)
        for good_uuid in uuids:
            requests.get(
                NOTIFYING_URL + str(good_uuid), # Valid Uuids
            )
            requests.get(
                NOTIFYING_URL + str(uuid.uuid4()), # Invalid Uuids
            )
        print("Sent partially fake data. Waiting for the rest of the data...")
        time.sleep(FREQUENCY + ALLOWED_RESPONSE_TIME + 10)
        print("Data should be collected by now. View dashboards and logs for further reference.")