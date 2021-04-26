import logging
import os
import random
import re
from typing import Dict, Any

from requests import HTTPError

from github import list_issues, close_issue
from request import Request


class DialogHandler:
    tts_end = 'если вы закончили , скажите " у меня всё " , иначе скажите " продолжить " '
    begin_standup_re = re.compile('(начать|начни|проведи) (стендап|стенд ап|standup|stand up)')
    end_standup_re = re.compile('за(кончи|верши)(ть)? (стендап|стенд ап|standup|stand up)')
    skip_person_re = re.compile('е(го|ё) (сегодня|сейчас)? (нет|не будет)')
    greetings = ['Привет', 'Добрый день', 'Здравствуйте']
    close_issue_re = re.compile('закрой (issue|тикет) ([0-9]+)')

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory
        self.connection = None
        self.response: Dict[str, Any] = {'end_session': False}

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

    @staticmethod
    def tts() -> str:
        # Звук тишины
        return os.getenv('TTS_FILENAME')

    @staticmethod
    def help_message() -> str:
        return 'Привет. Я могу помочь провести стендап, но для начала мне нужно узнать ' \
               'участников команды. Для этого можно сказать "Добавь в команду ИМЯ". ' \
               'Если не получается распознать имя, то можно воспользоваться командой' \
               '"Добавь в команду человека с именем ИМЯ [и фамилией ФАМИЛИЯ]", но в ней нужно следить за падежами' \
               'Чтобы посмотреть текущий состав команды можно сказать "Напомни команду"' \
               'После того, как все люди будут добавлены - можно будет начинать стендап ' \
               'командами "Начни стендап" или "Проведи стендап". Алиса будет вызывать участников ' \
               'и даст им две минуты на рассказ, во время которой навык не будет воспринимать команды. ' \
               'По истечении этого времени (или раннего завершения) можно сказать "у меня всё",' \
               'и тогда Алиса вызовет следующего участника, или сказать "продолжить" для дополнительного времени.' \
               'Так же в этот момент можно сказать "запомни тему ТЕМА". Темы будут повторены по окончанию стендапа' \
               'Если участник команды отсутствует, то его можно пропустить при помощи "его сегодня нет"' \
               'или "её сегодня нет"'

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
            self.response['tts'] += f' {self.tts() or ""} {self.tts_end}'
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

    def github_auth_help(self):
        self.response['text'] = 'Пожалуйста предоставьте свой логин, название репозитория и installation id.' \
                                ' Это сделать можно воспользовавшись командой ' \
                                '"Запомни гитхаб ЛОГИН РЕПО INSTALLATION_ID"'

    def list_issues(self, user_id: str):
        username, repo, installation = self.connection.get_github_info(user_id)
        if username is None or repo is None or installation is None:
            self.github_auth_help()
            return
        try:
            issues = list_issues(username, repo, installation)
            self.response['text'] = ', '.join(issues)
        except HTTPError as err:
            logging.info(err)
            self.response['text'] = f'Возникла ошибка в получении тикетов. Возможно это связано с неправильными ' \
                                    f'данными. Проверьте данные и попробуйте ещё раз. Логин: {username}, репозиторий:' \
                                    f' {repo}, Installation_id: {installation}.'

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

    def start_standup(self, user_id: str):
        self.response['text'] = 'Хорошо, начинаю.\n'
        self.response['tts'] = 'хорошо , начинаю .'
        self.connection.start_standup(user_id)
        self.call_next(user_id)

    def close_issue(self, user_id: str, issue_number: int):
        username, repo, installation = self.connection.get_github_info(user_id)
        if username is None or repo is None or installation is None:
            self.github_auth_help()
            return
        try:
            close_issue(username, repo, installation, issue_number)
            self.response['text'] = 'Тикет успешно закрыт'
        except HTTPError as err:
            logging.info(err)
            self.response['text'] = f'Возникла ошибка в закрытии тикета. Возможно это связано с неправильными ' \
                                    f'данными. Проверьте данные и попробуйте ещё раз. Логин: {username}, репозиторий:' \
                                    f' {repo}, Installation_id: {installation}, номер тикета: {issue_number}.'

    def add_theme(self, req: Request):
        theme = req.command()[13:]
        self.connection.set_theme_for_current_speaker(req.user_id(), theme)
        self.response['text'] = f'Запомнила тему "{theme}"'
        self.response['tts'] = f'запомнила тему {theme} . {self.tts() or ""} {self.tts_end}'

    def standup_mode(self, req: Request):
        if req.command() == 'у меня все' or req.command() == 'у меня всё':
            self.call_next(req.user_id())
        elif req.command().startswith('запомни тему '):
            self.add_theme(req)
        elif self.end_standup_re.match(req.command()):
            self.end_standup(req.user_id())
        elif req.command() == 'продолжить':
            self.response['text'] = ' '  # Игнорируем не команды
            self.response['tts'] = f'{self.tts() or ""} {self.tts_end}'
        elif self.skip_person_re.match(req.command()):
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
            if not self.connection.check_user_exists(req.user_id()):  # Новый пользователь
                self.new_user(req.user_id())
                return

            if req.is_session_new():
                self.returning_greeting(req.user_id())
                return

            if req.command().startswith('запомни гитхаб'):
                # Original utterance здесь, так как нам нужно именно то,
                # что передали
                self.register_github(req.user_id(), req.original_utterance())
                return

            if req.command() == 'покажи тикеты':
                self.list_issues(req.user_id())
                return

            if close_issue_command := self.close_issue_re.match(req.command()):
                self.close_issue(req.user_id(), int(close_issue_command.group(2)))
                return

            if self.connection.check_standup(req.user_id()):  # user_id в текущий момент проводит стендап
                self.standup_mode(req)
                return

            if req.command() == 'помощь':
                self.response['text'] = self.help_message()
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

            intents = req.intents()
            if 'team.newmember' in intents:
                self.add_team_member(req.user_id(), intents['team.newmember']['slots']['name']['value'])
                return

            if 'team.delmember' in intents:
                self.del_team_member(req.user_id(), intents['team.delmember']['slots']['name']['value'])
                return

            self.response['text'] = 'Неизвестная команда. Если нужна подсказка, то есть команда "помощь"'
