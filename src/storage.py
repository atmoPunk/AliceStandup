import os
from typing import Dict, List
import psycopg2
import psycopg2.extensions
import psycopg2.pool
import functools


class StorageConnection(psycopg2.extensions.connection):
    def start_standup(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET standup_held = TRUE WHERE user_id=%s""", (user_id,))

    def reset_user(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""UPDATE users SET standup_held = FALSE, cur_speaker = 0 WHERE user_id=%s""", (user_id,))

    def check_standup(self, user_id: str) -> bool:
        with self.cursor() as cur:
            cur.execute("""SELECT standup_held FROM users WHERE user_id = %s""", (user_id,))
            result = cur.fetchone()
            if not result:
                return False
            return result[0]

    def create_user(self, user_id: str):
        with self.cursor() as cur:
            cur.execute("""INSERT INTO users(user_id, standup_held, cur_speaker) VALUES(%s, False, 0)""", (user_id,))

    def check_user_exists(self, user_id: str) -> bool:
        with self.cursor() as cur:
            cur.execute("""SELECT 1 FROM users where user_id = %s""", (user_id,))
            result = cur.fetchone()
            return result is not None

    def add_team_member(self, user_id: str, person: Dict[str, str]):
        with self.cursor() as cur:
            if 'last_name' in person:
                cur.execute("""INSERT INTO persons(first_name, last_name, standup_organizer) VALUES (%s, %s, %s)""",
                            (person['first_name'], person['last_name'], user_id))
            else:
                cur.execute("""INSERT INTO persons(first_name, standup_organizer) VALUES (%s, %s)""",
                            (person['first_name'], user_id))

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

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = super(StorageConnection, self).__exit__(exc_type, exc_val, exc_tb)
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
