import base64
from unittest.mock import Mock, MagicMock, patch, ANY
from main import entrypoint
import requests

service = {
    'id': 'id123',
    'name': 'interesting service',
    'url': 'www.google.com',
    'last_time_responsive': 'yesterday',
    'primary_admin_email': 'email1',
    'secondary_admin_email': 'email2',
    'primary_admin_key': 'key123'
}

conn_execute_return = Mock()
conn_execute_return.fetchone.return_value = service

conn = Mock()
conn.execute.return_value = conn_execute_return

with_mock = MagicMock()
with_mock.__enter__.return_value = conn

db = Mock()
db.connect.return_value = with_mock

response = Mock()
response.status_code = 199


@patch('main.handle_service_up')
@patch('main.handle_service_down')
@patch('requests.get', return_value=response)
@patch('main.init_pool', return_value=db)
@patch('main.initialize_db')
def test_entrypoint_199(initialize_db, init_pool, get_request, handle_service_down, handle_service_up):
    entrypoint({'data': base64.b64encode(b'123')}, Mock())
    init_pool.assert_called_once()
    initialize_db.assert_called_once_with(conn)
    get_request.assert_called_once_with(service['url'], allow_redirects=ANY, timeout=ANY)
    handle_service_down.assert_called_once()
    handle_service_up.assert_not_called()

@patch('main.handle_service_up')
@patch('main.handle_service_down')
@patch('requests.get', return_value=response)
@patch('main.init_pool', return_value=db)
@patch('main.initialize_db')
def test_entrypoint_300(initialize_db, init_pool, get_request, handle_service_down, handle_service_up):
    response.status_code = 300
    entrypoint({'data': base64.b64encode(b'123')}, Mock())
    init_pool.assert_called_once()
    initialize_db.assert_called_once_with(conn)
    get_request.assert_called_once_with(service['url'], allow_redirects=ANY, timeout=ANY)
    handle_service_down.assert_called_once()
    handle_service_up.assert_not_called()


@patch('main.handle_service_up')
@patch('main.handle_service_down')
@patch('requests.get', return_value=response)
@patch('main.init_pool', return_value=db)
@patch('main.initialize_db')
def test_entrypoint_200(initialize_db, init_pool, get_request, handle_service_down, handle_service_up):
    response.status_code = 200
    entrypoint({'data': base64.b64encode(b'123')}, Mock())
    init_pool.assert_called_once()
    initialize_db.assert_called_once_with(conn)
    get_request.assert_called_once_with(service['url'], allow_redirects=ANY, timeout=ANY)
    handle_service_down.assert_not_called()
    handle_service_up.assert_called_once()


@patch('main.handle_service_up')
@patch('main.handle_service_down')
@patch('requests.get', return_value=response, side_effect=requests.exceptions.Timeout)
@patch('main.init_pool', return_value=db)
@patch('main.initialize_db')
def test_entrypoint_timeout(initialize_db, init_pool, get_request, handle_service_down, handle_service_up):
    response.status_code = 200
    entrypoint({'data': base64.b64encode(b'123')}, Mock())
    init_pool.assert_called_once()
    initialize_db.assert_called_once_with(conn)
    get_request.assert_called_once_with(service['url'], allow_redirects=ANY, timeout=ANY)
    handle_service_down.assert_called_once()
    handle_service_up.assert_not_called()

