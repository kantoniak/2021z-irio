from unittest.mock import Mock, MagicMock, patch, ANY
from main import entrypoint

ids = [{'id': 10}, {'id': 20}, {'id': 34}, {'id': 943}]

conn_execute_return = Mock()
conn_execute_return.fetchall.return_value = ids

conn = Mock()
conn.execute.return_value = conn_execute_return

with_mock = MagicMock()
with_mock.__enter__.return_value = conn

db = Mock()
db.connect.return_value = with_mock

publisher = Mock()


@patch('google.cloud.pubsub_v1.PublisherClient', return_value=publisher)
@patch('main.handle_service')
@patch('main.init_pool', return_value=db)
@patch('main.initialize_task_queue')
def test_entrypoint(init_pool, initialize_task_queue, handle_service, publisher_class):
    entrypoint(Mock(), Mock())
    for id_dict in ids:
        handle_service.assert_any_call(id_dict['id'], publisher, ANY)


@patch('google.cloud.pubsub_v1.PublisherClient', return_value=publisher)
@patch('main.handle_service')
@patch('main.init_pool', return_value=db)
@patch('main.initialize_task_queue')
def test_entrypoint_with_no_services(init_pool, initialize_task_queue, handle_service, publisher_class):
    conn_execute_return.fetchall.return_value = []
    entrypoint(Mock(), Mock())
    handle_service.assert_not_called()
