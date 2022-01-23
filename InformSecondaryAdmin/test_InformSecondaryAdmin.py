from unittest.mock import Mock, MagicMock, patch
from main import entrypoint

service = {
    'being_worked_on': False,
    'name': 'interesting service',
    'secondary_admin_email': 'email2',
}
conn_execute_return = Mock()
conn_execute_return.fetchone.return_value = None

conn = Mock()
conn.execute.return_value = conn_execute_return

with_mock = MagicMock()
with_mock.__enter__.return_value = conn

db = Mock()
db.connect.return_value = with_mock

response = Mock()
response.status_code = 199

request = Mock()
request.get_json.return_value = {
    'service_id': '123'
}


def test_entrypoint_no_request():
    try:
        entrypoint(None)
    except RuntimeError as err:
        assert str(err) == "Request was empty"


@patch('main.init_pool', return_value=db)
def test_entrypoint_no_service(init_pool):
    try:
        entrypoint(request)
        init_pool.assert_called_once()
    except RuntimeError as err:
        assert err.args == ('No service with such key: ', '123')


@patch('main.send_mail')
@patch('main.init_pool', return_value=db)
def test_entrypoint_not_being_worked_on(init_pool, send_mail):
    conn_execute_return.fetchone.return_value = service
    entrypoint(request)
    init_pool.assert_called_once()
    send_mail.assert_called_once_with(service['secondary_admin_email'], service['name'])


@patch('main.send_mail')
@patch('main.init_pool', return_value=db)
def test_entrypoint_being_worked_on(init_pool, send_mail):
    conn_execute_return.fetchone.return_value = service
    service['being_worked_on'] = True
    ret = entrypoint(request)
    init_pool.assert_called_once()
    send_mail.assert_not_called()
    assert ret == 'Hello World'
