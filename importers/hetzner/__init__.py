# -*- eval: (git-auto-commit-mode 1) -*-
"""Importer for Invoices in CSV format from Hetzner."""
__copyright__ = "Copyright (C) 2018  Roland Everaert"
__license__ = "GNU GPLv2"

import csv
import datetime
import re
import logging
# import decimal
from os import path

from beancount.core import data
from beancount.core import account
from beancount.core import amount
from beancount.core import position
from beancount.ingest import importer

from utils.utils import toAmount, VatBelgiumEnum, PostingPolicyEnum
from importers.hetzner.policy import HetznerPolicy

class InvoiceCsvFileDefinition():
    """A class that define the input file and provides all the facilities to read it."""
    def __init__(self, logger):
        self.logger = logger

        self.logger.debug("Entering Function")

        self.iso_date_regex = "\d{4}-(0\d|1[0-2])-([0-2]\d|3[01])"
        self.core_filename_regex = "Hetzner-" + self.iso_date_regex + "-R\d{10}"
        self.extension_regex = "\.csv"
        self.date_prefix_regex = self.iso_date_regex
        self.tag_suffix_regex = "(_.+)*"

        self.logger.debug("core_filename_regex: %s", self.core_filename_regex)

        self.csvDialect = csv.excel()
        self.csvDialect.delimiter = ','
        self.fieldname_list = ['product','description', 'date_start', 'date_end', 'qty', 'unit_price', 'price_no_vat', 'srv_id']

        self.logger.info("Object initialisation done.")

    def get_Reader(self, input_filename):
        """Return a csv.DictReader object"""
        self.logger.debug("Entering Function")

        reader = csv.DictReader(open(input_filename), fieldnames=self.fieldname_list, dialect=self.csvDialect)

        self.logger.debug("Leaving Function")

        return reader

    def isInvoiceFileName(self, filename):
        """Check if the filename have the format of an invoice from Hetzner."""

        return ((re.match(r"{}{}".format(self.inputFile.core_filename_regex, self.inputFile.extension_regex), path.basename(file.name))
                            or re.match(r"{}_{}{}{}".format(self.inputFile.date_prefix_regex, self.inputFile.core_filename_regex, self.inputFile.tag_suffix_regex, self.inputFile.extension_regex), path.basename(file.name))))


