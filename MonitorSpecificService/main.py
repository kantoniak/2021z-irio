import base64
import datetime
import logging
import os
import requests
import sqlalchemy
import time
import uuid
from google.cloud import logging as cloudlogging
from sqlalchemy.sql import text
from mailjet_rest import Client
from google.cloud import tasks_v2
import json




cloudlogging.Client().setup_logging()
logger = logging.getLogger()

DB_CONN_NAME = os.getenv('DB_CONN_NAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')
QUEUE_NAME = os.getenv('QUEUE_NAME')
REGION = os.getenv('REGION')
FUNC_TO_CALL = os.getenv('FUNC_TO_CALL')
PROJECT = os.getenv('PROJECT_NAME')

ALLOWED_RESPONSE_TIME = os.getenv('ALLOWED_RESPONSE_TIME')
REQUEST_TIMEOUT_SEC = os.getenv('REQUEST_TIMEOUT_SEC')
ALERTING_WINDOW_SEC = os.getenv('ALERTING_WINDOW_SEC')

if DB_CONN_NAME is None:
    raise RuntimeError('Missing environment variable: DB_CONN_NAME')
if DB_USERNAME is None:
    raise RuntimeError('Missing environment variable: DB_USERNAME')
if DB_PASSWORD is None:
    raise RuntimeError('Missing environment variable: DB_PASSWORD')
if DB_DATABASE is None:
    raise RuntimeError('Missing environment variable: DB_DATABASE')
if QUEUE_NAME is None:
    raise RuntimeError('Missing environment variable: QUEUE_NAME')
if REGION is None:
    raise RuntimeError('Missing environment variable: REGION')
if FUNC_TO_CALL is None:
    raise RuntimeError('Missing environment variable: FUNC_TO_CALL')
if PROJECT is None:
    raise RuntimeError('Missing environment variable: PROJECT')


if ALLOWED_RESPONSE_TIME is None:
    raise RuntimeError('Missing environment variable: ALLOWED_RESPONSE_TIME')
else:
    ALLOWED_RESPONSE_TIME = int(ALLOWED_RESPONSE_TIME)

if REQUEST_TIMEOUT_SEC is None:
  raise RuntimeError('Missing environment variable: REQUEST_TIMEOUT_SEC')
else:
  REQUEST_TIMEOUT_SEC = int(REQUEST_TIMEOUT_SEC)

if ALERTING_WINDOW_SEC is None:
  raise RuntimeError('Missing environment variable: ALERTING_WINDOW_SEC')
else:
  ALERTING_WINDOW_SEC = int(ALERTING_WINDOW_SEC)

api_key = '13bde1f003f14dfe019284c8839ec9fa' # TODO : fix this
api_secret = '4e64b4ac3672eec18b0fbdc4d79a1817' # TODO : fix this
MY_MAIL = "automatedmailer@protonmail.com"
MAILJET = Client(auth=(api_key, api_secret), version='v3.1')
def send_mail(recipient, service_name):
    data = {
        "Messages": [
            {
                "From": {
                    "Email": MY_MAIL,
                    "Name": "Alerting platform automatic mailer",
                },
                "To": [{"Email": recipient, "Name": recipient}],
                "Subject": "Warning, service is down",
                "TextPart": "Warning, service {} is down!".format(service_name),
                "HTMLPart": "",
                "CustomID": "",
            }
        ]
    }

    result = MAILJET.send.create(data=data)
    return result.json()

def schedule_task(service_id, delay):
    # https://cloud.google.com/tasks/docs/samples/cloud-tasks-taskqueues-new-task
    # https://cloud.google.com/tasks/docs/creating-http-target-tasks
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT, REGION, QUEUE_NAME)

    task = {
        'http_request': {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": "https://" + REGION + "-" + PROJECT + ".cloudfunctions.net/" + FUNC_TO_CALL,
            'headers': {
                "Content-Type": "application/json"
            },
            "oidc_token": {
                "service_account_email": PROJECT + "@appspot.gserviceaccount.com"
            },
            "body": json.dumps({"service_id" : service_id}).encode("utf-8"),
        },
        'schedule_time': datetime.datetime.now() + datetime.timedelta(seconds=delay) 
    }
    return client.create_task(request={"parent": parent, "task": task})


