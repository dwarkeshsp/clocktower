"""Start a free practice game through the public API, then end it. Standard library only."""
import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class CheckFailed(Exception):
    pass


class PlayCheck:
    def __init__(self, base_url, start_timeout=60, cleanup_timeout=30, poll_interval=1):
        self.base_url = base_url.rstrip('/')
        self.start_timeout = start_timeout
        self.cleanup_timeout = cleanup_timeout
        self.poll_interval = poll_interval
        self.table = None
        self.token = None

    def request(self, route, body=None):
        headers = {'Content-Type': 'application/json', 'User-Agent': 'clocktower-play-check'}
        if self.token:
            headers['X-Token'] = self.token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + route, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            # Never print response bodies, headers, or credentials returned by the API.
            raise CheckFailed(f'{req.get_method()} {route}: HTTP {exc.code}') from None
        except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError) as exc:
            raise CheckFailed(f'{req.get_method()} {route}: {type(exc).__name__}') from None
        if not isinstance(result, dict):
            raise CheckFailed(f'{req.get_method()} {route}: expected a JSON object')
        return result

    def api(self, action, body=None):
        return self.request(f'/api/t/{urllib.parse.quote(self.table, safe="")}/{action}', body)

    @staticmethod
    def required(reply, field):
        value = reply.get(field)
        if not isinstance(value, str) or not value:
            raise CheckFailed(f'API response is missing {field}')
        return value

    def start(self):
        created = self.request('/api/new', {})
        self.table = self.required(created, 'table')
        host = self.required(created, 'host_key')
        joined = self.api('join', {'name': 'Hourly health check', 'team': 'good', 'host': host})
        self.token = self.required(joined, 'token')
        self.api('config', {'good_model': 'random', 'evil_model': 'random', 'timer': 60})
        lobby = self.api('lobby')
        config = lobby.get('config') or {}
        if (config.get('good_model') != 'random' or config.get('evil_model') != 'random'
                or 'paid_by' not in lobby or lobby['paid_by'] is not None):
            raise CheckFailed('Practice-bot configuration was not confirmed; refusing to start')
        self.api('start', {})
        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            state = self.api('state?since=0')
            if state.get('error') or state.get('status') != 'playing' or state.get('over'):
                raise CheckFailed('Game failed before reaching a playable turn')
            if (state.get('seated') and (state.get('me') or {}).get('seat')
                    and state.get('events') and (state.get('pending') or {}).get('turn')):
                print('Practice game reached a playable human turn.', flush=True)
                return
            time.sleep(self.poll_interval)
        raise CheckFailed('Timed out waiting for a playable human turn')

    def cleanup(self):
        if not self.table or not self.token:
            return
        deadline = time.monotonic() + self.cleanup_timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                status = self.api('lobby').get('status')
                if status in ('lobby', 'over'):
                    # Keep finished games for normal retention; resetting would orphan their logs.
                    print('Check table has no running game.', flush=True)
                    return
                if status not in ('playing', 'paused'):
                    raise CheckFailed('Unexpected table status during cleanup')
                self.api('end', {})
            except CheckFailed as exc:
                # A start request can time out while the engine is still initializing. End becomes
                # available once initialization finishes; also tolerate transient network failures.
                last_error = exc
            time.sleep(self.poll_interval)
        detail = f' ({last_error})' if last_error else ''
        raise CheckFailed(f'Timed out ending the check game{detail}')

    def run(self):
        failure = None
        try:
            self.start()
        except CheckFailed as exc:
            failure = exc
        finally:
            try:
                self.cleanup()
            except CheckFailed as exc:
                failure = CheckFailed(f'{failure}; cleanup: {exc}') if failure else exc
        if failure:
            raise failure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='Play server origin, e.g. https://play.clocktowerbench.com')
    args = parser.parse_args()
    origin = urllib.parse.urlsplit(args.base_url)
    if (origin.scheme not in ('http', 'https') or not origin.netloc or origin.username or origin.password
            or origin.query or origin.fragment or origin.path not in ('', '/')):
        parser.error('--base-url must be an HTTP(S) origin without credentials')
    try:
        PlayCheck(args.base_url).run()
    except CheckFailed as exc:
        print(f'Play check failed: {exc}', file=sys.stderr)
        return 1
    print('Play check passed.', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
