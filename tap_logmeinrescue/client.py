import time
import requests
import singer

from tap_framework.client import BaseClient


LOGGER = singer.get_logger()


class LogMeInRescueClient(BaseClient):

    def __init__(self, config):
        super().__init__(config)

        self.cookie = None
        self.user_agent = self.config.get('user_agent')

    def get_headers(self):
        if self.user_agent:
            return {
                'User-Agent': self.user_agent
            }

        return {}

    def make_request(self, url, method, base_backoff=15,
                     params=None):
        self.login()
        backoff = False

        LOGGER.info("Making {} request to {}".format(method, url))

        with singer.metrics.Timer('request_duration', {}) as timer:
            response = requests.request(
                method,
                url,
                headers=self.get_headers(),
                cookies={
                    'ASP.NET_SessionId': self.cookie
                },
                params=params)

            if response.status_code == 429:
                if base_backoff > 120:
                    raise RuntimeError('Backed off too many times, exiting!')

                backoff = True
                timer.status = 'failed'

            if response.status_code != 200:
                raise RuntimeError(response.text)

        if backoff:
            LOGGER.warn('Got a 429, sleeping for {} seconds and trying again'
                        .format(base_backoff))

            time.sleep(base_backoff)

            return self.make_request(url, method, base_backoff * 2, params)

        return response.text

    def login(self):
        if self.cookie is not None:
            return

        url = 'https://secure.logmeinrescue.com/API/login.aspx'

        params = {
            'email': self.config.get('username'),
            'pwd': self.config.get('password')
        }

        LOGGER.info("Making GET request to {}".format(url))

        response = requests.get(
            url,
            headers=self.get_headers(),
            params=params
        )

        if 'OK' in response.text:
            self.cookie = response.cookies.get('ASP.NET_SessionId')

        if self.cookie is None or 'INVALID' in response.text:
            raise RuntimeError(
                'Failed to login! Please double check '
                'the provided credentials and try again.')
