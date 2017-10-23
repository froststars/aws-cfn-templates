# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '02/06/2017'

import json
import csv

def load_mapping(filename):
    """Load a mapping form JSON file"""
    with open(filename) as f:
        return json.load(f)


def load_csv_as_mapping(filename, key1, key2, value):
    """ Load mapping from a CSV file

    :param filename: name of the csv file
    :param key1: column name for first mapping key
    :param key2: column name for second mapping key
    :param value: column name for second mapping value
    """
    mapping = dict()
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row[key1]] = {key2: row[value]}

    return mapping
