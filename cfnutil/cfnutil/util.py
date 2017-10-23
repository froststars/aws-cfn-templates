# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '09/10/2016'

import re

import troposphere
import troposphere.elasticbeanstalk as beanstalk
import cfn_flip


def generate_parameter_labels(parameter_groups):
    """Generate parameter labels from interface section, assuming all parameters
    are CamelCased."""
    for g in parameter_groups:
        for p in (g['Parameters']):
            yield p, {'default': re.sub(r'([A-Z]+)', r' \1', p).strip()}


def load_config_file(filename, **kwargs):
    with open(filename) as fp:
        text = fp.read()
        return (text % kwargs) if kwargs else text


def make_beanstalk_option_settings(settings):
    """Make Beanstalk application option settings from a list of tuples
        (namespace, option_name, value)"""
    return list(
        beanstalk.OptionSettings(Namespace=n, OptionName=o, Value=v) for n, o, v
        in settings)


def write(template, filename, write_yaml=True):
    assert isinstance(template, troposphere.Template)
    with open(filename, 'w') as f:
        if write_yaml:
            f.write(cfn_flip.to_yaml(template.to_json(), clean_up=True))
        else:
            f.write(template.to_json(indent=2))
