import requests

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
})


def get(url, **kwargs):
    kwargs.setdefault("timeout", 40)
    return _session.get(url, **kwargs)


def post(url, **kwargs):
    kwargs.setdefault("timeout", 40)
    return _session.post(url, **kwargs)


def session():
    return _session
