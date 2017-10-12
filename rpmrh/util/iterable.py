"""Iteration related utilities"""

from collections import deque
from itertools import islice
from typing import Iterator, Optional


def consume(iterator: Iterator, steps: Optional[int] = None) -> None:
    """Advance the iterator a number of steps.

    Taken from itertools recipe.

    Keyword arguments:
        iterator: The iterator to advance.
        steps: The number of steps to advance.
            If None, consume the iterator entirely.
    """

    if steps is None:  # consume iterator at C speed
        deque(iterator, maxlen=0)

    else:  # advance to empty slice at requested position
        next(islice(iterator, steps, steps), None)
