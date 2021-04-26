from typing import Dict, Any


class Request:
    def __init__(self, req: Dict[str, Any]):
        self._req = req

    def is_session_new(self) -> bool:
        return self._req['session']['new']

    def user_id(self) -> str:
        return self._req['session']['user']['user_id']

    def intents(self) -> Dict[str, Any]:
        return self._req['request']['nlu']['intents']

    def command(self) -> str:
        return self._req['request']['command']

    def original_utterance(self) -> str:
        return self._req['request']['original_utterance']

    def is_authorized(self) -> bool:
        return 'user' in self._req['session']
