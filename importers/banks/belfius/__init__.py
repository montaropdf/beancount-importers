# -*- eval: (git-auto-commit-mode 1) -*-
"""Importer for Invoices in CSV format from Hetzner."""
__copyright__ = "Copyright (C) 2018  Roland Everaert"
__license__ = "GNU GPLv2"

import csv
import datetime
import re
import logging
from os import path

from beancount.core import data
from beancount.core import account
from beancount.core import amount
from beancount.core import position
from beancount.ingest import importer

from utils.utils import toAmount, VatBelgiumEnum, PostingPolicyEnum

class AccountTransactionCsvFileDefinition():
    """A class that define the input file and provides all the facilities to read it."""
    def __init__(self, logger):
        self.logger = logger

        self.logger.debug("Entering Function")

        # BE27 0639 8251 6873 2018-07-08 14-31-01 2_accounting_bank_belfius_report.csv
        
        self.iso_date_regex = "(\d{4})-(0\d|1[0-2])-([0-2]\d|3[01])"
        self.time_regex = "([01]\d|2[0-4])-([0-5]\d)-([0-5])"
        self.account_regex = "[A-Z][A-Z]\d\d( \d{4}){3}"
        self.core_filename_regex = self.account_regex + " " + self.iso_date_regex + " " + self.time_regex + "[^_]*"
        self.extension_regex = "\.csv"
        self.tag_suffix_regex = "(_.+)*"
        
        self.logger.debug("core_filename_regex: %s", self.core_filename_regex)

        self.csvDialect = csv.excel()
        self.csvDialect.delimiter = ';'
        self.fieldname_list = ['product','description', 'date_start', 'date_end', 'qty', 'unit_price', 'price_no_vat', 'srv_id']
# Compte;Date de comptabilisation;Numéro d'extrait;Numéro de transaction;Compte contrepartie;Nom contrepartie contient;Rue et numéro;Code postal et localité;Transaction;Date valeur;Montant;Devise;BIC;Code pays;Communications
        
        self.logger.info("Object initialisation done.")

    def get_Reader(self, input_filename):
        """Return a csv.DictReader object"""
        self.logger.debug("Entering Function")

        reader = csv.DictReader(open(input_filename), fieldnames=self.fieldname_list, dialect=self.csvDialect)

        self.logger.debug("Leaving Function")

        return reader

    def isAccountFileName(self, filename):
        """Check if the filename have the format of an invoice from Hetzner."""
        self.logger.debug("Entering Function")

        self.logger.debug("Filename to analyse %s", filename)
        
        self.logger.debug("Leaving Function")
        return re.match(r"{}{}{}".format(self.core_filename_regex, self.tag_suffix_regex, self.extension_regex), path.basename(filename))

    def get_DateInFileName(self, filename):
        self.logger.debug("Entering Function")
        self.logger.debug("Filename to analyse %s", filename)

        dateinfile = (re.findall(self.core_filename_regex, filename)[0])[:3]

        self.logger.debug("Date element found %s", dateinfile)
        dateinfile = "-".join(dateinfile)

        self.logger.debug("Date in file %s", dateinfile)
        self.logger.debug("Leaving Function")

        return dateinfile

    def get_SanitizedFileName(self, filename):
        self.logger.debug("Entering Function")
        self.logger.debug("Filename to analyse %s", filename)

        cleanFileName = filename.replace(' ', '-')
        
        self.logger.debug("Leaving Function")

        return cleanFileName

class Importer(importer.ImporterProtocol):
    """An importer for the Timesheet Report CSV files provided by one of my customer."""

    def __init__(self, assets_account_map,
                 incomes_account_map,
                 expenses_account_map,
                 liabilities_account_map):

        self.logger = logging.Logger("belfius", logging.DEBUG)

        fh = logging.FileHandler('belfius-importer.log')
        fmtr = logging.Formatter('%(asctime)s - %(levelname)s - %(lineno)d - %(funcName)s | %(message)s')

        fh.setFormatter(fmtr)
        self.logger.addHandler(fh)

        self.assets_account_map = assets_account_map
        self.incomes_account_map = incomes_account_map
        self.expenses_account_map = expenses_account_map
        self.liabilities_account_map = liabilities_account_map

    def identify(self, file):
        # Match if the filename is as downloaded and the header has the unique
        # fields combination we're looking for.

        self.logger.debug("Entering Function")
        self.logger.info("File to analyse: %s", str(file))
        self.logger.debug("Header file: %s", str(file.head()))

        matching_result = self.inputFile.isTimesheetFileName(file.name)

        if matching_result:
            matching_result = re.match("DATE;DAYTYPE;STD;DAYTYPE2;TIMESPENT;DAYTYPE3;TIMEREC;DAYTYPE4;TIMESPENT2", file.head())

        self.logger.info("Identification result: %s", str(matching_result))
        self.logger.debug("Leaving Function")
        return (matching_result)

    def file_name(self, file):
        self.logger.debug("Entering Function")

        cleanedFilename = self.inputFile.get_SanitizedFileName(path.basename(file.name))
        
        self.logger.info("File name to be used: %s", cleanedFilename)
        self.logger.debug("Leaving Function")

        return cleanedFilename

    def file_account(self, _):
        self.logger.debug("Entering Function")
        self.logger.info("File account: %s", FIXME)
        self.logger.debug("Leaving Function")
        return FIXME

    def file_date(self, file):
        # Extract the statement date from the filename.
        self.logger.debug("Entering Function")

        filedate = None
        if self.inputFile.isTimesheetFileName(file.name):
            filedate = self.inputFile.get_DateInFileName(file.name)

        self.logger.info("File date used: %s", str(filedate))
        self.logger.debug("Leaving Function")
        return filedate

    def extract(self, file):
        # Open the CSV file and create directives.
        self.logger.debug("Entering Function")
        self.logger.info("Extracting transactions from file: %s", str(file))

        entries = []
        index = 0

        for index, row in enumerate(self.inputFile.get_Reader(file.name)):
            self.logger.info("Fields: %s", str(row))
            
