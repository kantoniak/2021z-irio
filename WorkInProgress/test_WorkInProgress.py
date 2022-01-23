from unittest.mock import Mock, MagicMock, patch
from main import entrypoint

service = {
    'name': 'interesting service',
    'primary_admin_email': 'email1'
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

request = Mock()
request.args.get.return_value = None


@patch('main.init_pool')
@patch('main.render_response')
def test_entrypoint_no_key(render_response, init_pool):
    entrypoint(request)
    render_response.assert_called_once_with('Key missing or not valid')
    init_pool.assert_not_called()


@patch('main.init_pool')
@patch('main.render_response')
def test_entrypoint_no_uuid_in_key(render_response, init_pool):
    request.args.get.return_value = '123'
    entrypoint(request)
    render_response.assert_called_once_with('Key missing or not valid')
    init_pool.assert_not_called()


@patch('main.init_pool', return_value=db)
@patch('main.initialize_db')
@patch('uuid.UUID')
@patch('main.render_response')
def test_entrypoint_no_service(render_response, uuid, initialize_db, init_pool):
    request.args.get.return_value = '123'
    conn_execute_return.fetchone.return_value = None
    entrypoint(request)
    init_pool.assert_called_once()
    initialize_db.assert_called_once_with(conn)
    render_response.assert_called_once_with('No service with such key')
    conn.execute.assert_called_once()


@patch('main.init_pool', return_value=db)
@patch('main.initialize_db')
@patch('uuid.UUID')
@patch('main.render_response')
def test_entrypoint_correct(render_response, uuid, initialize_db, init_pool):
    request.args.get.return_value = '123'
    conn_execute_return.fetchone.return_value = service
    entrypoint(request)
    init_pool.assert_called_once()
    initialize_db.assert_called_once_with(conn)
    render_response.assert_called_once_with('Downtime acknowledged')


