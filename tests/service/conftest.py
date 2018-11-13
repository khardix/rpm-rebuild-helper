"""Common service test setup"""

# Backward-compatible betamax_session definition
try:
    from betamax.fixtures.pytest import (  # noqa: F401
        betamax_parametrized_recorder as betamax_recorder,
        betamax_parametrized_session as betamax_session,
    )
except ImportError:
    pass