def init_pool(conn_name, username, password, database):
    pool = sqlalchemy.create_engine(
        sqlalchemy.engine.url.URL.create(
            drivername="postgresql+pg8000",
            username=username,
            password=password,
            database=database,
            query={
                "unix_sock": "/cloudsql/{}/.s.PGSQL.5432".format(conn_name)
            }
        ),
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800
    )
    pool.dialect.description_encoding = None
    return pool


def initialize_db(conn):
    conn.execute("""
CREATE TABLE IF NOT EXISTS "services" (
    "id" INT NOT NULL,
    "name" VARCHAR(256) NOT NULL,
    "url" TEXT NOT NULL,
    "primary_admin_email" VARCHAR(254) NOT NULL,
    "secondary_admin_email" VARCHAR(254) NOT NULL,
    "last_time_responsive" TIMESTAMP NULL,
    "being_worked_on" BOOLEAN NOT NULL DEFAULT FALSE,
    "primary_admin_key" UUID NULL,
    CONSTRAINT "services_pk" PRIMARY KEY (id)
);""")

def handle_service_up(service, conn):
    conn.execute(
        text("UPDATE services SET last_time_responsive = :datetime WHERE id = :id"),
        {
            'id': service['id'],
            'datetime': datetime.datetime.now()
        }
    )


def handle_service_down(service, conn):
    time_now = datetime.datetime.now()

    since_last_check = (time_now - service['last_time_responsive']).total_seconds()
    if since_last_check > ALERTING_WINDOW_SEC:
        new_incident = True  # FIXME: How do we know current downtime had/had not been detected?

        if new_incident:
            service_name = service['name']
            logger.info(f'Service "{service_name}" down.')
            service_id = service['id']

            primary_key = str(uuid.uuid4())
            conn.execute(
                text("UPDATE services SET being_worked_on = FALSE, primary_admin_key = :primary_key WHERE id = :id"),
                {
                    'id': service_id,
                    'primary_key': primary_key
                }
            )
            send_mail(service['primary_admin_email'], service_name)
            schedule_task(service_id, ALLOWED_RESPONSE_TIME)

def entrypoint(event, _):
    # Decode incoming ID
    if 'data' in event:
        service_id = int(base64.b64decode(event['data']).decode('utf-8'))
    else:
        raise RuntimeError('Service ID missing.')

    # Init connection
    db = init_pool(
        DB_CONN_NAME,
        DB_USERNAME,
        DB_PASSWORD,
        DB_DATABASE
    )

    with db.connect() as conn:
        initialize_db(conn)

        # Fetch service details
        service = conn.execute(
            text("SELECT id, name, url, last_time_responsive, primary_admin_email, secondary_admin_email FROM services WHERE id = :id"),
            { 'id': service_id }
        ).fetchone()

        if not service:
            raise RuntimeError(f'No service with ID {service_id}.')

        url = service['url']
        name = service['name']

        if not service['last_time_responsive']:
            logger.warn(f'Service "{name}" has not been up yet.')
            return

        # Check if service up
        try:
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=(REQUEST_TIMEOUT_SEC, REQUEST_TIMEOUT_SEC),
            )

            if response.status_code < 200 or 300 <= response.status_code:
                logger.info(f'Service "{name}": request to {url} returned HTTP {response.status_code}.')
                handle_service_down(service, conn)
            else:
                handle_service_up(service, conn)

        except requests.exceptions.Timeout:
            logger.info(f'Service "{name}": request to {url} timed out after {REQUEST_TIMEOUT_SEC} s.')
            handle_service_down(service, conn)
