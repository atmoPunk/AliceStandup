import os
import psycopg2
import psycopg2.extensions


class StorageConnection(psycopg2.extensions.connection):
    def start_standup(self, user_id: str):
        cursor = self.cursor()
        cursor.execute("""UPDATE users SET standup_held = TRUE WHERE user_id=%s""", (user_id,))

    def reset_user(self, user_id: str):
        cur = self.cursor()
        cur.execute("""UPDATE users SET standup_held = FALSE, cur_speaker = 0 WHERE user_id=%s""", (user_id,))

    def check_standup(self, user_id: str) -> bool:
        cur = self.cursor()
        cur.execute("""SELECT standup_held FROM users WHERE user_id = %s""", (user_id,))
        result = cur.fetchone()
        if not result:
            return False
        return result[0]

    def create_user(self, user_id: str):
        cur = self.cursor()
        cur.execute("""INSERT INTO users(user_id, standup_held, cur_speaker) VALUES(%s, False, 0)""", (user_id,))

    def check_user_exists(self, user_id: str) -> bool:
        cur = self.cursor()
        cur.execute("""SELECT 1 FROM users where user_id = %s""", (user_id,))
        result = cur.fetchone()
        return result is not None

    def add_team_member(self, user_id: str, person: dict[str, str]):
        cur = self.cursor()
        if 'last_name' in person:
            cur.execute("""INSERT INTO persons(first_name, last_name) VALUES (%s, %s) RETURNING person_id""",
                        (person['first_name'],
                         person['last_name']))
        else:
            cur.execute("""INSERT INTO persons(first_name, last_name) VALUES (%s) RETURNING member_id""",
                        (person['first_name'],))
        person_id = cur.fetchone()[0]
        cur.execute("""INSERT INTO teams(user_id, person_id) VALUES (%s, %s)""", (user_id, person_id))

    def get_team(self, user_id: str) -> list[dict[str, str]]:
        cur = self.cursor()
        cur.execute(
            """SELECT first_name, last_name FROM persons JOIN teams on teams.person_id = persons.person_id WHERE user_id=%s""",
            (user_id,))
        persons = cur.fetchall()
        result = []
        for person in persons:
            result.append({'first_name': person[0], 'last_name': person[1]})
        return result

    def get_team_member(self, user_id: str, member_idx: int) -> dict[str, str]:
        cur = self.cursor()
        cur.execute(
            """SELECT first_name, last_name FROM persons JOIN teams on teams.person_id = persons.person_id WHERE user_id=%s""",
            (user_id,))
        persons = cur.fetchall()
        return {'first_name': persons[member_idx][0], 'last_name': persons[member_idx][0]}

    def call_next_speaker(self, user_id: str) -> dict[str, str]:
        cur = self.cursor()
        cur.execute("""SELECT cur_speaker FROM users where user_id = %s""", (user_id,))
        speaker_num = cur.fetchone()[0]
        next_speaker = self.get_team_member(user_id, speaker_num)  # This throws IndexError so we can end the standup
        cur.execute("""UPDATE users SET cur_speaker = cur_speaker + 1 WHERE user_id = %s""", (user_id,))
        return next_speaker


def create_conn() -> StorageConnection:
    return psycopg2.connect(host=os.getenv('PG_HOST'),
                            user=os.getenv('PG_USER'),
                            database=os.getenv('PG_DB'),
                            password=os.getenv('PG_PWD'),
                            connection_factory=StorageConnection)
