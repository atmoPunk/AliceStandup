import logging
from collections import namedtuple

from src import storage

Person = namedtuple('Person', ['first_name', 'last_name'])
session_storage = {}


def new_user(connection, user_id, resp):
    resp['text'] = 'Привет. Я могу помочь провести стендап, но для начала мне нужно узнать,' \
                               'участников команды. Для этого можно сказать "Добавь в команду ИМЯ".' \
                               'После того, как все люди будут добавлены - можно будет начинать стендап,' \
                               'командой "Начни стендап".'
    storage.create_user(connection, user_id)


def start_standup(connection, user_id, resp):
    resp['text'] = 'Хорошо, начинаю\n'
    storage.start_standup(connection, user_id)
    call_next(connection, user_id, resp)


def call_next(connection, user_id, resp):
    try:
        speaker = storage.call_next_speaker(connection, user_id)
        if 'text' not in resp:
            resp['text'] = f'{speaker["first_name"].capitalize()}, расскажи о прошедшем дне'
        else:
            resp['text'] += f'{speaker["first_name"].capitalize()}, расскажи о прошедшем дне'
    except IndexError:
        resp['text'] = 'Это был последний участник команды. Завершаю сессию'
        resp['end_session'] = True


def add_team_member(connection, req, resp):
    user_id = req['session']['user']['user_id']
    name_values = req['request']['nlu']['intents']['team.newmember']['slots']['name']['value']
    first_name = name_values.get('first_name', '')
    last_name = name_values.get('last_name', '')
    if not first_name:
        resp['text'] = 'К сожалению я не смогла распонзнать имя, попробуйте ещё раз'
        return
    storage.add_team_member(connection, user_id, {'first_name': first_name, 'last_name': last_name})
    logging.info('Added Person(%r,%r) to %r\'s storage', first_name, last_name, user_id)
    resp['text'] = f'Запомнила человека {last_name.capitalize()} {first_name.capitalize()}'


def handle_dialog(req):
    resp = {'end_session': False}
    if 'user' not in req['session']:  # Не умеем работать с неавторизованными пользователями
        resp['text'] = 'Привет. К сожалению, я не могу работать с неавторизованными пользователями.' \
                                   'Пожалуйста, зайдите в свой аккаунт и попробуйте снова'
        resp['end_session'] = True
        return resp

    user_id = req['session']['user']['user_id']
    with storage.create_conn() as connection:
        if not storage.check_user_exists(connection, user_id):  # Новый пользователь
            new_user(connection, user_id, resp)
            return resp

        if req['session']['new']:
            # if user_id not in session_storage:
            #     session_storage[user_id] = {'current_speaker': 0, 'held_standup': False}
            resp['text'] = 'Привет. Я тебя помню, твоя команда:'
            team = storage.get_team(connection, user_id)
            for (idx, person) in enumerate(team):
                resp['text'] += f' {person["last_name"].capitalize()} {person["first_name"].capitalize()}'
                if idx == len(team):
                    resp['text'] += '.'
                else:
                    resp['text'] += ','
            return resp

        if storage.check_standup(connection, user_id):
            if req['request']['command'] == 'у меня все':
                call_next(user_id, resp)
            else:
                resp['text'] = ' '  # Игнорируем, если кто-то что-то говорит во время стендапа
        else:
            if 'team.newmember' in req['request']['nlu']['intents']:  # Добавление человека в команду
                add_team_member(connection, req, resp)
            elif req['request']['command'] == 'начни стендап':
                start_standup(connection, user_id, resp)
            else:
                resp['text'] = 'Неизвестная команда'
        return resp
