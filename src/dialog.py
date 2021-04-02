import logging
import os
import re
from typing import Dict, Any


class DialogHandler:
    tts_end = 'если вы закончили , скажите " у меня всё " , иначе скажите " продолжить " '
    begin_standup_re = re.compile('(начать|начни|проведи) (стендап|стенд ап|standup|stand up)')
    end_standup_re = re.compile('закончи(ть)? (стендап|стенд ап|standup|stand up)')

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory
        self.connection = None
        self.response = {'end_session': False, 'text': ' '}

    def returning_greeting(self, user_id: str):
        greeting = 'Привет. Я тебя помню, твоя команда: '
        team = self.connection.get_team(user_id)
        names = [f'{person["last_name"].capitalize()} {person["first_name"].capitalize()}' for person in team]
        team_names = ', '.join(names)
        self.response['text'] = greeting + team_names + '.'
        if self.connection.check_standup(user_id):
            self.response['text'] += '\nВы остались в состоянии проведения стендапа в прошлый раз. ' \
                                     'Чтобы выйти из этого состояния, скажите "закончить стендап"'

    @staticmethod
    def tts() -> str:
        # Звук тишины
        return os.getenv('TTS_FILENAME')

    @staticmethod
    def help_message() -> str:
        return 'Привет. Я могу помочь провести стендап, но для начала мне нужно узнать ' \
               'участников команды. Для этого можно сказать "Добавь в команду ИМЯ". ' \
               'После того, как все люди будут добавлены - можно будет начинать стендап ' \
               'командами "Начни стендап" или "Проведи стендап". Алиса будет вызывать участников ' \
               'и даст им одну минуту на рассказ, во время которой навык не будет воспринимать команды. ' \
               'По истечении этой минуты (или раннего завершения) можно сказать "у меня всё",' \
               'и тогда Алиса вызовет следующего участника, или сказать "продолжить" для ещё одной минуты.'

    def new_user(self, user_id: str):
        self.connection.create_user(user_id)
        self.response['text'] = self.help_message()

    def call_next(self, user_id: str):
        try:
            speaker = self.connection.call_next_speaker(user_id)
            if 'text' not in self.response:
                self.response['text'] = f'{speaker["first_name"].capitalize()}, расскажи о прошедшем дне'
            else:
                self.response['text'] += f'{speaker["first_name"].capitalize()}, расскажи о прошедшем дне'
            if 'tts' not in self.response:
                self.response['tts'] = f'{speaker["first_name"]} , расскажи о прошедшем дне'
            else:
                self.response['tts'] += f'{speaker["first_name"]} , расскажи о прошедшем дне'
            self.response['tts'] += f' {self.tts() or ""} {self.tts_end}'
        except IndexError:
            self.response['text'] = 'Это был последний участник команды. Завершаю сессию'
            self.response['tts'] = 'это был последний учасник команды . завершаю сессию'
            self.response['end_session'] = True
            self.connection.reset_user(user_id)

    def add_team_member(self, user_id: str, names: Dict[str, str]):
        first_name = names.get('first_name', '')
        last_name = names.get('last_name', '')
        if not first_name:
            self.response['text'] = 'К сожалению я не смогла распознать имя, попробуйте ещё раз'
            return
        self.connection.add_team_member(user_id, names)
        logging.info('Added Person(%r,%r) to %r\'s storage', first_name, last_name, user_id)
        self.response['text'] = f'Запомнила человека {last_name.capitalize()} {first_name.capitalize()}'

    def del_team_member(self, user_id: str, names: Dict[str, str]):
        first_name = names.get('first_name', '')
        last_name = names.get('last_name', '')
        if not first_name:
            self.response['text'] = 'К сожалению я не смогла распознать имя, попробуйте ещё раз'
            return
        if self.connection.del_team_member(user_id, names):
            # TODO: удалить мы можем только по имени, поэтому здесь могут быть проблемы с людьми в одной команде,
            # TODO: у которых совпадают имя и фамилия
            logging.info('Deleted Person(%r,%r) from %r\'s storage', first_name, last_name, user_id)
            self.response['text'] = f'Удалила {last_name.capitalize()} {first_name.capitalize()} из команды'
        else:
            self.response['text'] = f'Не смогла удалить {last_name.capitalize()} {first_name.capitalize()}'

    def start_standup(self, user_id: str):
        self.response['text'] = 'Хорошо, начинаю.\n'
        self.response['tts'] = 'хорошо , начинаю .'
        self.connection.start_standup(user_id)
        self.call_next(user_id)

    def handle_dialog(self, req: Dict[str, Any]):
        if 'user' not in req['session']:  # Не умеем работать с неавторизованными пользователями
            self.response['text'] = 'Привет. К сожалению, я не могу работать с неавторизованными пользователями. ' \
                                    'Пожалуйста, зайдите в свой аккаунт и попробуйте снова'
            self.response['end_session'] = True
            return

        user_id = req['session']['user']['user_id']
        # Этот context manager закоммитит транзакцию и вернет соединение в пул
        with self.connection_factory.create_conn() as connection:
            self.connection = connection
            if not self.connection.check_user_exists(user_id):  # Новый пользователь
                self.new_user(user_id)
                return

            if req['session']['new']:
                self.returning_greeting(user_id)
                return

            if self.connection.check_standup(user_id):  # user_id в текущий момент проводит стендап
                if req['request']['command'] == 'у меня все' or req['request']['command'] == 'у меня всё':
                    self.call_next(user_id)
                elif self.end_standup_re.match(req['request']['command']):
                    self.connection.reset_user(user_id)
                    self.response['text'] = 'Стендап завершен'
                else:  # Тут человек по идее говорит "продолжить", но мы съедаем все слова
                    self.response['text'] = ' '  # Игнорируем не команды
                    self.response['tts'] = f'{self.tts() or ""} + {self.tts_end}'
                return

            if req['request']['command'] == 'помощь':
                self.response['text'] = self.help_message()
                return

            if 'team.newmember' in req['request']['nlu']['intents']:  # Добавление человека в команду
                self.add_team_member(user_id,
                                     req['request']['nlu']['intents']['team.newmember']['slots']['name']['value'])
                return

            if 'team.delmember' in req['request']['nlu']['intents']:
                self.del_team_member(user_id,
                                     req['request']['nlu']['intents']['team.delmember']['slots']['name']['value'])
                return

            if self.begin_standup_re.match(req['request']['command']):
                self.start_standup(user_id)
                return

            self.response['text'] = 'Неизвестная команда'
