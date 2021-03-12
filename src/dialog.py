import logging
from collections import namedtuple
from storage import storage


Person = namedtuple('Person', ['first_name', 'last_name'])


def new_user(user_id, resp):
    resp['response']['text'] = 'Привет. Я могу помочь провести стендап, но для начала мне нужно узнать,' \
                               'участников команды. Для этого можно сказать "Добавь в команду ИМЯ".' \
                               'После того, как все люди будут добавлены - можно будет начинать стендап,' \
                               'командой "Начни стендап".'
    storage[user_id] = {}
    storage[user_id].setdefault('users', [])
    storage[user_id]['current_speaker'] = -1


def start_standup(user_id, resp):
    resp['response']['text'] = 'Хорошо, начинаю\n'
    storage[user_id]['current_speaker'] = -1
    call_next(user_id, resp)


def call_next(user_id, resp):
    storage[user_id]['current_speaker'] += 1
    cur_speaker_idx = storage[user_id]['current_speaker']
    if cur_speaker_idx == len(storage[user_id]['users']):
        resp['response']['text'] = 'Это был последний участник команды. Завершаю сессию'
        resp['response']['end_session'] = True
        storage[user_id]['current_speaker'] = -1
    else:
        cur_speaker_name = storage[user_id]['users'][cur_speaker_idx]
        if 'text' not in resp['response']:
            resp['response']['text'] = f'{cur_speaker_name.first_name.capitalize()}, расскажи о прошедшем дне'
        else:
            resp['response']['text'] += f'{cur_speaker_name.first_name.capitalize()}, расскажи о прошедшем дне'


def add_team_member(req, resp):
    user_id = req['session']['user']['user_id']
    name_values = req['request']['nlu']['intents']['team.newmember']['slots']['name']['value']
    first_name = name_values.get('first_name', '')
    last_name = name_values.get('last_name', '')
    if not first_name:
        resp['response']['text'] = 'К сожалению я не смогла распонзнать имя, попробуйте ещё раз'
        return
    storage[user_id]['users'].append(Person(first_name, last_name))
    logging.info('Added Person(%r,%r) to %r\'s storage', first_name, last_name, user_id)
    resp['response']['text'] = f'Запомнила человека {last_name.capitalize()} {first_name.capitalize()}'


def handle_dialog(req):
    resp = {'response': {}}
    if 'user' not in req['session']:  # Не умеем работать с неавторизованными пользователями
        resp['response']['text'] = 'Привет. К сожалению, я не могу работать с неавторизованными пользователями.' \
                                   'Пожалуйста, зайдите в свой аккаунт и попробуйте снова'
        resp['response']['end_session'] = True
        return resp

    user_id = req['session']['user']['user_id']
    if user_id not in storage:  # Новый пользователь
        new_user(user_id, resp)
        return resp

    if req['session']['new']:
        resp['response']['text'] = 'Привет. Я тебя помню,' \
                                   'твоя команда:'
        for person in storage[user_id]['users']:
            resp['response']['text'] += f' {person.last_name.capitalize()} {person.first_name.capitalize()}'
            if person == storage[user_id]['users'][-1]:
                resp['response']['text'] += '.'
            else:
                resp['response']['text'] += ','
        return resp

    if req['request']['nlu']['intents'].get('team.newmember', None):  # Добавление человека в команду
        add_team_member(req, resp)
    elif req['request']['command'] == 'начни стендап':  # TODO: don't recognize this if a standup is already happening
        start_standup(user_id, resp)
    elif req['request']['command'] == 'у меня все':  # TODO: don't recognize this if no standup is running
        call_next(user_id, resp)
    else:
        if storage[user_id]['current_speaker'] == -1:
            resp['response']['text'] = 'Неизвестная команда'
        else:
            # Кто-то что-то сказал во время проведения стендапа,
            # а Алиса проигнорировать адресованную ей реплику не может, поэтому тут такой placeholder
            resp['response']['text'] = ' '
    return resp
