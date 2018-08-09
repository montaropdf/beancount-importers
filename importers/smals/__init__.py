"""Importer for Timesheet Report from one of my customer in CSV format."""
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

    def __init__(self, commodity_overtime, commodity_vacation_day, standard_work_period,
                 employer,
                 customer,
                 account_customer_overtime,
                 account_employer_root,
                 account_employer_overtime,
                 account_employer_vacation,
                 account_vacation):
        self.commodity_overtime = commodity_overtime
        self.commodity_vacation_day = commodity_vacation_day
        self.standard_work_period = self.__str_time_to_minutes(standard_work_period) # datetime.datetime(1970, 1, 1, int(standard_work_period.split(':')[0]), int(standard_work_period.split(':')[1]))
        self.employer = employer
        self.customer = customer
        self.account_customer_overtime = account_customer_overtime
        self.account_employer_root = account_employer_root
        self.account_employer_overtime = account_employer_overtime
        self.account_employer_vacation = account_employer_vacation
        self.account_vacation = account_vacation
        self.logger = logging.Logger("smals", logging.DEBUG)

        fh = logging.FileHandler('smals-importer.log')
        fmtr = logging.Formatter('%(levelname)s - %(lineno)d - %(funcName)s | %(message)s')

        fh.setFormatter(fmtr)
        self.logger.addHandler(fh)

        self.logger.info("Logger Initialized")
        self.logger.debug("Input parameters:")
        self.logger.debug("Commodity name for overtime units: %s", self.commodity_overtime)
        self.logger.debug("Commodity name for vacation day units: %s", self.commodity_vacation_day)
        self.logger.debug("Standard work time period: %s", str(self.standard_work_period))
        self.logger.debug("Employer: %s", self.employer)
        self.logger.debug("Customer: %s", self.customer)
        self.logger.debug("Account to use to get overtime from: %s", self.account_customer_overtime)
        self.logger.debug("Root account of the employer: %s", self.account_employer_root)
        self.logger.debug("Account to use to store overtime: %s", self.account_employer_overtime)
        self.logger.debug("Account containing vacation days: %s", self.account_employer_vacation)
        self.logger.debug("Account to use to record spent vacation days: %s", self.account_vacation)
        
        # print('{} {}'.format(self.commodity_overtime, self.commodity_vacation_day))

        self.logger.info("Object initialisation done.")
        
    def __txn_vacation(self, meta, date, desc, units_vac, units_ovt):
        """Return a holiday transaction object."""
        self.logger.debug("Entering Function")

        txn =  data.Transaction(
            meta, date, "!", self.employer, desc, data.EMPTY_SET, data.EMPTY_SET, [
                data.Posting(self.account_vacation, units_vac, None, None, None, None),
                data.Posting(self.account_employer_vacation, -units_vac, None, None, None, None),
                data.Posting(self.account_vacation, units_vac, None, units_ovt, "!", None),
                data.Posting(self.account_employer_overtime, -units_ovt, None, None, "!", None)
                ])

        self.logger.debug('Transaction to be recorded: %s', str(txn))
        self.logger.debug("Leaving Function")
        
        return txn
        
    def __txn_overtime(self, meta, date, units_ovt):
        """Return an overtime transaction object."""
        self.logger.debug("Entering Function")

        txn =  data.Transaction(
            meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
                data.Posting(self.account_employer_overtime, units_ovt, None, None, None, None),
                data.Posting(self.account_customer_overtime, -units_ovt, None, None, None, None)
                ])

        self.logger.debug('Transaction to be recorded: %s', str(txn))
        self.logger.debug("Leaving Function")
        
        return txn

    def __int_to_Amount(self, value, commodity):
        """Convert a value as a int to an Amount object."""
        self.logger.debug("Entering Function")
        atr = decimal.Decimal(value)
        atr = amount.Amount(atr, commodity)
        self.logger.debug("Amount to return: %s", atr)
        self.logger.debug("Leaving Function")

        return atr

    def __str_time_to_minutes(self, time_as_str_or_tuple):
        """Convert a time period expressed as a string into a number of minutes as an int."""

        if type(time_as_str_or_tuple) == str and re.fullmatch("^[0-9]{1-2}:[0-5][0-9]$", time_as_str_or_tuple) != None:
            time_as_tuple = (int(time_as_str_or_tuple.split(':')[0]), int(time_as_str_or_tuple.split(':')[1]))
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
        self.logger.info("Identification result: %s", str(re.match(r"smals-report-\d\d\d\d\d\d-cleaned.csv", path.basename(file.name)) and
                                                          re.match("DATE;DAYTYPE;STD;DAYTYPE2;TIMESPENT;DAYTYPE3;TIMEREC", file.head())))
        self.logger.debug("Leaving Function")
        # print(file)
        # print("identify")
        return (re.match(r"smals-report-\d\d\d\d\d\d-cleaned.csv", path.basename(file.name)) and
                re.match("DATE;DAYTYPE;STD;DAYTYPE2;TIMESPENT;DAYTYPE3;TIMEREC", file.head()))

    def file_name(self, file):
        # print("file_name")
        self.logger.debug("Entering Function")
        self.logger.info("File name to be used: %s", 'smals-ts-report.{}'.format(path.basename(file.name)))
        self.logger.debug("Leaving Function")
        return 'smals-ts-report.{}'.format(path.basename(file.name))

    def file_account(self, _):
        # print("file_account " + str(self.account_employer_root))
        self.logger.debug("Entering Function")
        self.logger.info("File account: %s", self.account_employer_root)
        self.logger.debug("Leaving Function")
        return self.account_employer_root

    def file_date(self, file):
        # Extract the statement date from the filename.
        # print("file_date " + file.name)
        self.logger.debug("Entering Function")
        filedate = datetime.datetime.strptime(path.basename(file.name),
                                          'smals-report-%Y%m-cleaned.csv').date()
        self.logger.info("File date used: %s", str(filedate))
        self.logger.debug("Leaving Function")
        return filedate

    def extract(self, file):
        # Open the CSV file and create directives.
        # print("extract")
        self.logger.debug("Entering Function")
        self.logger.info("Extracting transactions from file: %s", str(file))

        entries = []
        index = 0
        units_overtime = 0
        cur_month = 0
        swp_minutes =  int((self.standard_work_period - datetime.datetime(1970, 1, 1)).total_seconds() / 60)
        self.logger.debug('Standard working time period in minutes: %d', swp_minutes)
        
        csvDialect = csv.excel();
        csvDialect.delimiter = ';'
        
        for index, row in enumerate(csv.DictReader(open(file.name), dialect=csvDialect)): # , dialect=csvDialect
            self.logger.debug('Data in row: %s', str(row))
            # print(row)
            meta = data.new_metadata(file.name, index)
            # print(row['DATE'])

            date = datetime.datetime.strptime(row['DATE'], '%d/%m/%Y').date()
            month = row['DATE'][3:2]
            self.logger.debug("Month: %s", month)
            self.logger.debug("Current Month: %s", cur_month)

            if cur_month == 0:
                cur_month = month

            # If the month change, create the transaction for the overtime of the previous month
            if cur_month != month:
                cur_month = month

                txn = self.__txn_overtime(meta, date, self.int_to_Amount(units_overtime, self.commodity_overtime))
                self.logger.info('Overtime recorded at date: %s', date)
                # txn = data.Transaction(
                #     meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
                #         data.Posting(self.account_employer_overtime, units_overtime, None, None, None, None),
                #         data.Posting(self.account_customer_overtime, -units_overtime, None, None, None, None)
                #     ])

                entries.append(txn)
                units_overtime = 0
            
            dtype = row['DAYTYPE']
            dtype2 = row['DAYTYPE2']
            dtype3 = row['DAYTYPE3']
            self.logger.debug('Day of week type: %s', dtype)
            self.logger.debug('Work day type 1: %s', dtype2)
            self.logger.debug('Work day type 2: %s', dtype3)

            # print('{} {} {} {}'.format(date, dtype, dtype2, dtype3))
            
            # If it is a week-end day or a day for which I was not yet at Smals, skip it.
            if dtype in ["WK-PT", "-"]:
                self.logger.debug('Week-end day detected.')
                continue

            # If it is a work day, check if some overtime can be added to the overtime account.
            if dtype2 == "PRE":
                self.logger.debug('Work day detected.')

                wk_time = self.__str_time_to_minutes(row['TIMESPENT'])#   datetime.datetime(1970, 1, 1, int(row['TIMESPENT'].split(':')[0]), int(row['TIMESPENT'].split(':')[1]))
                wk_period = self.standard_work_period

                self.logger.debug('Worked time: %s', str(wk_time))
                
                # Check if a part of the day was a vacation
                if dtype3 == "CAO":
                    self.logger.debug('Half a day was a vacation, record it.')
                    txn = self.__txn_vacation(meta, date, "Demi-jour de congé",
                                       amount.Amount(decimal.Decimal('0.5'), self.commodity_vacation_day),
                                       amount.Amount(decimal.Decimal(swp_minutes), self.commodity_overtime))
                    self.logger.info('Vacation date: %s', date)
                    entries.append(txn)
                    wk_period = int(wk_period / 2)

                self.logger.debug('Worked period for the day (in Minutes): %s', str(wk_period))
                # overtime = decimal.Decimal((wk_time - wk_period).total_seconds() / 60)

                swp_minutes = int((self.standard_work_period - datetime.datetime(1970, 1, 1)).total_seconds() / 60)

                overtime = wk_time - wk_period

                self.logger.debug('Overtime for the day: %s', str(overtime))

                # if overtime <= 0:
                    # continue

                # desc = "Heure Supplémentaire"
                units_overtime += overtime
                # txn = data.Transaction(
                #     meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
                #         data.Posting(self.account_employer_overtime, units_overtime, None, None, None, None),
                #         data.Posting(self.account_customer_overtime, -units_overtime, None, None, None, None)
                #     ])
                self.logger.debug('Cumulative overtime for the month: %g', units_overtime)
            else:
                # If it is a work day, but I was sick or it was a legal holiday, skip it.
                if dtype3 in ["JFR", "MAL", "COLFE"]:
                    self.logger.debug('Non-worked day detected, skip it.')
                    continue

                # If it is a work day, but I was on vacation, add an entry for a vacation day.
                if dtype3 == "CAO":
                    self.logger.debug('Vacation day detected, record it.')
                    txn = self.__txn_vacation(meta, date, "Congé",
                                       amount.Amount(decimal.Decimal('1'), self.commodity_vacation_day),
                                           amount.Amount(decimal.Decimal(swp_minutes), self.commodity_overtime))
                    self.logger.info('Vacation date: %s', date)
                    entries.append(txn)
                    
                    # txn = data.Transaction(
                    #     meta, date, "!", self.employer, desc, data.EMPTY_SET, data.EMPTY_SET, [
                    #         data.Posting(self.account_vacation, units_vacation, None, None, None, None),
                    #         data.Posting(self.account_employer_holiday, -units_vacation, None, None, None, None),
                    #         data.Posting(self.account_vacation, units_vacation, None, units_overtime, "!", None),
                    #         data.Posting(self.account_employer_overtime, -units_overtime, None, None, "!", None)
                    #     ])
                else:
                    self.logger.warning("Unknown day type detected, row ignored.")
                    self.logger.warning('Data in row: %s', str(row))
                    # print("Bad row")
                    continue

            # entries.append(txn)

        # When there is no more row to process, create a transaction with the remaining overtime
        self.logger.debug('End of file reached. Record remaining overtime.')
        txn = self.__txn_overtime(meta, date, self.int_to_Amount(units_overtime, self.commodity_overtime))
        self.logger.info('Overtime recorded at date: %s', date)
        # txn = data.Transaction(
        #     meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
        #         data.Posting(self.account_employer_overtime, units_overtime, None, None, None, None),
        #         data.Posting(self.account_customer_overtime, -units_overtime, None, None, None, None)
        #         ])
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
