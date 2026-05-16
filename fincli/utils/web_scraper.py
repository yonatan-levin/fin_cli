import time
from random import choice

import cfscrape
import requests

from logger.logger import logger

session = requests.Session()
user_agents = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/60.0.3112.113 Safari/537.36"
    ),
]


def scrape(url: str):
    try:
        headers = {
            "user-agent": choice(user_agents),
        }
        response = session.get(url, headers=headers, timeout=10).content
    except requests.exceptions.HTTPError as errh:
        raise Exception("Http Error:", errh) from errh

    return response


def fetch_page_sync(url):
    page_start = time.time()
    scraper = cfscrape.create_scraper()
    content = scraper.get(url).content

    logger.info(f"{url} took {time.time() - page_start}", "Page fetched successfully")
    return content
