class User:
    def __init__(self, user_id, standup_held, cur_speaker, github_login, repo, installation_id, tracker_org, tracker_queue, silence_enabled):
        self.id = user_id
        self.stanup_held = standup_held
        self.cur_speaker = cur_speaker
        self.github_login = github_login
        self.repo = repo
        self.installation_id = installation_id
        self.tracker_org = tracker_org
        self.tracker_queue = tracker_queue
        self.silence_enabled = silence_enabled
