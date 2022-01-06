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

if DB_CONN_NAME is None:
  raise RuntimeError('Missing environment variable: DB_CONN_NAME')
if DB_USERNAME is None:
  raise RuntimeError('Missing environment variable: DB_USERNAME')
if DB_PASSWORD is None:
  raise RuntimeError('Missing environment variable: DB_PASSWORD')
if DB_DATABASE is None:
  raise RuntimeError('Missing environment variable: DB_DATABASE')

# TODO : this is a straight-up copy pasta from WorkInProgress.py, there should be a better way to do this
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

# TODO : this is also a copy-pasta
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

def entrypoint(request):
    request_json = request.get_json()
    if request == None:
        raise RuntimeError("Request was empty")

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

    return f'Hello World'