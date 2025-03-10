from logger.logger import logger
from random import choice
import requests
import cfscrape
import time

scraper = cfscrape.create_scraper()
session = requests.Session()

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
]


def scrape(url: str, headers: dict , timeout: int = 10) -> bytes | None:
    try:
        page_start = time.time()
        if headers is None:
            headers = {
                'user-agent': choice(user_agents),
            }

        response = session.get(url, headers=headers, timeout=10)

    except requests.exceptions.HTTPError as errh:
        logger.error(f'{errh}', "Http Error:")
        return None

    if response.status_code != 200:
        logger.error(f'{response.status_code} {response.reason} {url}',
                     "Page fetch failed")
        return None

    logger.info(f'{url} took {time.time() - page_start}',
                "Page fetched successfully")
    return response.content

def fetch_page_sync(url):
    page_start = time.time()
    content = scraper.get(url).content

    logger.info(f'{url} took {time.time() - page_start}',
                "Page fetched successfully")
    return content
