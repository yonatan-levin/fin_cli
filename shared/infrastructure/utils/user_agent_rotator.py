"""
User Agent Rotation Utility.

This module provides functionality to rotate user agents to help avoid detection
and reduce the likelihood of being blocked by financial data APIs.
"""
import random
from typing import List, Optional

# Comprehensive list of realistic user agents for better rotation
USER_AGENTS = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',

    # Chrome on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    # Chrome on Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    # Firefox on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',

    # Firefox on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',

    # Firefox on Linux
    'Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',

    # Safari on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1.2 Safari/605.1.15',

    # Edge on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',

    # Edge on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
]


class UserAgentRotator:
    """
    User agent rotation utility for avoiding detection.

    This class provides methods to get random user agents and manage
    user agent rotation for multiple requests.
    """

    def __init__(self, user_agents: Optional[List[str]] = None):
        """
        Initialize the user agent rotator.

        Args:
            user_agents: Optional list of user agents to use. If None, uses default list.
        """
        self.user_agents = user_agents or USER_AGENTS
        self._last_used_index = -1

    def get_random_user_agent(self) -> str:
        """
        Get a random user agent from the list.

        Returns:
            A random user agent string
        """
        return random.choice(self.user_agents)

    def get_next_user_agent(self) -> str:
        """
        Get the next user agent in rotation.

        This ensures we cycle through all user agents before repeating.

        Returns:
            The next user agent string in the rotation
        """
        self._last_used_index = (
            self._last_used_index + 1) % len(self.user_agents)
        return self.user_agents[self._last_used_index]

    def get_random_headers(self) -> dict:
        """
        Get a random set of headers including user agent.

        Returns:
            Dictionary of headers with random user agent
        """
        return {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

    def get_headers_for_session(self) -> dict:
        """
        Get headers suitable for requests session configuration.

        Returns:
            Dictionary of headers optimized for session use
        """
        return {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }


# Global instance for easy access
_default_rotator = UserAgentRotator()


def get_random_user_agent() -> str:
    """
    Get a random user agent (convenience function).

    Returns:
        A random user agent string
    """
    return _default_rotator.get_random_user_agent()


def get_random_headers() -> dict:
    """
    Get random headers including user agent (convenience function).

    Returns:
        Dictionary of headers with random user agent
    """
    return _default_rotator.get_random_headers()


def create_session_with_rotation():
    """
    Create a requests session with user agent rotation.

    Returns:
        Configured requests session
    """
    import requests

    session = requests.Session()
    session.headers.update(_default_rotator.get_headers_for_session())

    return session
