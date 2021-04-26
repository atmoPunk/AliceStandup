import datetime
import jwt
import os
import logging
import requests
from typing import List
from cachetools import cached, Cache, TTLCache
from cryptography.hazmat.primitives.serialization import load_pem_private_key


@cached(Cache(maxsize=1))
def github_app_key():
    with open(os.getenv('GITHUB_APP_KEY'), 'rb') as keyfile:
        return load_pem_private_key(keyfile.read(), password=None)


@cached(TTLCache(maxsize=1, ttl=600))
def github_jwt() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    delta_before = datetime.timedelta(0, 0, 0, 0, -1, 0, 0)  # 1 minute
    delta_after = datetime.timedelta(0, 0, 0, 0, 10, 0, 0)  # 10 minutes
    key = github_app_key()
    payload = {
        'exp': int((now + delta_after).timestamp()),
        'iat': int((now + delta_before).timestamp()),
        'iss': os.getenv('GITHUB_APP_ID')
    }
    return jwt.encode(payload, key, algorithm='RS256')


@cached(TTLCache(maxsize=10, ttl=600))
def get_installation_token(installation) -> str:
    app_token = github_jwt()
    headers = {'Authorization': f'Bearer {app_token}', 'Accept': 'application/vnd.github.v3+json'}
    response = requests.post(
        f'https://api.github.com/app/installations/{installation}/access_tokens', headers=headers
    )
    response.raise_for_status()
    data = response.json()
    logging.info('response from github: %r', data)
    return data['token']


def list_issues(user: str, repo: str, installation: str) -> List[str]:
    token = get_installation_token(installation)
    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
    response = requests.get(f'https://api.github.com/repos/{user}/{repo}/issues', headers=headers)
    response.raise_for_status()
    data = response.json()
    logging.info('response from github: %r', data)
    titles = [f"{r['number']}. {r['title']}" for r in data if 'pull_request' not in r]
    titles = titles[:10]
    return titles


def close_issue(user: str, repo: str, installation: str, issue_number: int):
    token = get_installation_token(installation)
    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
    params = {'state': 'closed'}
    response = requests.patch(f'https://api.github.com/repos/{user}/{repo}/issues/{issue_number}',
                              headers=headers,
                              json=params)
    response.raise_for_status()
    data = response.json()
    logging.info('response from github: %r', data)
    return

