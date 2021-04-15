from typing import Dict, Any, Optional

from mock_connection import MockStorageConnectionFactory
from src.dialog import DialogHandler


def create_request(user_id: str, command: str, new: bool = False) -> Dict[str, Any]:
    return {'session': {'user': {'user_id': user_id}, 'new': new},
            'request': {'command': command, 'nlu': {'intents': {}}}}


def add_name_intent(request: Dict[str, Any], first_name: str, last_name: Optional[str]):
    if last_name:
        request['request']['nlu']['intents']['team.newmember'] = {
                'slots': {'name': {'value': {'first_name': first_name, 'last_name': last_name}}}}
    else:
        request['request']['nlu']['intents']['team.newmember'] = {
            'slots': {'name': {'value': {'first_name': first_name}}}}


def add_del_intent(request: Dict[str, Any], first_name: str, last_name: Optional[str]):
    if last_name:
        request['request']['nlu']['intents']['team.delmember'] = {
            'slots': {'name': {'value': {'first_name': first_name, 'last_name': last_name}}}}
    else:
        request['request']['nlu']['intents']['team.delmember'] = {
            'slots': {'name': {'value': {'first_name': first_name}}}}


class TestDialogHandler:
    def test_new_user(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        request = create_request(user_id, '')  # Первая команда игнорирует высказывание
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': DialogHandler.help_message()} == handler.response
        assert user_id in factory.storage.storage

    def test_unknown_command(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        request = create_request(user_id, 'какая-то команда')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Неизвестная команда. Если нужна подсказка, '
                                              'то есть команда "помощь"'} == handler.response

    def test_add_user(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        request = create_request(user_id, 'добавь в команду вову')
        add_name_intent(request, 'вова', None)  # Заменяем парсинг интентов от Яндекса
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Запомнила человека  Вова'} == handler.response
        assert {'first_name': 'вова', 'theme': None} in factory.storage.storage[user_id]['team']
        request = create_request(user_id, 'добавь в команду Иванова Диму')
        add_name_intent(request, 'дима', 'иванов')  # Заменяем парсинг интентов от Яндекса
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Запомнила человека Иванов Дима'} == handler.response
        assert {'first_name': 'дима', 'last_name': 'иванов', 'theme': None} in factory.storage.storage[user_id]['team']

    def test_add_user_no_intent(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        request = create_request(user_id, 'добавь в команду человека с именем дима и фамилией иванов')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Запомнила человека Иванов Дима'} == handler.response
        assert {'first_name': 'дима', 'last_name': 'иванов', 'theme': None} in factory.storage.storage[user_id]['team']
        request = create_request(user_id, 'добавь в команду человека с именем вова')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Запомнила человека  Вова'} == handler.response
        assert {'first_name': 'вова', 'theme': None} in factory.storage.storage[user_id]['team']


    def test_start_standup_empty(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        request = create_request(user_id, 'начни стендап')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': True, 'text': 'Это был последний участник команды.\nЗавершаю сессию'} == handler.response

    def test_start_standup(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        factory.storage.add_team_member(user_id, {'first_name': 'вова'})
        factory.storage.add_team_member(user_id, {'first_name': 'дима'})
        request = create_request(user_id, 'начни стендап')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert factory.storage.storage[user_id]['standup_held']
        assert {'end_session': False, 'text': 'Хорошо, начинаю.\nВова, расскажи о прошедшем дне',
                'tts': 'хорошо , начинаю .Вова, расскажи о прошедшем дне  если вы закончили '
                ', скажите " у меня всё " , иначе скажите " продолжить " '} == handler.response
        assert 1 == factory.storage.storage[user_id]['cur_speaker']

    def test_call_next(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        factory.storage.add_team_member(user_id, {'first_name': 'вова'})
        factory.storage.add_team_member(user_id, {'first_name': 'дима', 'last_name': 'Иванов'})
        factory.storage.storage[user_id]['cur_speaker'] = 1
        factory.storage.storage[user_id]['standup_held'] = True
        request = create_request(user_id, 'у меня все')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Дима Иванов, расскажи о прошедшем дне',
                'tts': 'Дима Иванов, расскажи о прошедшем дне  если вы закончили '
                ', скажите " у меня всё " , иначе скажите " продолжить " '} == handler.response
        assert 2 == factory.storage.storage[user_id]['cur_speaker']

    def test_call_next_after_last(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        factory.storage.add_team_member(user_id, {'first_name': 'вова'})
        factory.storage.add_team_member(user_id, {'first_name': 'дима', 'last_name': 'Иванов'})
        factory.storage.storage[user_id]['cur_speaker'] = 2
        factory.storage.storage[user_id]['standup_held'] = True
        request = create_request(user_id, 'у меня все')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': True, 'text': 'Это был последний участник команды.\nЗавершаю сессию'} == handler.response
        assert 0 == factory.storage.storage[user_id]['cur_speaker']
        assert not factory.storage.storage[user_id]['standup_held']

    def test_del_member(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        factory.storage.add_team_member(user_id, {'first_name': 'вова'})
        factory.storage.add_team_member(user_id, {'first_name': 'дима', 'last_name': 'иванов'})
        request = create_request(user_id, 'удали из команды Сашу')
        add_del_intent(request, 'саша', None)
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Не смогла удалить  Саша'} == handler.response
        request = create_request(user_id, 'удали из команды Вову')
        add_del_intent(request, 'вова', None)
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'first_name': 'вова'} not in factory.storage.storage[user_id]['team']
        assert {'end_session': False, 'text': 'Удалила  Вова из команды'} == handler.response

    def test_themes(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        factory.storage.add_team_member(user_id, {'first_name': 'вова'})
        factory.storage.add_team_member(user_id, {'first_name': 'дима', 'last_name': 'иванов'})
        factory.storage.storage[user_id]['standup_held'] = True
        factory.storage.storage[user_id]['cur_speaker'] = 1
        request = create_request(user_id, 'запомни тему чай')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert {'end_session': False, 'text': 'Запомнила тему "чай"'} == handler.response
        assert factory.storage.storage[user_id]['team'][0]['theme'] == 'чай'
        request = create_request(user_id, 'у меня всё')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        request = create_request(user_id, 'запомни тему кофе')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        assert factory.storage.storage[user_id]['team'][1]['theme'] == 'кофе'
        assert {'end_session': False, 'text': 'Запомнила тему "кофе"'} == handler.response
        request = create_request(user_id, 'у меня всё')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        # Reset themes
        assert factory.storage.storage[user_id]['team'][0]['theme'] is None
        assert factory.storage.storage[user_id]['team'][1]['theme'] is None
        assert {'end_session': True, 'text': 'Это был последний участник команды. Сегодня у Вова была тема "чай", '
                                             'у Дима Иванов была тема "кофе".\nЗавершаю сессию'} == handler.response
