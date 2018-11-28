# -*- eval: (git-auto-commit-mode 1) -*-
"""Importer for Invoices in CSV format from Hetzner."""
__copyright__ = "Copyright (C) 2018  Roland Everaert"
__license__ = "GNU GPLv2"

import csv
import datetime
import re
import logging
import decimal
from os import path

from beancount.core import data
from beancount.core import account
from beancount.core import amount
from beancount.core import position
from beancount.ingest import importer

from utils import toAmount, VatBelgiumEnum, PostingPolicyEnum
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

        post = data.Posting(account, amount1, None, amount2, "!", None)

        self.logger.debug('Posting to be returned: %s', str(post))
        self.logger.debug("Leaving Function")

        return post

    def __get_transaction(self, meta, date, date_start, date_end, total, srv_id_tag, posting_list=None):
        """Return a transaction object for a server."""
        self.logger.debug("Entering Function")

        vat = ((total / 100) * self.policy.vat_value)
        postings = []
        if posting_list == None:
            postings.append(self.__get_posting(self.account_liability, total))
            postings.append(self.__get_posting(self.account_assets, -total))
        else:
            if self.policy.posting_policy == PostingPolicyEnum.SINGLE_INCLUDE_VAT:
                postings.append(self.__get_posting(self.account_liability, total + vat))
            else:
                postings.append(self.__get_posting(self.account_liability, total))
            postings += posting_list

        if self.policy.posting_policy in [PostingPolicyEnum.MULTI, PostingPolicyEnum.SINGLE]:
            postings.append(self.__get_posting(self.account_assets, -vat))
            
        desc = "Renting of server {} for the period {} to {}".format(srv_id_tag, date_start, date_end)
        txn =  data.Transaction(
            meta, date, self.FLAG, "Hetzner", desc, data.EMPTY_SET, data.EMPTY_SET, posting_list)

        self.logger.debug('Transaction to be recorded: %s', str(txn))
        self.logger.debug("Leaving Function")
        
        return txn

    def identify(self, file):
        # Match if the filename is as downloaded and the header has the unique
        # fields combination we're looking for.

        self.logger.debug("Entering Function")
        self.logger.info("File to analyse: %s", str(file))
        self.logger.debug("Header file: %s", str(file.head()))

        matching_result = ((re.match(r"{}{}".format(self.inputFile.core_filename_regex, self.inputFile.extension_regex), path.basename(file.name))
                            or re.match(r"{}_{}{}{}".format(self.inputFile.date_prefix_regex, self.inputFile.core_filename_regex, self.inputFile.tag_suffix_regex, self.inputFile.extension_regex), path.basename(file.name))))

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

        matching_result = ((re.match(r"{}{}".format(self.inputFile.core_filename_regex, self.inputFile.extension_regex), path.basename(file.name))
                            or re.match(r"{}_{}{}{}".format(self.inputFile.date_prefix_regex, self.inputFile.core_filename_regex, self.inputFile.tag_suffix_regex, self.inputFile.extension_regex), path.basename(file.name))))

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
            
            if srv_id != None:
                servers_txn[srv_id] = {'total': 0, 'txn': []}
            else:
                if re.match('Server #\d{6}', row['description']):
                    srv_id = re.findall('Server #(\d{6})', row['description'])[0]

            if srv_id in servers_txn:
                servers_txn[srv_id]['total'] += (float(row['price_no_vat']) * float(row['qty']))
                if self.policy.posting_policy == PostingPolicyEnum.MULTI:
                    amt = toAmount(-row['price_no_vat'], 'EUR')
                    servers_txn[srv_id]['txn'].append(self.__get_posting(self.account_assets, amt, None))

        for srv_id, postings in servers_txn.items():
            if self.policy.posting_policy == PostingPolicyEnum.SINGLE:
                txn = self.__get_transaction(meta, datetime.now(), row['date_start'], row['date_end'], postings['total'], srv_id)
            else:
                txn = self.__get_transaction(meta, datetime.now(), row['date_start'], row['date_end'], postings['total'], srv_id, postings['txn'])
            
            entries.append(txn)
            

        #     if cur_month == 0:
        #         cur_month = month
        #     if cur_year == 0:
        #         cur_year = year

        #     # If the month or year change, create the transaction for the overtime of the previous month
        #     if cur_month != month or cur_year != year:
        #         meta_w_month['worked_period'] = "{}-{}".format(cur_year, cur_month)

        #         cur_month = month
        #         cur_year = year

        #         txn = self.__txn_overtime(meta_w_month,
        #                                   date,
        #                                   toAmount(units_overtime,
        #                                            self.commodity_overtime))
        #         self.logger.info('Overtime recorded at date: %s', date)

        #         entries.append(txn)
        #         units_overtime = 0
        #         txn = self.__txn_worked_day_in_month(meta_w_month, date,
        #                                              toAmount(workday_counter,
        #                                                       self.commodity_workday))
        #         self.logger.info('Number of worked day recorded at date: %s', workday_counter)

        #         entries.append(txn)
        #         workday_counter = 0
                
        #     dtype = row['DAYTYPE']
        #     dtype2 = row['DAYTYPE2']
        #     dtype3 = row['DAYTYPE3']
        #     dtype4 = row['DAYTYPE4']
            
        #     self.logger.debug('Day of week type: %s', dtype)
        #     self.logger.debug('Work day type 1: %s', dtype2)
        #     self.logger.debug('Work day type 2: %s', dtype3)

        #     # If it is a week-end day or a day for which I was not yet at Smals, skip it.
        #     if dtype in ["WK-PT", "-"]:
        #         self.logger.info('Week-end day detected.')
        #         continue

        #     # If it is a work day, check if some overtime can be added to the overtime account.
        #     if dtype2 == "PRE":
        #         self.logger.info('Work day detected.')

        #         wk_time = self.__str_time_to_minutes(row['TIMESPENT'])
        #         wk_period = self.standard_work_period

        #         self.logger.debug('Worked time: %s', str(wk_time))

        #         if dtype3 in ["CAO", "MAL"]:
        #             wk_period = int(wk_period / 2)
                
        #         # Check if a part of the day was a vacation
        #         if dtype3 == "CAO":
        #             self.logger.info('Half a day was a vacation, record it.')
        #             txn = self.__txn_vacation(meta, date, "Demi-jour de congé",
        #                                       amount.Amount(decimal.Decimal('0.5'),
        #                                                     self.commodity_vacation_day),
        #                                       amount.Amount(decimal.Decimal(wk_period),
        #                                                     self.commodity_overtime))
        #             self.logger.info('Vacation date: %s', date)
        #             entries.append(txn)

        #         self.logger.info('Worked period for the day (in Minutes): %s', str(wk_period))

        #         overtime = wk_time - wk_period
        #         workday_counter += 1
                
        #         self.logger.debug('Overtime for the day: %s', str(overtime))

        #         units_overtime += overtime
        #         self.logger.info('Cumulative overtime for the month: %g', units_overtime)
        #     else:
        #         # If it is a work day, but I was sick or it was a legal holiday, skip it.
        #         if dtype3 in ["JFR", "MAL", "COLFE"] and dtype4 == '':
        #             self.logger.info('Non-worked day detected, skip it.')
        #             continue

        #         # If it is a work day, but I was on vacation, add an entry for a vacation day.
        #         if dtype3 == "CAO":
        #             self.logger.info('Vacation day detected, record it.')
        #             txn = self.__txn_vacation(meta, date, "Congé",
        #                                       amount.Amount(decimal.Decimal('1'),
        #                                                     self.commodity_vacation_day),
        #                                       amount.Amount(decimal.Decimal(self.standard_work_period),
        #                                                     self.commodity_overtime))
        #             self.logger.info('Vacation date: %s', date)
        #             entries.append(txn)
        #         else:
        #             if  dtype4 == "CAO":
        #                 wk_period = int(wk_period / 2)
        #                 txn = self.__txn_vacation(meta, date, "Demi-jour de congé",
        #                                           amount.Amount(decimal.Decimal('0.5'), self.commodity_vacation_day),
        #                                           amount.Amount(decimal.Decimal(wk_period), self.commodity_overtime))
        #                 self.logger.info('Vacation date: %s', date)
        #                 entries.append(txn)
        #             else:
        #                 self.logger.warning("Unknown day type detected, row ignored.")
        #                 self.logger.warning('Data in row: %s', str(row))
        #                 continue

        # # When there is no more row to process, create a transaction with the remaining overtime
        # self.logger.debug('End of file reached. Record remaining overtime and number of worked days.')
        # meta_w_month['worked_period'] = "{}-{}".format(cur_year, cur_month)
        # txn = self.__txn_overtime(meta_w_month,
        #                           date,
        #                           toAmount(units_overtime,
        #                                    self.commodity_overtime))
        # self.logger.info('Overtime recorded at date: %s', date)
        # entries.append(txn)

        # txn = self.__txn_worked_day_in_month(meta_w_month,
        #                                      date,
        #                                      toAmount(workday_counter,
        #                                               self.commodity_workday))
        # self.logger.info('Number of worked days recorded at date: %s', workday_counter)
        # entries.append(txn)

        self.logger.debug("Leaving Function")
        return entries

# def test():
#     # Create an importer instance for running the regression tests.
#     importer = Importer("EXTHR", "VACDAY", "7:36", "My Employer s.a.", "Customer s.a.",
#                         "Income:BE:Customer:HeureSup",
#                         "Assets:BE:Employer",
#                         "Assets:BE:Employer:HeureSup",
#                         "Assets:BE:Employer:JourConge",
#                         "Liability:Conge")
#     # yield from regression.compare_sample_files(importer, __file__)
