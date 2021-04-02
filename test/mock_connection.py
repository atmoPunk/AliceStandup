from typing import Dict, List


class MockStorage:
    def __init__(self):
        self.storage = {}

    def start_standup(self, user_id: str):
        self.storage[user_id]['standup_held'] = True

    def reset_user(self, user_id: str):
        self.storage[user_id]['standup_held'] = False
        self.storage[user_id]['cur_speaker'] = 0

    def check_standup(self, user_id: str) -> bool:
        return self.storage[user_id]['standup_held']

    def create_user(self, user_id: str):
        self.storage[user_id] = {'standup_held': False, 'cur_speaker': 0, 'team': []}

    def check_user_exists(self, user_id: str) -> bool:
        return user_id in self.storage

    def add_team_member(self, user_id: str, person: Dict[str, str]):
        self.storage[user_id]['team'].append(person)

    def del_team_member(self, user_id: str, person: Dict[str, str]):
        if person not in self.storage[user_id]['team']:
            return False
        self.storage[user_id]['team'].remove(person)
        return True

    def get_team(self, user_id: str) -> List[Dict[str, str]]:
        return self.storage[user_id]['team']

    def get_team_member(self, user_id: str, member_idx: int) -> Dict[str, str]:
        return self.storage[user_id]['team'][member_idx]

    def call_next_speaker(self, user_id: str) -> Dict[str, str]:
        speaker = self.get_team_member(user_id, self.storage[user_id]['cur_speaker'])
        self.storage[user_id]['cur_speaker'] += 1
        return speaker

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None


class MockStorageConnectionFactory:
    def __init__(self):
        self.storage = MockStorage()

    def create_conn(self) -> MockStorage:
        return self.storage
