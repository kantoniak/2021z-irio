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

cloudlogging.Client().setup_logging()
logger = logging.getLogger()

DB_CONN_NAME = os.getenv('DB_CONN_NAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')

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

if REQUEST_TIMEOUT_SEC is None:
  raise RuntimeError('Missing environment variable: REQUEST_TIMEOUT_SEC')
else:
  REQUEST_TIMEOUT_SEC = int(REQUEST_TIMEOUT_SEC)

if ALERTING_WINDOW_SEC is None:
  raise RuntimeError('Missing environment variable: ALERTING_WINDOW_SEC')
else:
  ALERTING_WINDOW_SEC = int(ALERTING_WINDOW_SEC)


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
    "secondary_admin_key" UUID NULL,
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

            primary_key = str(uuid.uuid4())
            secondary_key = str(uuid.uuid4())

            conn.execute(
                text("UPDATE services SET being_worked_on = FALSE, primary_admin_key = :primary_key, secondary_admin_key = :secondary_key WHERE id = :id"),
                {
                    'id': service['id'],
                    'primary_key': primary_key,
                    'secondary_key': secondary_key
                }
            )

            # TODO: Send email to primary admin (service['primary_admin_email'])
            # TODO: Schedule task for secondary admin


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
            text("SELECT id, name, url, last_time_responsive, primary_admin_email FROM services WHERE id = :id"),
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
