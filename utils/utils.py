# -*- eval: (git-auto-commit-mode 1) -*-
__copyright__ = "Copyright (C) 2018  Roland Everaert"
__license__ = "GNU GPLv2"

from beancount.core import amount
from enum import Enum, IntEnum, unique, auto
import decimal


class Policy:
    """A Generic policy class."""
    def validate(self):
        """A validator of the data held by the object."""
        pass


@unique
class VatBelgiumEnum(IntEnum):
    VAT21 = 21
    VAT6 = 6


@unique
class PostingPolicyEnum(Enum):
    SINGLE = auto()  # One posting per account + one posting for VAT
    MULTI = auto()  # Possibly more than one posting per account + one posting for VAT on the total amount
    SINGLE_INCLUDE_VAT = auto()  # One posting per account with VAT included
    MULTI_NO_VAT = auto()  # Possibly more than one posting per account and no posting for VAT
    SINGLE_NO_VAT = auto()  # One posting per account and no posting for VAT


def toAmount(value, commodity):
    """Convert a python built-in value to an Amount object.

Parameters:
- value, the value to convert to an amount.
- commodity, the commodity (currency/unit) associated to the value."""
    atr = decimal.Decimal(value)
    atr = amount.Amount(atr, commodity)

    return atr
