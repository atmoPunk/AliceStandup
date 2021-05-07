from abc import ABC, abstractmethod


class IssueTracker(ABC):

    @abstractmethod
    def list_issues(self):
        pass

    @abstractmethod
    def close_issue(self, issue):
        pass
