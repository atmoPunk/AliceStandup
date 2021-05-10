from typing import Dict, Any, Optional

from mock_connection import MockStorageConnectionFactory
from dialog import DialogHandler
from request import Request


def create_request(user_id: str, command: str, new: bool = False) -> Request:
    return Request({'session': {'user': {'user_id': user_id}, 'new': new},
                    'request': {'command': command, 'nlu': {'intents': {}}}})


def add_name_intent(request: Request, first_name: str, last_name: Optional[str]):
    if last_name:
        request._req['request']['nlu']['intents']['team.newmember'] = {
                'slots': {'name': {'value': {'first_name': first_name, 'last_name': last_name}}}}
    else:
        request._req['request']['nlu']['intents']['team.newmember'] = {
            'slots': {'name': {'value': {'first_name': first_name}}}}


def add_del_intent(request: Request, first_name: str, last_name: Optional[str]):
    if last_name:
        request._req['request']['nlu']['intents']['team.delmember'] = {
            'slots': {'name': {'value': {'first_name': first_name, 'last_name': last_name}}}}
    else:
        request._req['request']['nlu']['intents']['team.delmember'] = {
            'slots': {'name': {'value': {'first_name': first_name}}}}


class TestDialogHandler:
    def test_pass(self):
        assert True
