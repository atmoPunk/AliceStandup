import unittest
from typing import Dict, Any, Optional

from src.dialog import DialogHandler
from test.mock_connection import MockStorageConnectionFactory


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


class TestDialogHandler(unittest.TestCase):
    def test_new_user(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        request = create_request(user_id, '')  # Первая команда игнорирует высказывание
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        self.assertEqual({'end_session': False, 'text': DialogHandler.help_message()}, handler.response)
        self.assertIn(user_id, factory.storage.storage)

    def test_unknown_command(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        request = create_request(user_id, 'какая-то комманда')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        self.assertEqual({'end_session': False, 'text': 'Неизвестная команда'}, handler.response)

    def test_add_user(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        request = create_request(user_id, 'добавь в команду вову')
        add_name_intent(request, 'вова', None)  # Заменяем парсинг интентов от Яндекса
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        self.assertEqual({'end_session': False, 'text': 'Запомнила человека  Вова'}, handler.response)
        self.assertIn({'first_name': 'вова'}, factory.storage.storage[user_id]['team'])
        request = create_request(user_id, 'добавь в команду Иванова Диму')
        add_name_intent(request, 'дима', 'иванов')  # Заменяем парсинг интентов от Яндекса
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        self.assertEqual({'end_session': False, 'text': 'Запомнила человека Иванов Дима'}, handler.response)
        self.assertIn({'first_name': 'дима', 'last_name': 'иванов'}, factory.storage.storage[user_id]['team'])

    def test_start_standup_empty(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        request = create_request(user_id, 'начни стендап')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        self.assertEqual({'end_session': True, 'text': 'Это был последний участник команды. Завершаю сессию',
                          'tts': 'это был последний учасник команды . завершаю сессию'}, handler.response)

    def test_start_standup(self):
        factory = MockStorageConnectionFactory()
        user_id = '1'
        factory.storage.create_user(user_id)
        factory.storage.add_team_member(user_id, {'first_name': 'вова'})
        factory.storage.add_team_member(user_id, {'first_name': 'дима'})
        request = create_request(user_id, 'начни стендап')
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        self.assertTrue(factory.storage.storage[user_id]['standup_held'])
        self.assertEqual({'end_session': False, 'text': 'Хорошо, начинаю.\nВова, расскажи о прошедшем дне',
                          'tts': 'хорошо , начинаю .вова , расскажи о прошедшем дне  если вы закончили '
                                 ', скажите " у меня всё " , иначе скажите " продолжить " '}, handler.response)
        self.assertEqual(1, factory.storage.storage[user_id]['cur_speaker'])

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
        self.assertEqual({'end_session': False, 'text': ' Дима, расскажи о прошедшем дне',
                          'tts': 'дима , расскажи о прошедшем дне  если вы закончили '
                                 ', скажите " у меня всё " , иначе скажите " продолжить " '}, handler.response)
        self.assertEqual(2, factory.storage.storage[user_id]['cur_speaker'])

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
        self.assertEqual({'end_session': True, 'text': 'Это был последний участник команды. Завершаю сессию',
                          'tts': 'это был последний учасник команды . завершаю сессию'}, handler.response)
        self.assertEqual(0, factory.storage.storage[user_id]['cur_speaker'])
        self.assertFalse(factory.storage.storage[user_id]['standup_held'])

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
        self.assertEqual({'end_session': False, 'text': 'Не смогла удалить  Саша'}, handler.response)
        request = create_request(user_id, 'удали из команды Вову')
        add_del_intent(request, 'вова', None)
        handler = DialogHandler(factory)
        handler.handle_dialog(request)
        self.assertNotIn({'first_name': 'вова'}, factory.storage.storage[user_id]['team'])
        self.assertEqual({'end_session': False, 'text': 'Удалила  Вова из команды'}, handler.response)


if __name__ == '__main__':
    unittest.main()