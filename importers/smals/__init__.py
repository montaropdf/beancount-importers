# -*- eval: (git-auto-commit-mode 1) -*-
"""Importer for Timesheet Report from one of my customer in CSV format."""
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
from beancount.core import inventory
from beancount.ingest import importer
from beancount.ingest import regression

import utils

class TimesheetCsvFileDefinition():
    """A class that define the input file and provides all the facilities to read it."""
    def __init__(self, logger):
        self.logger = logger

        self.logger.debug("Entering Function")

        # self.iso_date_regex = "(\d{4})-(0\d|1[0-2])-([0-2]\d|3[01])"
        self.year_month_regex = "\d{4}(0\d|1[0-2])"
        self.core_filename_regex = "smals-report-" + self.year_month_regex + "-cleaned"
        self.extension_regex = "\.csv"
        # self.date_prefix_regex = self.iso_date_regex
        self.tag_suffix_regex = "(_.+)*"

        self.logger.debug("core_filename_regex: %s", self.core_filename_regex)

        self.csvDialect = csv.excel()
        self.csvDialect.delimiter = ';'

        self.logger.info("Object initialisation done.")

    def get_Reader(self, input_filename):
        """Return a csv.DictReader object"""
        self.logger.debug("Entering Function")

        reader = csv.DictReader(open(input_filename), dialect=self.csvDialect)

        self.logger.debug("Leaving Function")

        return reader

    def isTimesheetFileName(self, filename):
        """Check if the filename have the format of an invoice from Hetzner."""
        self.logger.debug("Entering Function")

        self.logger.debug("Filename to analyse %s", filename)

        matching_result = re.match(r"{}{}{}".format(self.core_filename_regex, self.tag_suffix_regex, self.extension_regex), path.basename(filename))

        self.logger.debug("Leaving Function")

        return matching_result

    def get_DateInFileName(self, filename):
        self.logger.debug("Entering Function")
        self.logger.debug("Filename to analyse %s", filename)

        dateinfile = re.findall(self.core_filename_regex, filename)[0]
        self.logger.debug("Date element found %s", dateinfile)
        dateinfile = "-".join(dateinfile)

        self.logger.debug("Date in file %s", dateinfile)
        self.logger.debug("Leaving Function")

        return dateinfile

