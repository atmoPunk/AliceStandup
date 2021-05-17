import logging
import os
import random
import re
from typing import Dict, Any

from requests import HTTPError

from github import GithubTracker
from request import Request
from tracker import YandexTracker, NoTokenException, NoInfoException


class AuthorizationRequest(Exception):
    pass


class DialogHandler:
    tts_end = 'если вы закончили , скажите " у меня всё " , иначе скажите " продолжить " '
    begin_standup_re = re.compile('(начать|начни|проведи) (стендап|стенд ап|standup|stand up)')
    end_standup_re = re.compile('за(кончи|верши)(ть)? (стендап|стенд ап|standup|stand up)')
    greetings = ['Привет', 'Добрый день', 'Здравствуйте']
    close_issue_re = re.compile('закрой (issue|тикет) ([0-9]+) (гитхаб|трекер)')

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory
        self.connection = None
        self.response: Dict[str, Any] = {'end_session': False}
        self.silence_enabled = True

    def returning_greeting(self, user_id: str):
        greeting = random.choice(self.greetings)
        self.response['text'] = greeting + '.'
        if self.connection.check_standup(user_id):
            self.response['text'] += '\nВы остались в состоянии проведения стендапа в прошлый раз. ' \
                                     'Чтобы выйти из этого состояния, скажите "закончить стендап"'

    def remind_team(self, user_id: str):
        team = self.connection.get_team(user_id)
        names = [f'{person["last_name"].capitalize()} {person["first_name"].capitalize()}' for person in team]
        team_names = ', '.join(names)
        self.response['text'] = 'Твоя команда: ' + team_names

    def tts(self) -> str:
        if self.silence_enabled:
            # Звук тишины
            return os.getenv('TTS_FILENAME') + ' ' + self.tts_end
        else:
            return ''

    @staticmethod
    def help_message() -> str:
        return 'Привет. Я могу помочь провести стендап.\n' \
               'Команды доступные в обычном режиме:\n' \
               '"Добавь в команду ИМЯ ФАМИЛИЯ" - так навык может запомнить участников команды.\n' \
               '"Удали из команды ИМЯ ФАМИЛИЯ" - фраза, действие которой противоположно предыдущей.\n' \
               '"Включи/выключи тишину" - выключает или включает проигрывание тишины во время стендапа.\n' \
               '"Напомни команду" - посмотреть текущий состав команды.\n' \
               '"Начни стендап" - Переходит в режим стендапа. Навык начнет по очереди предлагать участникам команды ' \
               'рассказать о своём рабочем дне.\n' \
               '"Помощь продолжение" - для остальных ключевых фраз.\n'

    @staticmethod
    def help_next() -> str:
        return '"Авторизуй трекер" - навык предложит авторизоваться в Яндекс.трекере.\n' \
               '"Запомни гитхаб LOGIN REPO INSTALLATION_ID" - передать навыку необходимую информацию о гитхабе. ' \
               'Подробнее: LINK.\n' \
               '"Запомни трекер ORG_ID QUEUE" - передать навыку необходимую информацию о трекере. ' \
               'Подробнее: LINK.\n' \
               '"Покажи тикеты трекер/гитхаб" - получить информацию об открытых тикетах в заданной системе.\n' \
               '"Закрой тикет НОМЕР трекер/гитхаб" - закрыть тикет с номером НОМЕР в заданной системе.\n' \
               '"Удали команду" - убирает всех людей из команды.\n' \
               '"Помощь стендап" - покажет команды, доступные во время стендапа.'

    @staticmethod
    def standup_help() -> str:
        return 'Режим стендапа:\n' \
               '"У меня всё/я закончил" или другие вариации - завершает выступление текущего человека, очередь переходит к следующему.\n' \
               '"Его/её сегодня нет" - выполняет ту же функцию, что и предыдущая фраза.\n' \
               '"Продолжить" - если включено проигрывание тишины, то навык начнёт проигрывать её ещё раз.\n' \
               '"Завершить стендап" - если возникает необходимость, то можно завершить стендап, не пройдя всю команду.\n' \
               '"Запомни тему ТЕМА" - можно попросить навык запомнить небольшую тему, о которой он напомнит в конце стендапа.'

    def new_user(self, user_id: str):
        self.connection.create_user(user_id)
        self.response['text'] = self.help_message()

    def call_next(self, user_id: str):
        try:
            speaker = self.connection.call_next_speaker(user_id)
            name = speaker['first_name'].capitalize()
            if speaker['last_name'] != '':
                name += ' ' + speaker['last_name'].capitalize()
            text = f'{name}, расскажи о прошедшем дне'
            if 'text' not in self.response:
                self.response['text'] = text
            else:
                self.response['text'] += text
            if 'tts' not in self.response:
                self.response['tts'] = text
            else:
                self.response['tts'] += text
            self.response['tts'] += self.tts()
        except IndexError:
            self.end_standup(user_id)

    def end_standup(self, user_id):
        self.response['text'] = 'Это был последний участник команды'
        themes = self.connection.get_team_themes(user_id)
        theme_list = []
        for theme in themes:
            if theme['theme']:
                name = theme['first_name'].capitalize()
                if theme['last_name'] is not None and theme['last_name'] != '':
                    name += ' ' + theme['last_name'].capitalize()
                theme_list.append(f'у {name} '
                                  f'была тема "{theme["theme"]}"')  # TODO: Исправить падежи
        if theme_list:
            self.response['text'] += '. Сегодня ' + ', '.join(theme_list)
        self.response['text'] += '.\nХорошего вам дня.'
        self.response['end_session'] = True
        if 'tts' in self.response:
            del self.response['tts']
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

    def add_team_member_no_intent(self, req: Request):
        # command should be: Добавь в команду человека с именем ИМЯ и фамилией ФАМИЛИЯ
        split_lastname = req.command().split(' и фамилией ')
        names = {}
        if len(split_lastname) > 1:
            names['last_name'] = split_lastname[1]
        split_name = split_lastname[0].split(' с именем ')
        if len(split_name) != 2:
            self.response['text'] = 'К сожалению я не смогла распознать имя, попробуйте ещё раз'
            return
        names['first_name'] = split_name[1]
        self.connection.add_team_member(req.user_id(), names)
        logging.info('Added %r to %r\'s storage', names, req.user_id())
        self.response['text'] = f'Запомнила человека {names.get("last_name", "").capitalize()} ' \
                                f'{names["first_name"].capitalize()}'

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

    def clean_team(self, user_id: str):
        self.connection.clean_team(user_id)
        self.response['text'] = 'Все люди из команды были удалены'

    def github_auth_help(self):
        self.response['text'] = 'Пожалуйста предоставьте свой логин, название репозитория и installation id.' \
                                ' Это сделать можно воспользовавшись командой ' \
                                '"Запомни гитхаб ЛОГИН РЕПО INSTALLATION_ID"'

    def tracker_auth_help(self):
        self.response['text'] = 'Чтобы авторизоваться в трекере необходимо использовать команду \'авторизуй трекер\'.' \
                                ' Затем при помощи команды \'запомни трекер ORG_ID QUEUE\' надо указать идентификатор ' \
                                'организации и очередь, с которой вы хотите работать'

    def tracker_reg_help(self):
        self.response['text'] = 'При помощи команды \'запомни трекер ORG_ID QUEUE\' надо указать идентификатор ' \
                                'организации и очередь, с которой вы хотите работать'

    def get_tracker_client(self, req: Request):
        org, queue = self.connection.get_tracker_info(req.user_id())
        if 'access_token' not in req._req['session']['user']:
            self.tracker_auth_help()
            raise NoTokenException()
        if org is None or queue is None:
            self.tracker_reg_help()
            raise NoInfoException()
        return YandexTracker(req._req['session']['user']['access_token'], org, queue)

    def list_issues(self, req: Request, tracker: str):
        client = None
        if tracker == 'github':
            username, repo, installation = self.connection.get_github_info(req.user_id())
            if username is None or repo is None or installation is None:
                self.github_auth_help()
                return
            try:
                client = GithubTracker(username, repo, installation)
            except HTTPError as err:
                logging.info(err)
                self.response['text'] = f'Возникла ошибка в авторизации на гитхабе. Возможно это связано с неправильными ' \
                                        f'данными. Проверьте данные и попробуйте ещё раз. Логин: {username}, репозиторий:' \
                                        f' {repo}, Installation_id: {installation}.'

        else:  # tracker == 'tracker'
            try:
                client = self.get_tracker_client(req)
            except (NoTokenException, NoInfoException):
                # message is already written
                return
        try:
            issues = client.list_issues()
            self.response['text'] = ', '.join(issues)
        except HTTPError as err:
            logging.info(err)
            self.response['text'] = f'Возникла ошибка в получении тикетов.'

    def register_github(self, user_id: str, command: str):
        splits = command.split(' ')
        if len(splits) > 5:
            self.response['text'] = 'Неправильный формат'
            return
        name = splits[2]
        repo = splits[3]
        in_id = splits[4]
        self.connection.register_github(user_id, name, repo, in_id)
        self.response['text'] = f'Успешно запомнила: логин "{name}", репозиторий "{repo}" и installation id "{in_id}"'
        self.response['tts'] = 'Успешно запомнила'

    def register_tracker(self, user_id: str, command: str):
        splits = command.split(' ')
        if len(splits) > 4:
            self.response['text'] = 'Неправильный формат. Ожидается "запомни трекер ORG_ID QUEUE"'
            return
        org = splits[2]
        queue = splits[3]
        self.connection.register_tracker(user_id, org, queue)
        self.response['text'] = f'Успешно запомнила: организация "{org}", очередь "{queue}"'
        self.response['tts'] = 'Успешно запомнила'

    def start_standup(self, user_id: str):
        self.response['text'] = 'Хорошо, начинаю.\n'
        self.response['tts'] = 'хорошо , начинаю .'
        self.connection.start_standup(user_id)
        self.call_next(user_id)

    def close_issue(self, req: Request, issue_number: int, tracker: str):
        client = None
        if tracker == 'github':
            username, repo, installation = self.connection.get_github_info(req.user_id())
            if username is None or repo is None or installation is None:
                self.github_auth_help()
                return
            try:
                client = GithubTracker(username, repo, installation)
            except HTTPError as err:
                logging.info(err)
                self.response['text'] = f'Возникла ошибка в авторизации на гитхабе. Возможно это связано с неправильными ' \
                                        f'данными. Проверьте данные и попробуйте ещё раз. Логин: {username}, репозиторий:' \
                                        f' {repo}, Installation_id: {installation}, номер тикета: {issue_number}.'
        else:
            try:
                client = self.get_tracker_client(req)
            except (NoTokenException, NoInfoException):
                # message is already written
                return
        try:
            client.close_issue(issue_number)
            self.response['text'] = 'Тикет успешно закрыт'
        except HTTPError as err:
            logging.info(err)
            self.response['text'] = 'Не удалось закрыть тикет'

    def add_theme(self, req: Request):
        theme = req.command()[13:]
        self.connection.set_theme_for_current_speaker(req.user_id(), theme)
        self.response['text'] = f'Запомнила тему "{theme}"'
        self.response['tts'] = f'запомнила тему {theme} . {self.tts()}'

    def standup_mode(self, req: Request):
        if 'end.report' in req.intents():
            self.call_next(req.user_id())
        elif req.command().startswith('запомни тему '):
            self.add_theme(req)
        elif self.end_standup_re.match(req.command()):
            self.end_standup(req.user_id())
        elif req.command() == 'продолжить':
            self.response['text'] = ' '  # Игнорируем не команды
            self.response['tts'] = self.tts()
        elif 'skip.person' in req.intents():
            self.response['text'] = 'Хорошо, пропускаю.\n'
            self.response['tts'] = 'хорошо , пропускаю .'
            self.call_next(req.user_id())
        else:
            self.response['text'] = 'Не смогла распознать команду. Во время проведения стендапа могу ' \
                                    'распознать следующие команды: "у меня всё", "продолжить", ' \
                                    '"его|её сегодня нет", "запомнить тему ТЕМА", "закончи стендап"'

    def handle_dialog(self, req: Request):
        if not req.is_authorized():  # Не умеем работать с неавторизованными пользователями
            self.response['text'] = 'Привет. К сожалению, я не могу работать с неавторизованными пользователями. ' \
                                    'Пожалуйста, зайдите в свой аккаунт и попробуйте снова'
            self.response['end_session'] = True
            return

        # Этот context manager закоммитит транзакцию и вернет соединение в пул
        with self.connection_factory.create_conn() as connection:
            self.connection = connection
            req.user = self.connection.get_user(req.user_id())
            if not req.user:  # Новый пользователь
                self.new_user(req.user_id())
                return

            self.silence_enabled = req.user.silence_enabled

            if 'account_linking_complete_event' in req._req:
                self.response['text'] = 'Вы успешно авторизованны'
                return

            if req.is_session_new():
                self.returning_greeting(req.user_id())
                return

            if req.command() == 'покажи тикеты гитхаб':
                self.list_issues(req, 'github')
                return

            if req.command() == 'покажи тикеты трекер':
                self.list_issues(req, 'tracker')
                return

            if close_issue_command := self.close_issue_re.match(req.command()):
                self.close_issue(req, int(close_issue_command.group(2)), close_issue_command.group(3))
                return

            if self.connection.check_standup(req.user_id()):  # user_id в текущий момент проводит стендап
                self.standup_mode(req)
                return

            if req.command().startswith('запомни гитхаб'):
                # Original utterance здесь, так как нам нужно именно то,
                # что передали
                self.register_github(req.user_id(), req.original_utterance())
                return

            if req.command().startswith('запомни трекер'):
                self.register_tracker(req.user_id(), req.original_utterance())
                return

            if req.command() == 'авторизуй трекер':
                if 'access_token' in req._req['session']['user']:
                    self.response['text'] = 'Вы уже авторизованны'
                    return
                else:
                    raise AuthorizationRequest()

            if req.command() == 'помощь' or req.command() == 'что ты умеешь':
                self.response['text'] = self.help_message()
                return

            if req.command() == 'помощь продолжение':
                self.response['text'] = self.help_next()
                return

            if req.command() == 'помощь стендап':
                self.response['text'] = self.standup_help()
                return

            if req.command().startswith('добавь в команду человека с именем'):
                self.add_team_member_no_intent(req)
                return

            if req.command() == 'напомни команду':
                self.remind_team(req.user_id())
                return

            if self.begin_standup_re.match(req.command()):
                self.start_standup(req.user_id())
                return

            if req.command() == 'включи тишину':
                self.connection.modify_silence(req.user_id(), True)
                self.response['text'] = 'Тишина включена'
                return
            elif req.command() == 'выключи тишину':
                self.connection.modify_silence(req.user_id(), False)
                self.response['text'] = 'Тишина выключена'
                return

            if req.command() == 'удали команду':
                self.clean_team(req.user_id())
                return

            intents = req.intents()
            if 'team.newmember' in intents:
                self.add_team_member(req.user_id(), intents['team.newmember']['slots']['name']['value'])
                return

            if 'team.delmember' in intents:
                self.del_team_member(req.user_id(), intents['team.delmember']['slots']['name']['value'])
                return

            self.response['text'] = 'Неизвестная команда.'
