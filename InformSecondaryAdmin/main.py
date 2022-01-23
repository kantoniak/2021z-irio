import logging
import os
import sqlalchemy
from google.cloud import logging as cloudlogging
from sqlalchemy.sql import text
from mailjet_rest import Client

cloudlogging.Client().setup_logging()
logger = logging.getLogger()

DB_CONN_NAME = os.getenv('DB_CONN_NAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

if DB_CONN_NAME is None:
  raise RuntimeError('Missing environment variable: DB_CONN_NAME')
if DB_USERNAME is None:
  raise RuntimeError('Missing environment variable: DB_USERNAME')
if DB_PASSWORD is None:
  raise RuntimeError('Missing environment variable: DB_PASSWORD')
if DB_DATABASE is None:
  raise RuntimeError('Missing environment variable: DB_DATABASE')
if API_KEY is None:
    raise RuntimeError('Missing environment variable: API_KEY')
if API_SECRET is None:
    raise RuntimeError('Missing environment variable: API_SECRET')

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

MY_MAIL = "automatedmailer@protonmail.com"
MAILJET = Client(auth=(API_KEY, API_SECRET), version='v3.1')
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
    logger.info("Email sent to secondary admin {} about {}.".format(recipient, service_name))
    result = MAILJET.send.create(data=data)
    return result.json()

def entrypoint(request):
    if request == None:
        raise RuntimeError("Request was empty")

    request_json = request.get_json()

    service_id = request_json["service_id"]

    db = init_pool(
        DB_CONN_NAME,
        DB_USERNAME,
        DB_PASSWORD,
        DB_DATABASE
    )

    with db.connect() as conn:
        service = conn.execute(
            text("SELECT being_worked_on, name, secondary_admin_email FROM services WHERE id = :service_id"),
            { 'service_id': service_id }
        ).fetchone()

        if not service:
            raise RuntimeError('No service with such key: ', service_id)

        secondary_admin_email = service["secondary_admin_email"]
        if service["being_worked_on"] == False:
            send_mail(secondary_admin_email, service["name"])
        else:
            logger.info("Primary administrator acknowledged the issue, we don't need to send any more emails.")

    return f'Hello World'