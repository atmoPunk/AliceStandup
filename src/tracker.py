import yandex_tracker_client as ytc
from cachetools import TTLCache, cached

from issue_tracker import IssueTracker


class YandexTracker(IssueTracker):
    def __init__(self, token, org_id, queue):
        self.client = get_ytc(token, org_id)
        self.queue = queue

    def list_issues(self):
        return self.client.issues.find(filter={'queue': self.queue})

    def close_issue(self, issue):
        issue = self.client.issues[f'{self.queue}-{issue}']
        transition = issue.transitions['close']
        transition.execute(comment='Закрыто из Алисы')


@cached(TTLCache(maxsize=10, ttl=600))
def get_ytc(token, org_id):
    return ytc.TrackerClient(token=token, org_id=org_id)