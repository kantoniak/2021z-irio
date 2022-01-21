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
from google.cloud import tasks_v2
from google.cloud import pubsub_v1
import json

cloudlogging.Client().setup_logging()
logger = logging.getLogger()

DB_CONN_NAME = os.getenv('DB_CONN_NAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')
QUEUE_NAME = os.getenv('QUEUE_NAME')
REGION = os.getenv('REGION')
PROJECT = os.getenv('PROJECT_NAME')
PUBSUB_TOPIC = os.getenv('PUBSUB_TOPIC')

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
if PROJECT is None:
    raise RuntimeError('Missing environment variable: PROJECT')


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


def initialize_task_queue():
    # https://cloud.google.com/tasks/docs/samples/cloud-tasks-create-queue#cloud_tasks_create_queue-python
    client = tasks_v2.CloudTasksClient()

    # Construct the fully qualified location path.
    parent = f"projects/{PROJECT}/locations/{REGION}"

    all_queues = client.list_queues(request={"parent": parent})
    for queue in all_queues:
        if queue.name.split("/")[-1] == QUEUE_NAME:
            return None

    # Construct the create queue request.
    queue = {"name": client.queue_path(PROJECT, REGION, QUEUE_NAME)}
    # Use the client to create the queue.
    response = client.create_queue(request={"parent": parent, "queue": queue})

    return response


def handle_service(service_id, publisher, topic_name):
    message = str(service_id).encode('utf-8')
    future = publisher.publish(topic_name, message)


def entrypoint(event, _):
    initialize_task_queue()

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
        services = conn.execute(
            text("SELECT id FROM services")
        ).fetchall()

        publisher = pubsub_v1.PublisherClient()
        topic_name = 'projects/{project_id}/topics/{topic}'.format(
            project_id=PROJECT,
            topic=PUBSUB_TOPIC,
        )

        for service in services:
            service_id = service['id']
            handle_service(service_id, publisher, topic_name)
