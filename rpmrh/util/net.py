"""Utilities for network calls."""
from typing import Optional
from typing import Union

import requests
from requests_file import FileAdapter


def default_requests_session(
    session: Optional[requests.Session] = None
) -> requests.Session:
    """Create a requests.Session with suitable default values.

    This function is intended for use by functions that can utilize
    provided session, but do not require it.

    Example::
        def download(url: str, *, session: Optional[requests.Session] = None):
            # Use provided session if any, or create new session
            session = default_requests_session(session)

    Keyword arguments:
        session: If not None, the session is passed unchanged.
                 If None, create new session.
    """

    if session is not None:
        return session

    session = requests.Session()

    # Add local file adapter
    session.mount("file://", FileAdapter())

    return session


def fetch(
    url: str,
    *,
    encoding: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Union[str, bytes]:
    """Fetch contents of a remote file.

    Keyword arguments:
        url: The URL of the file to retrieve.
        encoding: The file encoding to use.
            If None (default), returns the binary representation of the file.
            If specified, the contents are decoded to string.
        session: The requests.Session to use for downloading.

    Returns:
        The contents of the file.
    """

    session = default_requests_session(session)

    response = session.get(url)
    response.raise_for_status()

    if encoding is None:
        return response.content

    response.encoding = encoding
    return response.text
