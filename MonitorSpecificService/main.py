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
FUNC_TO_MARK_AS_BEING_WORKED_ON = os.getenv('FUNC_TO_MARK_AS_BEING_WORKED_ON')
PROJECT = os.getenv('PROJECT_NAME')

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

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
if FUNC_TO_MARK_AS_BEING_WORKED_ON is None:
    raise RuntimeError('Missing environment variable: FUNC_TO_MARK_AS_BEING_WORKED_ON')
if PROJECT is None:
    raise RuntimeError('Missing environment variable: PROJECT')
if API_KEY is None:
    raise RuntimeError('Missing environment variable: API_KEY')
if API_SECRET is None:
    raise RuntimeError('Missing environment variable: API_SECRET')


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

def get_func_qualified_URL(func_name):
    return "https://" + REGION + "-" + PROJECT + ".cloudfunctions.net/" + func_name

MY_MAIL = "automatedmailer@protonmail.com"
MAILJET = Client(auth=(API_KEY, API_SECRET), version='v3.1')
def send_mail(recipient, service_key, service_name):
    data = {
        "Messages": [
            {
                "From": {
                    "Email": MY_MAIL,
                    "Name": "Alerting platform automatic mailer",
                },
                "To": [{"Email": recipient, "Name": recipient}],
                "Subject": "Warning, service is down",
                "TextPart": "Warning, service {} is down! Click this link to begin working on this issue: {}".format(service_name, get_func_qualified_URL(FUNC_TO_MARK_AS_BEING_WORKED_ON) + "?key=" + service_key),
                "HTMLPart": "",
                "CustomID": "",
            }
        ]
    }
    logger.info('Email sent to primary admin {} regarding {}.'.format(recipient, service_name))
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
    logger.info('Scheduled notifying second admin regarding service nr {}.'.format(service_id))
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
        pool_size=1,
        max_overflow=1,
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
        text("UPDATE services SET last_time_responsive = :datetime, primary_admin_key = NULL WHERE id = :id"),
        {
            'id': service['id'],
            'datetime': datetime.datetime.now()
        }
    )


def handle_service_down(service, conn):
    time_now = datetime.datetime.now()

    if not service['last_time_responsive']:
        logger.warn("Service {} has not been up yet.".format(service['name']))
        since_last_check = ALERTING_WINDOW_SEC + 1
    else:
        since_last_check = (time_now - service['last_time_responsive']).total_seconds()
    
    if since_last_check > ALERTING_WINDOW_SEC:
        if service["primary_admin_key"] == None:
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
            send_mail(service['primary_admin_email'], primary_key, service_name)
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
            text("SELECT id, name, url, last_time_responsive, primary_admin_email, secondary_admin_email, primary_admin_key FROM services WHERE id = :id"),
            { 'id': service_id }
        ).fetchone()

        if not service:
            raise RuntimeError(f'No service with ID {service_id}.')

        url = service['url']
        name = service['name']

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
