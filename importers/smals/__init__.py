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
                 account_employer_holiday,
                 account_vacation):
        self.commodity_overtime = commodity_overtime
        self.commodity_vacation_day = commodity_vacation_day
        self.standard_work_period = datetime.datetime(1970, 1, 1, int(standard_work_period.split(':')[0]), int(standard_work_period.split(':')[1]))
        self.employer = employer
        self.customer = customer
        self.account_customer_overtime = account_customer_overtime
        self.account_employer_root = account_employer_root
        self.account_employer_overtime = account_employer_overtime
        self.account_employer_holiday = account_employer_holiday
        self.account_vacation = account_vacation
        
        # print('{} {}'.format(self.commodity_overtime, self.commodity_vacation_day))

    def tnx_holiday(self, meta, date, desc, unit_vac, unit_ovt):
        """Return a holiday transaction object."""

        return  data.Transaction(
            meta, date, "!", self.employer, desc, data.EMPTY_SET, data.EMPTY_SET, [
                data.Posting(self.account_vacation, units_vac, None, None, None, None),
                data.Posting(self.account_employer_holiday, -units_vac, None, None, None, None),
                data.Posting(self.account_vacation, units_vac, None, unit_ovt, "!", None),
                data.Posting(self.account_employer_overtime, -unit_ovt, None, None, "!", None)
                ])

    def tnx_overtime(self, meta, date, unit_ovt):
        """Return an overtime transaction object."""

        return data.Transaction(
            meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
                data.Posting(self.account_employer_overtime, units_ovt, None, None, None, None),
                data.Posting(self.account_customer_overtime, -units_ovt, None, None, None, None)
                ])
        
    def identify(self, file):
        # Match if the filename is as downloaded and the header has the unique
        # fields combination we're looking for.
        print(file)
        print("identify")
        return (re.match(r"smals-report-\d\d\d\d\d\d-cleaned.csv", path.basename(file.name)) and
                re.match("DATE;DAYTYPE;STD;DAYTYPE2;TIMESPENT;DAYTYPE3;TIMEREC", file.head()))

    def file_name(self, file):
        # print("file_name")
        return 'smals-ts-report.{}'.format(path.basename(file.name))

    def file_account(self, _):
        # print("file_account " + str(self.account_employer_root))
        return self.account_employer_root

    def file_date(self, file):
        # Extract the statement date from the filename.
        # print("file_date " + file.name)
        return datetime.datetime.strptime(path.basename(file.name),
                                          'smals-report-%Y%m-cleaned.csv').date()

    def extract(self, file):
        # Open the CSV file and create directives.
        # print("extract")
        entries = []
        index = 0
        units_overtime = 0
        swp_minutes = int((self.standard_work_period - datetime.datetime(1970, 1, 1)).total_seconds() / 60)

        csvDialect = csv.excel();
        csvDialect.delimiter = ';'
        
        for index, row in enumerate(csv.DictReader(open(file.name), dialect=csvDialect)): # , dialect=csvDialect
            # print(row)
            meta = data.new_metadata(file.name, index)
            # print(row['DATE'])

            date = datetime.datetime.strptime(row['DATE'], '%d/%m/%Y').date()
            month = row['DATE'][3:2]
            print("Month: {}".format(month))
            print("Current Month: {}".format(cur_month))

            if cur_month == 0:
                cur_month = month

            # If the month change, create the transaction for the overtime of the previous month
            if cur_month != month:
                cur_month = month

                tnx = tnx_overtime(meta, date, units_overtime)
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

            # print('{} {} {} {}'.format(date, dtype, dtype2, dtype3))
            
            # If it is a week-end day or a day for which I was not yet at Smals, skip it.
            if dtype in ["WK-PT", "-"]:
                continue

            # If it is a work day, check if some overtime can be added to the overtime account.
            if dtype2 == "PRE":
                wk_time = datetime.datetime(1970, 1, 1, int(row['TIMESPENT'].split(':')[0]), int(row['TIMESPENT'].split(':')[1]))
                wk_period = self.standard_work_period

                # Check if a part of the day was a vacation
                if dtype3 == "CAO":
                    txn = txn_vacation(amount.Amount(decimal.Decimal('0.5'), self.commodity_vacation_day),
                                       amount.Amount(decimal.Decimal(swp_minutes), self.commodity_overtime))
                    entries.append(txn)
                    wk_period = wk_period / 2

                overtime = decimal.Decimal((wk_time - wk_period).total_seconds() / 60)

                # if overtime <= 0:
                    # continue

                # desc = "Heure Supplémentaire"
                units_overtime += amount.Amount(overtime, self.commodity_overtime)
                # txn = data.Transaction(
                #     meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
                #         data.Posting(self.account_employer_overtime, units_overtime, None, None, None, None),
                #         data.Posting(self.account_customer_overtime, -units_overtime, None, None, None, None)
                #     ])

            else:
                # If it is a work day, but I was sick or it was a legal holiday, skip it.
                if dtype3 in ["JFR", "MAL", "COLFE"]:
                    continue

                # If it is a work day, but I was on vacation, add an entry for a vacation day.
                if dtype3 == "CAO":
                    txn = txn_vacation(meta, date, "Congé",
                                       amount.Amount(decimal.Decimal('1'), self.commodity_vacation_day),
                                           amount.Amount(decimal.Decimal(swp_minutes), self.commodity_overtime))
                    entries.append(txn)
                    
                    # txn = data.Transaction(
                    #     meta, date, "!", self.employer, desc, data.EMPTY_SET, data.EMPTY_SET, [
                    #         data.Posting(self.account_vacation, units_vacation, None, None, None, None),
                    #         data.Posting(self.account_employer_holiday, -units_vacation, None, None, None, None),
                    #         data.Posting(self.account_vacation, units_vacation, None, units_overtime, "!", None),
                    #         data.Posting(self.account_employer_overtime, -units_overtime, None, None, "!", None)
                    #     ])
                else:
                    # print("Bad row")
                    continue

            # entries.append(txn)

        # When there is no more row to process, create a transaction with the remaining overtime
        tnx = tnx_overtime(meta, date, units_overtime)
        # txn = data.Transaction(
        #     meta, date, self.FLAG, self.customer, None, data.EMPTY_SET, data.EMPTY_SET, [
        #         data.Posting(self.account_employer_overtime, units_overtime, None, None, None, None),
        #         data.Posting(self.account_customer_overtime, -units_overtime, None, None, None, None)
        #         ])
        entries.append(txn)

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
