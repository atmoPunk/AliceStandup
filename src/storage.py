import functools
import os
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extensions
import psycopg2.pool

from user import User


class StorageConnection(psycopg2.extensions.connection):
    def start_standup(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET standup_held = TRUE WHERE user_id=%s""", (user_id,))

    def modify_silence(self, user_id: str, value: bool):
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET silence_enabled = %s WHERE user_id=%s""", (value, user_id))

    def reset_user(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET standup_held = FALSE, cur_speaker = 0 WHERE user_id=%s""", (user_id,))
        with self.cursor() as cur:
            cur.execute("""UPDATE persons SET last_theme = NULL WHERE standup_organizer = %s""", (user_id,))

    def check_standup(self, user_id: str) -> bool:
        with self.cursor() as cur:
            cur.execute("""SELECT standup_held FROM users WHERE user_id = %s""", (user_id,))
            result = cur.fetchone()
            if not result:
                return False
            return result[0]

    def create_user(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""INSERT INTO users(user_id, standup_held, cur_speaker, silence_enabled) VALUES(%s, False, 0, True)""", (user_id,))

    def get_user(self, user_id: str) -> Optional[User]:
        with self.cursor() as cur:
            cur.execute("""SELECT * FROM users where user_id = %s""", (user_id,))
            result = cur.fetchone()
            if not result:
                return None
            else:
                return User(*result)

    def add_team_member(self, user_id: str, person: Dict[str, str]):
        with self.cursor() as cur:
            if 'last_name' in person:
                cur.execute("""INSERT INTO persons(first_name, last_name, standup_organizer) VALUES (%s, %s, %s)""",
                            (person['first_name'], person['last_name'], user_id))
            else:
                cur.execute("""INSERT INTO persons(first_name, standup_organizer) VALUES (%s, %s)""",
                            (person['first_name'], user_id))

    def del_team_member(self, user_id: str, person: Dict[str, str]):
        with self.cursor() as cur:
            if 'last_name' in person:
                cur.execute("""DELETE FROM persons WHERE (first_name=%s AND last_name=%s AND standup_organizer=%s) RETURNING *""",
                            (person['first_name'], person['last_name'], user_id))
            else:
                cur.execute("""DELETE FROM persons WHERE (first_name=%s AND last_name IS NULL AND standup_organizer=%s) RETURNING *""",
                            (person['first_name'], user_id))
            return cur.fetchone() is not None

    def get_team(self, user_id: str) -> List[Dict[str, str]]:
        with self.cursor() as cur:
            # Здесь порядок не очень важен, поэтому без ORDER BY
            cur.execute(
                """SELECT first_name, last_name FROM persons WHERE standup_organizer=%s""",
                (user_id,))
            persons = cur.fetchall()
            result = []
            for person in persons:
                result.append({'first_name': person[0], 'last_name': person[1] or ''})
            return result

    def get_team_member(self, user_id: str, member_idx: int) -> Dict[str, str]:
        with self.cursor() as cur:
            cur.execute(
                """SELECT first_name, last_name FROM persons WHERE standup_organizer=%s ORDER BY person_id ASC""",
                (user_id,))
            persons = cur.fetchall()
            return {'first_name': persons[member_idx][0], 'last_name': persons[member_idx][1] or ''}

    def call_next_speaker(self, user_id: str) -> Dict[str, str]:
        with self.cursor() as cur:
            cur.execute("""SELECT cur_speaker FROM users where user_id = %s""", (user_id,))
            speaker_num = cur.fetchone()[0]
            # This throws IndexError so we can end the standup
        next_speaker = self.get_team_member(user_id, speaker_num)
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET cur_speaker = cur_speaker + 1 WHERE user_id = %s""", (user_id,))
        return next_speaker

    def set_theme_for_current_speaker(self, user_id: str, theme: str):
        with self.cursor() as cur:
            cur.execute("""SELECT cur_speaker FROM users where user_id = %s""", (user_id,))
            speaker_num = cur.fetchone()[0]
        speaker = self.get_team_member(user_id, speaker_num - 1)
        with self.cursor() as cur:
            if not speaker['last_name']:
                cur.execute("""UPDATE persons SET last_theme = %s WHERE standup_organizer = %s AND first_name = %s AND last_name IS NULL""",
                            (theme, user_id, speaker['first_name']))
            else:
                cur.execute("""UPDATE persons SET last_theme = %s WHERE standup_organizer = %s AND first_name = %s AND last_name = %s""",
                            (theme, user_id, speaker['first_name'], speaker['last_name']))

    def get_team_themes(self, user_id: str) -> List[Dict[str, str]]:
        with self.cursor() as cur:
            cur.execute("""SELECT first_name, last_name, last_theme FROM persons WHERE standup_organizer = %s""",
                        (user_id,))
            themes = cur.fetchall()
            result = []
            for theme in themes:
                result.append({'first_name': theme[0], 'last_name': theme[1], 'theme': theme[2]})
            return result

    def get_github_info(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""SELECT github_login, repo, installation_id FROM users WHERE user_id=%s""", (user_id,))
            data = cur.fetchone()
            return data

    def get_tracker_info(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""SELECT tracker_org, tracker_queue FROM users WHERE user_id=%s""", (user_id,))
            data = cur.fetchone()
            return data

    def register_github(self, user_id: str, name: str, repo: str, installation_id: str):
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET github_login=%s, repo=%s, installation_id=%s WHERE user_id=%s""",
                        (name, repo, installation_id, user_id))

    def register_tracker(self, user_id: str, org: str, queue: str):
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET tracker_org=%s, tracker_queue=%s WHERE user_id=%s""",
                        (org, queue, user_id))

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = super().__exit__(exc_type, exc_val, exc_tb)
        pool().putconn(self)
        return res


@functools.lru_cache
def pool() -> psycopg2.pool.ThreadedConnectionPool:
    return psycopg2.pool.ThreadedConnectionPool(minconn=1,
                                                maxconn=2,
                                                host=os.getenv('PG_HOST'),
                                                user=os.getenv('PG_USER'),
                                                database=os.getenv('PG_DB'),
                                                password=os.getenv('PG_PWD'),
                                                connection_factory=StorageConnection)


class StorageConnectionFactory:
    @staticmethod
    def create_conn() -> StorageConnection:
        return pool().getconn()
