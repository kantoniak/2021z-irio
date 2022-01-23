# from main import entrypoint
import logging
import requests
import os
import sys
from google.cloud import logging as cloudlogging
import json
import time
import requests

cloudlogging.Client().setup_logging()
logger = logging.getLogger()

DB_CONN_NAME = os.getenv('DB_CONN_NAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')
PROJECT_NAME = os.getenv('PROJECT_NAME')

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
    query = ""
    query += "DELETE FROM services;\n"
    query += """INSERT INTO "services" ("id", "name", "url", "primary_admin_email", "secondary_admin_email", "last_time_responsive", "being_worked_on", "primary_admin_key") VALUES\n"""
             
    for i in range(how_many):
        query += "({}, '{}', '{}', 'admin1@example.com', 'admin2@example.com', NULL, FALSE, NULL)".format(i, "example" + str(i), MOCK_PAGE + "/ping/")
        if i != how_many - 1:
            query += ",\n"
        else:
            query += ";\n"

    with open(filename + ".sql", 'w') as file:
        original_stdout = sys.stdout
        sys.stdout = file
        print(query)
        sys.stdout = original_stdout


if __name__ == "__main__":
    if sys.argv[1] == "0":
        generate_SQL(int(sys.argv[2]), sys.argv[3])
    else:
        requests.get(
            MOCK_PAGE + "/manage/turnOn",
            allow_redirects=True,
            timeout=(10, 10),
        )
        print(MOCK_PAGE + "/manage/turnOn")
        print("Mock service is up and running. Waiting for functions to see that")
        time.sleep(2 * FREQUENCY)
        requests.get(
            MOCK_PAGE + "/manage/turnOff",
            allow_redirects=True,
            timeout=(10, 10),
        )
        print("Mock service stops respoding. Collecting data...")
        time.sleep(2 * FREQUENCY + ALERTING_WINDOW_SEC + ALLOWED_RESPONSE_TIME + 10)
        print("Data should be collected by now. View dashboards and logs for further reference.")


# python3 stress_test.py 0 100 example

# gsutil mb gs://testing-bucket-for-irio
# gsutil cp example.sql gs://testing-bucket-for-irio
# SA_NAME=$(gcloud sql instances describe [YOUR_DB_INSTANCE_NAME] --project=[YOUR_PROJECT_ID] --format="value(serviceAccountEmailAddress)")
# gsutil acl ch -u ${SA_NAME}:R gs://testing-bucket-for-irio
# gsutil acl ch -u ${SA_NAME}:R gs://testing-bucket-for-irio/example.sql
# gcloud sql import sql services-instance gs://testing-bucket-for-irio/example.sql --database=services-db --user=services_user

