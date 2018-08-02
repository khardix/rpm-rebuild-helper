"""Basic exception sanity tests"""

from rpmrh.exception import UserError


def test_user_error_can_be_raised():
    """UserError can be shown without causing another exception"""

    UserError("Sample message").show()
