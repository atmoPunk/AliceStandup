import singleton
import pymongo


class Storage(metaclass=singleton.Singleton):
    def __init__(self):
        self.client = pymongo.MongoClient('mongodb://localhost:27017')
        self.db = self.client['alice-standup']
        self.users = self.db['users']

    def create_user(self, user_id):
        self.users.insert_one({'user_id': user_id, 'members': []})

    def check_user_exists(self, user_id):
        return self.users.find_one({'user_id': user_id}) is not None

    def add_team_member(self, user_id, person):
        query = {'user_id': user_id}
        update = {'$push': {'members': person}}
        result = self.users.update_one(query, update)
        if not result.acknowledged or result.modified_count != 1:
            raise RuntimeError(f'could not update {user_id}')

    def get_team(self, user_id):
        query = {'user_id': user_id}
        result = self.users.find_one(query)
        return result['members']

    def get_team_member(self, user_id, member_idx):
        query = {'user_id': user_id}
        result = self.users.find_one(query)
        if member_idx > len(result['members']):
            raise IndexError()
        return result['members'][member_idx]

