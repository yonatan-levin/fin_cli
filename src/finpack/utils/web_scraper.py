from __future__ import annotations

from random import choice
import requests

_session = requests.Session()
_user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
]


def fetch_page_sync(url: str) -> bytes:
    headers = {'user-agent': choice(_user_agents)}
    response = _session.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.content