class Importer(importer.ImporterProtocol):
    """An importer for the Timesheet Report CSV files provided by one of my customer."""

    def __init__(self, commodity_overtime, commodity_vacation_day, commodity_workday, standard_work_period,
                 employer,
                 customer,
                 account_working_day,
                 account_customer_overtime,
                 account_customer_worked_day,
                 account_employer_root,
                 account_employer_overtime,
                 account_employer_vacation,
                 account_employer_worked_day,
                 account_sickness,
                 account_vacation):

        self.logger = logging.Logger("smals", logging.DEBUG)

        fh = logging.FileHandler('smals-importer.log')
        fmtr = logging.Formatter('%(asctime)s - %(levelname)s - %(lineno)d - %(funcName)s | %(message)s')

        fh.setFormatter(fmtr)
        self.logger.addHandler(fh)

        self.commodity_overtime = commodity_overtime
        self.commodity_vacation_day = commodity_vacation_day
        self.commodity_workday = commodity_workday
        self.standard_work_period = self.__str_time_to_minutes(standard_work_period)
        self.employer = employer
        self.customer = customer
        self.account_working_day = account_working_day
        self.account_customer_overtime = account_customer_overtime
        self.account_customer_worked_day = account_customer_worked_day
        self.account_employer_root = account_employer_root
        self.account_employer_overtime = account_employer_overtime
        self.account_employer_vacation = account_employer_vacation
        self.account_employer_worked_day = account_employer_worked_day
        self.account_sickness = account_sickness
        self.account_vacation = account_vacation
        
        self.inputFile = TimesheetCsvFileDefinition(self.logger)
        
        self.logger.info("Logger Initialized")
        self.logger.debug("Input parameters:")
        self.logger.debug("Commodity name for overtime units: %s", self.commodity_overtime)
        self.logger.debug("Commodity name for vacation day units: %s", self.commodity_vacation_day)
        self.logger.debug("Commodity name for worked day units: %s", self.commodity_workday)
        self.logger.debug("Standard work time period: %s", str(self.standard_work_period))
        self.logger.debug("Employer: %s", self.employer)
        self.logger.debug("Customer: %s", self.customer)
        self.logger.debug("Account to use to get working days from: %s", self.account_working_day)
        self.logger.debug("Account to use to get overtime from: %s", self.account_customer_overtime)
        self.logger.debug("Account to use to get worked day from: %s", self.account_customer_worked_day)
        self.logger.debug("Root account of the employer: %s", self.account_employer_root)
        self.logger.debug("Account to use to store overtime: %s", self.account_employer_overtime)
        self.logger.debug("Account containing vacation days: %s", self.account_employer_vacation)
        self.logger.debug("Account to use to store number of worked days: %s", self.account_employer_worked_day)
        self.logger.debug("Account to use to store number of sickness days: %s", self.account_sickness)
        self.logger.debug("Account to use to record spent vacation days: %s", self.account_vacation)
        
        self.logger.info("Object initialisation done.")
        
    def __txn_vacation(self, meta, date, desc, units_vac, units_ovt, price):
        """Return a holiday transaction object."""
        self.logger.debug("Entering Function")

        txn =  data.Transaction(
            meta, date, "!", self.employer, desc, data.EMPTY_SET, data.EMPTY_SET, [
                data.Posting(self.account_vacation, units_vac, None, None, None, None),
                data.Posting(self.account_employer_vacation, -units_vac, None, None, None, None),
                data.Posting(self.account_vacation, units_vac, None, price, "!", None),
                data.Posting(self.account_employer_overtime, -units_ovt, None, None, "!", None)
                ])

        self.logger.debug('Transaction to be recorded: %s', str(txn))
        self.logger.debug("Leaving Function")
        
        return txn
        
    def __txn_common(self, meta, date, acc_in, acc_out, units_common, payee="", desc=""):
        """Return a transaction object for simple transactions."""
        self.logger.debug("Entering Function")

        self.logger.debug("Receiving account: %s", acc_in)
        self.logger.debug("Sending account: %s", acc_out)

        txn =  data.Transaction(
            meta, date, self.FLAG, payee, desc, data.EMPTY_SET, data.EMPTY_SET, [
                data.Posting(acc_in, units_common, None, None, None, None),
                data.Posting(acc_out, -units_common, None, None, None, None)
                ])

        self.logger.debug('Transaction to be recorded: %s', str(txn))
        self.logger.debug("Leaving Function")
        
        return txn

    # def __iof2Amount(self, value, commodity):
    #     """Convert a value as a int to an Amount object."""
    #     self.logger.debug("Entering Function")
    #     atr = decimal.Decimal(value)
    #     atr = amount.Amount(atr, commodity)
    #     self.logger.debug("Amount to return: %s", atr)
    #     self.logger.debug("Leaving Function")

    #     return atr

    def __str_time_to_minutes(self, time_as_str_or_tuple):
        """Convert a time period expressed as a string into a number of minutes as an int."""
        self.logger.debug("Entering Function")

        self.logger.debug("Parameter to transform: '%s'", time_as_str_or_tuple)
        self.logger.debug("Parameter type: %s", type(time_as_str_or_tuple))

        if type(time_as_str_or_tuple) == str:
            self.logger.debug("Is it in [H]H:MM format: %s", re.fullmatch("^[0-9]{1,2}:[0-5][0-9]$", time_as_str_or_tuple))
            if re.fullmatch("^[0-9]{1,2}:[0-5][0-9]$", time_as_str_or_tuple) != None:
                time_as_tuple = (int(time_as_str_or_tuple.split(':')[0]), int(time_as_str_or_tuple.split(':')[1]))
            else:
                raise ValueError("Parameter was not a string  of the form [H]H:MM: {}".format(time_as_str_or_tuple))
        elif type(time_as_str_or_tuple) == tuple and len(time_as_str_or_tuple) == 2 and type(time_as_str_or_tuple[0]) == int and type(time_as_str_or_tuple[1]):
            time_as_tuple = time_as_str_or_tuple
        else:
            raise ValueError("Parameter was not a string or a tuple of 2 elements")

        return (time_as_tuple[0] * 60) + time_as_tuple[1]
    
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
        self.logger.info("File name to be used: %s", 'smals-ts-report.{}'.format(path.basename(file.name)))
        self.logger.debug("Leaving Function")
        return 'smals-ts-report.{}'.format(path.basename(file.name))

    def file_account(self, _):
        self.logger.debug("Entering Function")
        self.logger.info("File account: %s", self.account_employer_root)
        self.logger.debug("Leaving Function")
        return self.account_employer_root

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
        units_overtime = 0
        cur_month = 0
        cur_year = 0
        workday_counter = 0

        self.logger.debug('Standard working time period in minutes: %d', self.standard_work_period)
        
        for index, row in enumerate(self.inputFile.get_Reader(file.name)):
            self.logger.debug('Data in row: %s', str(row))
            meta = data.new_metadata(file.name, index)
            meta_w_month = data.new_metadata(file.name, index)
            date = datetime.datetime.strptime(row['DATE'], '%d/%m/%Y').date()
            day, month, year = row['DATE'].split('/')
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

                txn = self.__txn_common(meta_w_month,
                                        date,
                                        self.account_employer_overtime,
                                        self.account_customer_overtime,
                                        toAmount(units_overtime,
                                                 self.commodity_overtime),
                                        self.customer)
                self.logger.info('Overtime recorded at date: %s', date)

                entries.append(txn)
                units_overtime = 0
                txn = self.__txn_common(meta_w_month,
                                        date,
                                        self.account_employer_worked_day,
                                        self.account_customer_worked_day,
                                        toAmount(workday_counter,
                                                 self.commodity_workday),
                                        self.customer)
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
                wk_period_full = self.standard_work_period

                self.logger.debug('Worked time: %s', str(wk_time))

                if dtype3 in ["CAO", "MAL"]:
                    wk_period = int(wk_period_full / 2)
                else:
                    wk_period = wk_period_full
                    
                # Check if a part of the day was a vacation
                if dtype3 == "CAO":
                    self.logger.info('Half a day was a vacation, record it.')
                    txn = self.__txn_vacation(meta, date, "Demi-jour de congé",
                                              toAmount(0.5,
                                                       self.commodity_vacation_day),
                                              toAmount(wk_period,
                                                       self.commodity_overtime),
                                              toAmount(wk_period_full,
                                                       self.commodity_overtime)
                    )
                    self.logger.info('Vacation date: %s', date)
                    entries.append(txn)

                if dtype3 == "MAL":
                    txn = self.__txn_common(meta,
                                            date,
                                            self.account_sickness,
                                            self.account_working_day,
                                            toAmount(0.5,
                                                     self.commodity_workday),
                                            self.employer,
                                            "Incapacité de travail"
                    )
                    entries.append(txn)
                    
                self.logger.info('Worked period for the day (in Minutes): %s', str(wk_period))

                overtime = wk_time - wk_period
                workday_counter += 1
                
                self.logger.debug('Overtime for the day: %s', str(overtime))

                units_overtime += overtime
                self.logger.info('Cumulative overtime for the month: %g', units_overtime)
            else:
                # If it is a work day, but I was sick or it was a legal holiday, skip it.
                if dtype3 in ["JFR", "COLFE"] and dtype4 == '':
                    self.logger.info('Non-worked day detected, skip it.')
                    continue

                if dtype3 == "MAL":
                    if dtype4 == '':
                        u = 1
                    else:
                        u = 0.5
                        
                    txn = self.__txn_common(meta,
                                            date,
                                            self.account_sickness,
                                            self.account_working_day,
                                            toAmount(u,
                                                     self.commodity_workday),
                                            self.employer,
                                            "Incapacité de travail"
)
                    entries.append(txn)

                # If it is a work day, but I was on vacation, add an entry for a vacation day.
                if dtype3 == "CAO":
                    self.logger.info('Vacation day detected, record it.')
                    txn = self.__txn_vacation(meta, date, "Congé",
                                              toAmount(1,
                                                       self.commodity_vacation_day),
                                              toAmount(self.standard_work_period,
                                                       self.commodity_overtime),
                                              toAmount(self.standard_work_period,
                                                       self.commodity_overtime)
                    )
                    self.logger.info('Vacation date: %s', date)
                    entries.append(txn)
                else:
                    if  dtype4 == "CAO":
                        wk_period = int(wk_period / 2)
                        txn = self.__txn_vacation(meta, date, "Demi-jour de congé",
                                                  toAmount(0.5,
                                                           self.commodity_vacation_day),
                                                  toAmount(wk_period,
                                                           self.commodity_overtime),
                                                  toAmount(wk_period_full,
                                                           self.commodity_overtime)
)
                        self.logger.info('Vacation date: %s', date)
                        entries.append(txn)
                    else:
                        self.logger.warning("Unknown day type detected, row ignored.")
                        self.logger.warning('Data in row: %s', str(row))
                        continue

        # When there is no more row to process, create a transaction with the remaining overtime
        self.logger.debug('End of file reached. Record remaining overtime and number of worked days.')
        meta_w_month['worked_period'] = "{}-{}".format(cur_year, cur_month)
        txn = self.__txn_common(meta_w_month,
                                date,
                                self.account_employer_overtime,
                                self.account_customer_overtime,
                                toAmount(units_overtime,
                                         self.commodity_overtime),
                                self.customer)
        self.logger.info('Overtime recorded at date: %s', date)
        entries.append(txn)

        txn = self.__txn_common(meta_w_month,
                                date,
                                self.account_employer_worked_day,
                                self.account_customer_worked_day,
                                toAmount(workday_counter,
                                         self.commodity_workday),
                                self.customer)
        self.logger.info('Number of worked days recorded at date: %s', workday_counter)
        entries.append(txn)

        self.logger.debug("Leaving Function")
        return entries

# def test():
#     # Create an importer instance for running the regression tests.
#     importer = Importer("EXTHR", "VACDAY", "7:36", "My Employer s.a.", "Customer s.a.",
#                         "Income:BE:Customer:HeureSup",
#                         "Assets:BE:Employer",
#                         "Assets:BE:Employer:HeureSup",
#                         "Assets:BE:Employer:JourConge",
#                         "Expenses:Conge")
#     # yield from regression.compare_sample_files(importer, __file__)
