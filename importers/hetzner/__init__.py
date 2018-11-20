# -*- eval: (git-auto-commit-mode 1) -*-
"""Importer for Invoices in CSV format from Hetzner."""
__copyright__ = "Copyright (C) 2018  Roland Everaert"
__license__ = "GNU GPLv2"

import csv
import datetime
import re
import pprint
import logging
import decimal
from os import path

from dateutil.parser import parse

from beancount.core.number import D
from beancount.core.number import ZERO
from beancount.core.number import MISSING
from beancount.core import data
from beancount.core import account
from beancount.core import amount
from beancount.core import position
from beancount.core import inventory
from beancount.ingest import importer
from beancount.ingest import regression

class Importer(importer.ImporterProtocol):
    """An importer for the Timesheet Report CSV files provided by one of my customer."""

    def __init__(self,
                 account_liability,
                 account_assets):

        self.logger = logging.Logger("hetzner", logging.DEBUG)

        fh = logging.FileHandler('hetzner-importer.log')
        fmtr = logging.Formatter('%(asctime)s - %(levelname)s - %(lineno)d - %(funcName)s | %(message)s')

        fh.setFormatter(fmtr)
        self.logger.addHandler(fh)

        self.account_liability = account_liability
        self.account_assets = account_assets

        self.logger.info("Logger Initialized")
        self.logger.debug("Input parameters:")
        self.logger.debug("Liabilities account: %s", self.account_liability)
        self.logger.debug("Assets account: %s", self.account_assets)
        
        self.logger.info("Object initialisation done.")
        
    # def __txn_vacation(self, meta, date, desc, units_vac, units_ovt):
    #     """Return a holiday transaction object."""
    #     self.logger.debug("Entering Function")

    #     txn =  data.Transaction(
    #         meta, date, "!", self.employer, desc, data.EMPTY_SET, data.EMPTY_SET, [
    #             data.Posting(self.account_vacation, units_vac, None, None, None, None),
    #             data.Posting(self.account_employer_vacation, -units_vac, None, None, None, None),
    #             data.Posting(self.account_vacation, units_vac, None, units_ovt, "!", None),
    #             data.Posting(self.account_employer_overtime, -units_ovt, None, None, "!", None)
    #             ])

    #     self.logger.debug('Transaction to be recorded: %s', str(txn))
    #     self.logger.debug("Leaving Function")
        
    #     return txn
        
    # def __txn_overtime(self, meta, date, units_ovt):
    #     """Return an overtime transaction object."""
    #     self.logger.debug("Entering Function")

    #     txn =  data.Transaction(
    #         meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
    #             data.Posting(self.account_employer_overtime, units_ovt, None, None, None, None),
    #             data.Posting(self.account_customer_overtime, -units_ovt, None, None, None, None)
    #             ])

    #     self.logger.debug('Transaction to be recorded: %s', str(txn))
    #     self.logger.debug("Leaving Function")
        
    #     return txn

    # def __txn_worked_day_in_month(self, meta, date, units_wk_dt):
    #     """Return an overtime transaction object."""
    #     self.logger.debug("Entering Function")

    #     txn =  data.Transaction(
    #         meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
    #             data.Posting(self.account_employer_worked_day, units_wk_dt, None, None, None, None),
    #             data.Posting(self.account_customer_worked_day, -units_wk_dt, None, None, None, None)
    #             ])

    #     self.logger.debug('Transaction to be recorded: %s', str(txn))
    #     self.logger.debug("Leaving Function")
        
    #     return txn

    def __int_to_Amount(self, value, commodity):
        """Convert a value as a int to an Amount object."""
        self.logger.debug("Entering Function")
        atr = decimal.Decimal(value)
        atr = amount.Amount(atr, commodity)
        self.logger.debug("Amount to return: %s", atr)
        self.logger.debug("Leaving Function")

        return atr

    # def __str_time_to_minutes(self, time_as_str_or_tuple):
    #     """Convert a time period expressed as a string into a number of minutes as an int."""
    #     self.logger.debug("Entering Function")

    #     self.logger.debug("Parameter to transform: '%s'", time_as_str_or_tuple)
    #     self.logger.debug("Parameter type: %s", type(time_as_str_or_tuple))

    #     if type(time_as_str_or_tuple) == str:
    #         self.logger.debug("Is it in [H]H:MM format: %s", re.fullmatch("^[0-9]{1,2}:[0-5][0-9]$", time_as_str_or_tuple))
    #         if re.fullmatch("^[0-9]{1,2}:[0-5][0-9]$", time_as_str_or_tuple) != None:
    #             time_as_tuple = (int(time_as_str_or_tuple.split(':')[0]), int(time_as_str_or_tuple.split(':')[1]))
    #         else:
    #             raise ValueError("Parameter was not a string  of the form [H]H:MM: {}".format(time_as_str_or_tuple))
    #     elif type(time_as_str_or_tuple) == tuple and len(time_as_str_or_tuple) == 2 and type(time_as_str_or_tuple[0]) == int and type(time_as_str_or_tuple[1]):
    #         time_as_tuple = time_as_str_or_tuple
    #     else:
    #         raise ValueError("Parameter was not a string or a tuple of 2 elements")

    #     return (time_as_tuple[0] * 60) + time_as_tuple[1]
    
    def identify(self, file):
        # Match if the filename is as downloaded and the header has the unique
        # fields combination we're looking for.

        self.logger.debug("Entering Function")
        self.logger.info("File to analyse: %s", str(file))
        self.logger.debug("Header file: %s", str(file.head()))

        core_filename_regex = "Hetzner-\d\d\d\d-\d\d-\d\d-R\d\d\d\d\d\d\d\d\d\d"
        extension_regex = "\.csv"
        date_prefix_regex = "\d\d\d\d-\d\d-\d\d"
        tag_suffix_regex = "(_.+)*"

        matching_result = ((re.match(r"{}{}".format(core_filename_regex, extension_regex), path.basename(file.name))
                            or re.match(r"{}_{}{}{}".format(date_prefix_regex, core_filename_regex, tag_suffix_regex, extension_regex), path.basename(file.name))))

        self.logger.info("Identification result: %s", str(matching_result))

        if matching_result:
            csvDialect = csv.excel();
            csvDialect.delimiter = ','

            for index, row in enumerate(csv.DictReader(open(file.name), dialect=csvDialect)):
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

        core_filename_regex = "Hetzner-\d\d\d\d-\d\d-\d\d-R\d{10}"
        extension_regex = "\.csv"
        date_prefix_regex = "\d\d\d\d-\d\d-\d\d"
        tag_suffix_regex = "(_.+)*"

        if re.match(r"{}{}".format(core_filename_regex, extension_regex), path.basename(file.name)):
            filedate = datetime.datetime.strptime(path.basename(file.name),
                                          'Hetzner-%Y-%m-%d-R[0-9]{10}.csv').date()
        elif re.match(r"{}_{}{}{}".format(date_prefix_regex, core_filename_regex, tag_suffix_regex, extension_regex), path.basename(file.name)):
            filedate = datetime.datetime.strptime(path.basename(file.name),
                                          'Hetzner-%Y-%m-%d-R[0-9]{10}.csv').date()
            self.logger.debug("Year: %s", year)
            self.logger.debug("Current Year: %s", cur_year)
            self.logger.debug("Month: %s", month)
            self.logger.debug("Current Month: %s", cur_month)

            if cur_month == 0:
                cur_month = month
            if cur_year == 0:
                cur_year = year

            # If the month or year change, create the transaction for the overtime of the previous month
            if cur_month != month or cur_year != year:
                meta_w_month['worked_period'] = "{}-{}".format(cur_year, cur_month)

                cur_month = month
                cur_year = year

                txn = self.__txn_overtime(meta_w_month,
                                          date,
                                          self.__int_to_Amount(units_overtime,
                                                               self.commodity_overtime))
                self.logger.info('Overtime recorded at date: %s', date)

                entries.append(txn)
                units_overtime = 0
                txn = self.__txn_worked_day_in_month(meta_w_month, date,
                                                     self.__int_to_Amount(workday_counter,
                                                                          self.commodity_workday))
                self.logger.info('Number of worked day recorded at date: %s', workday_counter)

                entries.append(txn)
                workday_counter = 0
                
            dtype = row['DAYTYPE']
            dtype2 = row['DAYTYPE2']
            dtype3 = row['DAYTYPE3']
            dtype4 = row['DAYTYPE4']
            
            self.logger.debug('Day of week type: %s', dtype)
            self.logger.debug('Work day type 1: %s', dtype2)
            self.logger.debug('Work day type 2: %s', dtype3)

            # If it is a week-end day or a day for which I was not yet at Smals, skip it.
            if dtype in ["WK-PT", "-"]:
                self.logger.info('Week-end day detected.')
                continue

            # If it is a work day, check if some overtime can be added to the overtime account.
            if dtype2 == "PRE":
                self.logger.info('Work day detected.')

                wk_time = self.__str_time_to_minutes(row['TIMESPENT'])
                wk_period = self.standard_work_period

                self.logger.debug('Worked time: %s', str(wk_time))

                if dtype3 in ["CAO", "MAL"]:
                    wk_period = int(wk_period / 2)
                
                # Check if a part of the day was a vacation
                if dtype3 == "CAO":
                    self.logger.info('Half a day was a vacation, record it.')
                    txn = self.__txn_vacation(meta, date, "Demi-jour de congé",
                                              amount.Amount(decimal.Decimal('0.5'),
                                                            self.commodity_vacation_day),
                                              amount.Amount(decimal.Decimal(wk_period),
                                                            self.commodity_overtime))
                    self.logger.info('Vacation date: %s', date)
                    entries.append(txn)

                self.logger.info('Worked period for the day (in Minutes): %s', str(wk_period))

                overtime = wk_time - wk_period
                workday_counter += 1
                
                self.logger.debug('Overtime for the day: %s', str(overtime))

                units_overtime += overtime
                self.logger.info('Cumulative overtime for the month: %g', units_overtime)
            else:
                # If it is a work day, but I was sick or it was a legal holiday, skip it.
                if dtype3 in ["JFR", "MAL", "COLFE"] and dtype4 == '':
                    self.logger.info('Non-worked day detected, skip it.')
                    continue

                # If it is a work day, but I was on vacation, add an entry for a vacation day.
                if dtype3 == "CAO":
                    self.logger.info('Vacation day detected, record it.')
                    txn = self.__txn_vacation(meta, date, "Congé",
                                              amount.Amount(decimal.Decimal('1'),
                                                            self.commodity_vacation_day),
                                              amount.Amount(decimal.Decimal(self.standard_work_period),
                                                            self.commodity_overtime))
                    self.logger.info('Vacation date: %s', date)
                    entries.append(txn)
                else:
                    if  dtype4 == "CAO":
                        wk_period = int(wk_period / 2)
                        txn = self.__txn_vacation(meta, date, "Demi-jour de congé",
                                                  amount.Amount(decimal.Decimal('0.5'), self.commodity_vacation_day),
                                                  amount.Amount(decimal.Decimal(wk_period), self.commodity_overtime))
                        self.logger.info('Vacation date: %s', date)
                        entries.append(txn)
                    else:
                        self.logger.warning("Unknown day type detected, row ignored.")
                        self.logger.warning('Data in row: %s', str(row))
                        continue

        # When there is no more row to process, create a transaction with the remaining overtime
        self.logger.debug('End of file reached. Record remaining overtime and number of worked days.')
        meta_w_month['worked_period'] = "{}-{}".format(cur_year, cur_month)
        txn = self.__txn_overtime(meta_w_month,
                                  date,
                                  self.__int_to_Amount(units_overtime,
                                                       self.commodity_overtime))
        self.logger.info('Overtime recorded at date: %s', date)
        entries.append(txn)

        txn = self.__txn_worked_day_in_month(meta_w_month,
                                             date,
                                             self.__int_to_Amount(workday_counter,
                                                                  self.commodity_workday))
        self.logger.info('Number of worked days recorded at date: %s', workday_counter)
        entries.append(txn)

        self.logger.debug("Leaving Function")
        return entries

def test():
    # Create an importer instance for running the regression tests.
    importer = Importer("EXTHR", "VACDAY", "7:36", "My Employer s.a.", "Customer s.a.",
                        "Income:BE:Customer:HeureSup",
                        "Assets:BE:Employer",
                        "Assets:BE:Employer:HeureSup",
                        "Assets:BE:Employer:JourConge",
                        "Expenses:Conge")
    # yield from regression.compare_sample_files(importer, __file__)
