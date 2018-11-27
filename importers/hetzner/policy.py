# -*- eval: (git-auto-commit-mode 1) -*-
__copyright__ = "Copyright (C) 2018  Roland Everaert"
__license__ = "GNU GPLv2"

import utils
from utils import VAT, EnumPosting

class HetznerPolicy(utils.Policy):
    """A Policy class to set the rules for producing a transaction from Hetzner Invoice."""
    def __init__(self,
                 posting_policy=EnumPosting.MULTI,
                 vat_value=VAT.VAT21):

        self.posting_policy = posting_policy
        self.vat_value = vat_value
        self.validate()

    def validate():
        if not isinstance(self.posting_policy, utils.EnumPosting):
            raise TypeError

        if not isinstance(self.vat_value, utils.VAT):
            raise TypeError

        
