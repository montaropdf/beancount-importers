# -*- eval: (git-auto-commit-mode 1) -*-
__copyright__ = "Copyright (C) 2018  Roland Everaert"
__license__ = "GNU GPLv2"

from utils.utils import VatBelgiumEnum, PostingPolicyEnum

class HetznerPolicy(utils.utils.Policy):
    """A Policy class to set the rules for producing a transaction from Hetzner Invoice."""
    def __init__(self,
                 posting_policy=PostingPolicyEnum.MULTI,
                 vat_value=VatBelgiumEnum.VAT21):

        self.posting_policy = posting_policy
        self.vat_value = vat_value
        self.validate()

    def validate(self):
        if not isinstance(self.posting_policy, PostingPolicyEnum):
            raise TypeError

        if not isinstance(self.vat_value, VatBelgiumEnum):
            raise TypeError

        
