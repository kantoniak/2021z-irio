import logging
import os
import sqlalchemy
import uuid
from flask import render_template
from google.cloud import logging as cloudlogging
from sqlalchemy.sql import text

cloudlogging.Client().setup_logging()
logger = logging.getLogger()

DB_CONN_NAME = os.getenv('DB_CONN_NAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')

if DB_CONN_NAME is None:
  raise RuntimeError('Missing environment variable: DB_CONN_NAME')
if DB_USERNAME is None:
  raise RuntimeError('Missing environment variable: DB_USERNAME')
if DB_PASSWORD is None:
  raise RuntimeError('Missing environment variable: DB_PASSWORD')
if DB_DATABASE is None:
  raise RuntimeError('Missing environment variable: DB_DATABASE')


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


# FIXME: Move to MonitorAllServices once created
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


def render_response(message):
    return render_template('response.html', message=message)


def entrypoint(request):

    # Validate key
    key = request.args.get("key", default=None)
    if not key:
        return render_response('Key missing or not valid')
    try:
        uuid.UUID(str(key))
    except ValueError:
        return render_response('Key missing or not valid')

    # Init connection
    db = init_pool(
        DB_CONN_NAME,
        DB_USERNAME,
        DB_PASSWORD,
        DB_DATABASE
    )

    with db.connect() as conn:
        initialize_db(conn)

        # Fetch matching service
        service = conn.execute(
            text("SELECT name, primary_admin_email FROM services WHERE primary_admin_key = :key"),
            { 'key': key }
        ).fetchone()
        
        if not service:
            return render_response('No service with such key')

        service_name = service['name']
        admin_email = service['primary_admin_email']
        logging.info(f'Admin {admin_email} acknowledged downtime of service {service_name}')

        # Mark as being worked on
        conn.execute(
            text("UPDATE services SET being_worked_on = TRUE WHERE primary_admin_key = :key"),
            { 'key': key }
        )
        return render_response('Downtime acknowledged')
