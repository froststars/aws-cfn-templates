# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '02/06/2017'

import pyminifier.minification
import pyminifier.token_utils
import pyminifier.compression


def load_python_lambda(filename):
    """Use pyminifier to reduce code size, CloudFormation inline size
    limit is 4K."""

    class Options(object): tabs = True

    with open(filename) as f:
        original_source = f.read()
        tokens = pyminifier.token_utils.listified_tokenizer(original_source)
        options = Options()
        lambda_code = pyminifier.minification.minify(tokens, options)
        return lambda_code

