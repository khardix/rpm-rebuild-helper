"""rpmrh exception set"""

import click


class UserError(click.ClickException):
    """An error caused by user"""

    #: Leading description text
    lead = "Error"

    def show(self, file=None):
        """Pretty-print the error message."""

        if file is None:
            file = click.get_text_stderr()

        fields = {
            "lead": click.style(self.lead, fg="red"), "message": self.format_message()
        }
        click.echo("{lead}: {message}".format_map(fields), file=file)
