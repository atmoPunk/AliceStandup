import psycopg2
import os


def create_conn():
    return psycopg2.connect(host=os.getenv('PG_HOST'),
                            user='postgres',
                            database='postgres',
                            password=os.getenv('PG_PWD'))


def start_standup(conn, user_id):
    cur = conn.cursor()
    cur.execute("""UPDATE users SET standup_held = TRUE WHERE user_id=%s""", user_id)


def check_standup(conn, user_id):
    cur = conn.cursor()
    cur.execute("""SELECT standup_held FROM users WHERE user_id = %s""", user_id)
    result = cur.fetchone()
    return False if result is None else result[0]


def create_user(conn, user_id):
    cur = conn.cursor()
    cur.execute("""INSERT INTO users(user_id, standup_held, cur_speaker) VALUES(%s, False, 0)""", user_id)
    # self.users.insert_one({'user_id': user_id, 'members': []})


def check_user_exists(conn, user_id):
    cur = conn.cursor()
    cur.execute("""SELECT 1 FROM users where user_id = %s""", user_id)
    result = cur.fetchone()
    return result is not None

    # return self.users.find_one({'user_id': user_id}) is not None


def add_team_member(conn, user_id, person):
    cur = conn.cursor()
    if 'last_name' in person:
        cur.execute("""INSERT INTO persons(first_name, last_name) VALUES (%s, %s) RETURNING member_id""",
                    person['first_name'],
                    person['last_name'])
    else:
        cur.execute("""INSERT INTO persons(first_name, last_name) VALUES (%s) RETURNING member_id""", person['first_name'])
    person_id = cur.fetchone()[0]
    cur.execute("""INSERT INTO teams(user_id, person_id) VALUES (%s, %s)""", user_id, person_id)


def get_team(conn, user_id):
    cur = conn.cursor()
    cur.execute(
        """SELECT first_name, last_name FROM persons JOIN teams on teams.person_id = persons.persons_id WHERE user_id=%s""",
        user_id)
    persons = cur.fetchall()
    result = []
    for person in persons:
        result.append({'first_name': person[0], 'last_name': person[1]})
    return result
    #
    # query = {'user_id': user_id}
    # result = self.users.find_one(query)
    # return result['members']


def get_team_member(conn, user_id, member_idx):
    cur = conn.cursor()
    cur.execute(
        """SELECT first_name, last_name FROM persons JOIN teams on teams.person_id = persons.persons_id WHERE user_id=%s""",
        user_id)
    persons = cur.fetchall()
    # result = []
    # for person in persons:
    #     result.append({'first_name': person[0], 'last_name': person[1]})
    return {'first_name': persons[member_idx][0], 'last_name': persons[member_idx][0]}


def call_next_speaker(conn, user_id):
    cur = conn.cursor()
    cur.execute("""SELECT current_speaker FROM users where user_id = %s""", user_id)
    speaker_num = cur.fetchone()
    next_speaker = get_team_member(conn, user_id, speaker_num)
    cur.execute("""UPDATE users SET cur_speaker = cur_speaker + 1 WHERE user_id = %s""", user_id)
    return next_speaker

