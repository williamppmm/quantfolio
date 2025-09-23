class PortfolioAlreadyExistsError(Exception):
    """Raised when attempting to create a portfolio with an existing name."""


class PortfolioNotFoundError(Exception):
    """Raised when a portfolio cannot be located."""


class TransactionNotFoundError(Exception):
    """Raised when a transaction cannot be located."""


class InvalidTransactionError(Exception):
    """Raised when a transaction payload violates business rules."""