class Importer(importer.ImporterProtocol):
    """An importer for the Timesheet Report CSV files provided by one of my customer."""

    def __init__(self,
                 account_liability,
                 account_assets,
                 policy):

        self.logger = logging.Logger("hetzner", logging.DEBUG)

        fh = logging.FileHandler('hetzner-importer.log')
        fmtr = logging.Formatter('%(asctime)s - %(levelname)s - %(lineno)d - %(funcName)s | %(message)s')

        fh.setFormatter(fmtr)
        self.logger.addHandler(fh)

        self.account_liability = account_liability
        self.account_assets = account_assets
        self.policy = policy
        self.inputFile = InvoiceCsvFileDefinition(self.logger)
        
        self.logger.info("Logger Initialized")
        self.logger.debug("Input parameters:")
        self.logger.debug("Liability account: %s", self.account_liability)
        self.logger.debug("Assets account: %s", self.account_assets)
        self.logger.debug("Policies: %s", str(self.policy))
        
        self.logger.info("Object initialisation done.")

    def __get_posting(self, account, amount1, amount2=None):
        """Return a posting object."""
        self.logger.debug("Entering Function")

        post = data.Posting(account, amount1, None, amount2, None, None)

        self.logger.debug('Posting to be returned: %s', str(post))
        self.logger.debug("Leaving Function")

        return post

    def __get_transaction(self, meta, date, date_start, date_end, total, srv_id_tag, posting_list=None):
        """Return a transaction object for a server."""
        self.logger.debug("Entering Function")

        self.logger.debug("List of postings: %s", posting_list)

        vat = ((total / 100) * float(self.policy.vat_value))
        postings = []
        total_amount = 0

        if posting_list == None:
            if self.policy.posting_policy == PostingPolicyEnum.SINGLE_NO_VAT:
                total_amount = total
            else:
                total_amount = total + vat
            if self.policy.posting_policy == PostingPolicyEnum.SINGLE_INCLUDE_VAT:
                minus_total_amount = -total_amount
            else:
                minus_total_amount = -total
            total_amount = toAmount("{:.2f}".format(total_amount), 'EUR')
            minus_total_amount = toAmount("{:.2f}".format(minus_total_amount), 'EUR')
            postings.append(self.__get_posting(self.account_liability, total_amount))
            postings.append(self.__get_posting(self.account_assets, minus_total_amount))
            self.logger.debug("Posting list: %s", str(postings))
        else:
            if self.policy.posting_policy == PostingPolicyEnum.MULTI_NO_VAT:
                total_amount = toAmount("{:.2f}".format(total), 'EUR')
            else:
                total_amount = toAmount("{:.2f}".format(total + vat), 'EUR')
            postings.append(self.__get_posting(self.account_liability, total_amount))

            postings += posting_list
            self.logger.debug("Posting list: %s", str(postings))

        if self.policy.posting_policy in [PostingPolicyEnum.MULTI, PostingPolicyEnum.SINGLE]:
            minus_vat = toAmount("{:.2f}".format(-vat), 'EUR')
            postings.append(self.__get_posting(self.account_assets, minus_vat))
            
        desc = "Renting of server {} for the period {} to {}".format(srv_id_tag, date_start, date_end)
        txn =  data.Transaction(
            meta, date, self.FLAG, "Hetzner", desc, data.EMPTY_SET, data.EMPTY_SET, postings)

        self.logger.debug('Transaction to be recorded: %s', str(txn))
        self.logger.debug("Leaving Function")
        
        return txn

    def identify(self, file):
        # Match if the filename is as downloaded and the header has the unique
        # fields combination we're looking for.

        self.logger.debug("Entering Function")
        self.logger.info("File to analyse: %s", str(file))
        self.logger.debug("Header file: %s", str(file.head()))

        # matching_result = ((re.match(r"{}{}".format(self.inputFile.core_filename_regex, self.inputFile.extension_regex), path.basename(file.name))
        #                     or re.match(r"{}_{}{}{}".format(self.inputFile.date_prefix_regex, self.inputFile.core_filename_regex, self.inputFile.tag_suffix_regex, self.inputFile.extension_regex), path.basename(file.name))))

        matching_result = self.inputFile.isInvoiceFileName(file.name)
        self.logger.info("Identification result: %s", str(matching_result))

        if matching_result:
            for index, row in enumerate(self.inputFile.get_Reader(file.name)):
                self.logger.debug("Row content: %s", str(row))
                self.logger.debug("Row length: %d", len(row))
                if len(row) != 8:
                    matching_result = False
                    break

        self.logger.debug("Leaving Function")
        return (matching_result)

    def file_name(self, file):
        self.logger.debug("Entering Function")
        self.logger.info("File name to be used: %s", '{}'.format(path.basename(file.name)))
        self.logger.debug("Leaving Function")
        return '{}'.format(path.basename(file.name))

    def file_account(self, _):
        self.logger.debug("Entering Function")
        self.logger.info("File account: %s", self.account_assets)
        self.logger.debug("Leaving Function")
        return self.account_assets

    def file_date(self, file):
        # Extract the statement date from the filename.
        self.logger.debug("Entering Function")

        if re.match(r"{}{}".format(core_filename_regex, extension_regex), path.basename(file.name)):
            filedate = datetime.datetime.strptime(path.basename(file.name),
                                          'Hetzner-%Y-%m-%d-R[0-9]{10}.csv').date()
        elif re.match(r"{}_{}{}{}".format(date_prefix_regex, core_filename_regex, tag_suffix_regex, extension_regex), path.basename(file.name)):
            filedate = datetime.datetime.strptime(path.basename(file.name),
                                          'Hetzner-%Y-%m-%d-R[0-9]{10}.csv').date()


        self.logger.info("File date used: %s", str(filedate))
        self.logger.debug("Leaving Function")
        return filedate

    def extract(self, file):
        # Open the CSV file and create directives.
        self.logger.debug("Entering Function")
        self.logger.info("Extracting transactions from file: %s", str(file))

        entries = []
        index = 0
        servers_txn = {}

        for index, row in enumerate(self.inputFile.get_Reader(file.name)):
            self.logger.debug('Data in row: %s', str(row))
            meta = data.new_metadata(file.name, index)
            meta['start_period'] = row['date_start']
            meta['end_period'] = row['date_end']
            srv_id = row['srv_id']
            
            if srv_id != None and srv_id != '':
                servers_txn[srv_id] = {'total': 0, 'txn': []}
            else:
                if re.match('Server #\d{6}', row['description']):
                    srv_id = re.findall('Server #(\d{6})', row['description'])[0]

            if srv_id in servers_txn:
                servers_txn[srv_id]['total'] += (float(row['price_no_vat']) * float(row['qty']))
                if self.policy.posting_policy in [PostingPolicyEnum.MULTI, PostingPolicyEnum.MULTI_NO_VAT]:
                    amt = toAmount('-' + row['price_no_vat'], 'EUR')
                    self.logger.debug('Amount: %s', str(amt))
                    servers_txn[srv_id]['txn'].append(self.__get_posting(self.account_assets, amt, None))


        self.logger.debug('Data in servers_txn: %s', str(servers_txn))

        for srv_id, postings in servers_txn.items():
            if self.policy.posting_policy in [PostingPolicyEnum.SINGLE, PostingPolicyEnum.SINGLE_INCLUDE_VAT, PostingPolicyEnum.SINGLE_NO_VAT]:
                txn = self.__get_transaction(meta, datetime.date.today(), row['date_start'], row['date_end'], postings['total'], srv_id)
            else:
                txn = self.__get_transaction(meta, datetime.date.today(), row['date_start'], row['date_end'], postings['total'], srv_id, postings['txn'])
            
            entries.append(txn)
            
        self.logger.debug("Leaving Function")
        return entries
