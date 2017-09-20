"""Utilities for logging"""

import logging

import click
from click_log import ColorFormatter


class ClickErrHandler(logging.Handler):
    """Log to stderr using click."""

    def emit(self, record):
        try:
            click.echo(self.format(record), err=True)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def basic_config(logger: logging.Logger) -> logging.Logger:
    """Configure the logger for reporting to stderr using click."""

    handler = ClickErrHandler()
    handler.formatter = ColorFormatter()

    logger.handlers = [handler]

    return handler


def quiet_option(
    logger: logging.Logger,
    *names,
    level_quiet: int = logging.ERROR,
    level_verbose: int = logging.INFO,
    help: str = 'Silence informative output.',
    **kwargs
):
    """Click option for silencing the logging output."""

    if not names:
        names = '--quiet', '-q'

    def decorator(f):
        def set_level(_ctx, _param, quiet):
            """Set logger output level."""

            if quiet:
                logger.setLevel(level_quiet)
            else:
                logger.setLevel(level_verbose)

        option = click.option(
            *names,
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=set_level,
            help=help,
            **kwargs
        )
        return option(f)
    return decorator
