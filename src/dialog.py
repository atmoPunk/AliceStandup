import logging
from collections import namedtuple
from storage import storage


Person = namedtuple('Person', ['first_name', 'last_name'])


def new_user(user_id, resp):
    resp['text'] = 'Привет. Я могу помочь провести стендап, но для начала мне нужно узнать,' \
                               'участников команды. Для этого можно сказать "Добавь в команду ИМЯ".' \
                               'После того, как все люди будут добавлены - можно будет начинать стендап,' \
                               'командой "Начни стендап".'
    storage[user_id] = {}
    storage[user_id].setdefault('users', [])
    storage[user_id]['current_speaker'] = -1
    storage[user_id]['held_standup'] = False


def start_standup(user_id, resp):
    resp['text'] = 'Хорошо, начинаю\n'
    storage[user_id]['current_speaker'] = 0
    storage[user_id]['held_standup'] = True
    call_next(user_id, resp)


def call_next(user_id, resp):
    cur_speaker_idx = storage[user_id]['current_speaker']
    if cur_speaker_idx == len(storage[user_id]['users']):
        resp['text'] = 'Это был последний участник команды. Завершаю сессию'
        resp['end_session'] = True
        storage[user_id]['current_speaker'] = 0
        storage[user_id]['held_standup'] = False
    else:
        cur_speaker_name = storage[user_id]['users'][cur_speaker_idx]
        if 'text' not in resp:
            resp['text'] = f'{cur_speaker_name.first_name.capitalize()}, расскажи о прошедшем дне'
        else:
            resp['text'] += f'{cur_speaker_name.first_name.capitalize()}, расскажи о прошедшем дне'
        storage[user_id]['current_speaker'] += 1


def add_team_member(req, resp):
    user_id = req['session']['user']['user_id']
    name_values = req['request']['nlu']['intents']['team.newmember']['slots']['name']['value']
    first_name = name_values.get('first_name', '')
    last_name = name_values.get('last_name', '')
    if not first_name:
        resp['text'] = 'К сожалению я не смогла распонзнать имя, попробуйте ещё раз'
        return
    storage[user_id]['users'].append(Person(first_name, last_name))
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
    if user_id not in storage:  # Новый пользователь
        new_user(user_id, resp)
        return resp

    if req['session']['new']:
        resp['text'] = 'Привет. Я тебя помню,' \
                                   'твоя команда:'
        for person in storage[user_id]['users']:
            resp['text'] += f' {person.last_name.capitalize()} {person.first_name.capitalize()}'
            if person == storage[user_id]['users'][-1]:
                resp['text'] += '.'
            else:
                resp['text'] += ','
        return resp

    if storage[user_id]['held_standup']:
        if req['request']['command'] == 'у меня все':
            call_next(user_id, resp)
        else:
            resp['text'] = ' '  # Игнорируем, если кто-то что-то говорит во время стендапа
    else:
        if 'team.newmember' in req['request']['nlu']['intents']:  # Добавление человека в команду
            add_team_member(req, resp)
        elif req['request']['command'] == 'начни стендап':
            start_standup(user_id, resp)
        else:
            resp['text'] = 'Неизвестная команда'
    return resp
