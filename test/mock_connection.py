from typing import Dict, List, Optional


class MockStorage:
    def __init__(self):
        self.storage = {}

    def start_standup(self, user_id: str):
        self.storage[user_id]['standup_held'] = True

    def reset_user(self, user_id: str):
        self.storage[user_id]['standup_held'] = False
        self.storage[user_id]['cur_speaker'] = 0
        for i in range(len(self.storage[user_id]['team'])):
            self.storage[user_id]['team'][i]['theme'] = None

    def check_standup(self, user_id: str) -> bool:
        return self.storage[user_id]['standup_held']

    def create_user(self, user_id: str):
        self.storage[user_id] = {'standup_held': False, 'cur_speaker': 0, 'team': []}

    def check_user_exists(self, user_id: str) -> bool:
        return user_id in self.storage

    def add_team_member(self, user_id: str, person: Dict[str, Optional[str]]):
        person.update({'theme': None})
        self.storage[user_id]['team'].append(person)

    def del_team_member(self, user_id: str, person: Dict[str, str]):
        del_idx = None
        for (idx, p) in enumerate(self.storage[user_id]['team']):
            if p['first_name'] == person['first_name'] and p.get('last_name', '') == person.get('last_name', ''):
                del_idx = idx
                break
        if del_idx is None:
            return False
        del self.storage[user_id]['team'][del_idx]
        return True

    def get_team(self, user_id: str) -> List[Dict[str, str]]:
        return self.storage[user_id]['team']

    def get_team_member(self, user_id: str, member_idx: int) -> Dict[str, str]:
        member = self.storage[user_id]['team'][member_idx]
        member['last_name'] = member.get('last_name', '')
        return member

    def set_theme_for_current_speaker(self, user_id: str, theme: str):
        speaker = self.get_team_member(user_id, self.storage[user_id]['cur_speaker'] - 1)
        for (idx, person) in enumerate(self.storage[user_id]['team']):
            if speaker['first_name'] == person['first_name'] and speaker.get('last_name', '') == person.get('last_name', ''):
                self.storage[user_id]['team'][idx]['theme'] = theme
                break

    def get_team_themes(self, user_id: str) -> List[Dict[str, str]]:
        team = self.storage[user_id]['team']
        for member in team:
            member['last_name'] = member.get('last_name', '')
        return team

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
