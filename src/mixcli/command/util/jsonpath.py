"""
MixCli **util** command group **jsonpath** command.

This command will process a JSON file with a specified JsonPath query and send result to STDOUT.

This command accepts JsonPath queries that are supported by jsonpath-ng project at
&nbsp;[https://github.com/h2non/jsonpath-ng](https://github.com/h2non/jsonpath-ng). One important note is that
Python JsonPath-ng always return a list, which could be empty, when JsonPath query matches none of values, or all
values the query has matched.

To access the element(s) in the query result list, users may use the switch "--always-first" to have the command
always post-process query results and extract the first element in the list, should list be non-empty.

On the otherhand, users may use "--postproc-pyexpr" to have a Python EXPRESSION to be evaluated on query result list
and take evaluation result as end result. In the Python expression, use placeholder 'r' (case-sensitive) to refer to
the query result list. For example, **--postproc-pyexpr "r[0]"** would yield the same result as **--always-first**.
Please NOTE the different betwwen EXPRESSION and STATEMENT. For example, **r[0]** is a supported expression,
while **a=r[0]** is a **statement** which would not work.
"""
import codecs
import json
import os.path
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Optional, List

from jsonpath_ng import parse

from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func


def jsonpath_on_jsonfile(jsonfile: str, jsonpath: str) -> Optional[List]:
    """
    Run given JsonPath query on Json File. If there are any matchings from query, return the list of all matchings,
    which may contain one or more than one element. Otherwise return empty list.

    :param jsonfile: Path to JSON file to process
    :param jsonpath: String of JsonPath expression
    :return: List of matched JSON values if expression has matching, or empty list if none.
    """
    if not os.path.isfile(jsonfile):
        raise FileNotFoundError(f'Input JSON file not found: {jsonfile}')
    with codecs.open(jsonfile, 'r', 'utf-8') as fhij:
        injson = json.load(fhij)
        try:
            jsonpath_expr = parse(jsonpath)
        except Exception as ex:
            raise RuntimeError(f'Error with JsonPath expression: {jsonpath}') from ex
        match_list = jsonpath_expr.find(injson)
        if not match_list:
            return match_list
        return [match.value for match in match_list]


# noinspection PyUnusedLocal
def cmd_util_jsonpath(mixcli: MixCli, **kwargs: str) -> bool:
    """
    Default function wht util jsonpath command is called.

    :param mixcli: MixCli instance
    :param kwargs: ArgumentParser argumenets
    :return: True
    """
    in_json = kwargs['infile']
    qry_jsonpath = kwargs['jsonpath']
    result = jsonpath_on_jsonfile(jsonfile=in_json, jsonpath=qry_jsonpath)
    # Should we post-process the result by always using the first element in the list?
    ppr_1stelmnt = kwargs['first_element']
    end_result = None
    if not result:
        end_result = result
    elif ppr_1stelmnt is not None and ppr_1stelmnt is True:
        # We do this only when the result is non-empty list, e.g. there is matched value
        end_result = result[0]
    elif kwargs['postproc_expr']:
        # Should we post-process the result by evaluating a Python expression on query result?
        ppr_pyexpr = kwargs['postproc_expr']
        mixcli.debug(f'Post-processing python expr: {ppr_pyexpr}')
        try:
            pp_result = eval(ppr_pyexpr, {'r': result, 'json': json})
            mixcli.debug(f'Post-processing result with eval: {pp_result}')
            end_result = pp_result
        except Exception as ex:
            # raise RuntimeError(f'Error evaluating Python expr: {postproc_py}, on {json.dumps(result)}') from ex
            raise RuntimeError()
    else:
        end_result = result

    result_as_json = kwargs['json_result']
    if result_as_json:
        try:
            end_result = json.dumps(end_result)
        except Exception as ex:
            er_repr = end_result if isinstance(end_result, str) else repr(end_result)
            raise RuntimeError(f'Failed to cast result to Json: {er_repr}')
    else:
        end_result = end_result if isinstance(end_result, str) else repr(end_result)
    print(end_result)
    return True


@cmd_regcfg_func('util', 'jsonpath', 'Process JSON file with given JsonPath query and show result', cmd_util_jsonpath)
def config_argparser(argparser: ArgumentParser):
    """
    Command argument parser configuration.

    :param argparser: ArgumentParser instance for the command
    """
    argparser.formatter_class = RawTextHelpFormatter
    argparser.epilog = """There are considerations to generate and expect the end results from JsonPath queries.
    
    1. Python JsonPath-ng implementation always return query results a List. That being said, the actual query result
    expected by user would be element of the list, regardless more than often there is only one element in list. Users
    could use --first-element argument to have the command to take the first element in list as end result.
    
    2. Users on the other hand could use their own post-processing Python expressions, which are evaluated on JsonPath
    query result (the list), to prepare expected end results as command results. There are two reserved variable
    names in statements: "r" stands for the JsonPath query result (the list), and "json" stands for the json module
    should users need any Json processing. Please note the difference between Python expressions and statements.
    
    2.1 Another example on --postproc-expr: '--postproc-expr "r[0]"' has same result as --always-first.
    
    2.2 Please note that first-element argument and postproc-expr are mutually exclusive. 
    
    3. The query results from JsonPath-ng package are Python objects. Then this command uses print(repr(...)) statement
    to send content ot STDOUT. However the STDOUT-serialized content are not necessarily Json-compliant literals. For
    example, if query result is another Json object, "print(repr(...))" would produce dictionary representation where
    strings are quoted with single quotes, which are invalid for Json literals.
    
    3.1. To yield JsonPath query results, optionally with post-processing, as valid Json literals, use 
    --json-result argument.
    """
    argparser.add_argument('-i', '--infile', required=True, metavar='JSON_TO_PROC',
                           help='JSON file to be processed with JsonPath query')
    argparser.add_argument('-j', '--jsonpath', required=True, metavar='JSONPATH_QUERY',
                           help='JsonPath query to be run on input JSON file')
    arggrp_postproc = argparser.add_mutually_exclusive_group(required=False)
    arggrp_postproc.add_argument('-f', '--first-element', action='store_true', default=None,
                                 help='Return the first element in primitive JsonPath query result list as end result')
    arggrp_postproc.add_argument('-P', '--postproc-expr', type=str, required=False,
                                 metavar='POSTPROC_PYTHON_EXPRESSION',
                                 help='Python expression to be evaluated on query result. ' +
                                      'Evaluation result will be used as command end result.' +
                                      'Use "r" as reference of query result such as r[0]. ' +
                                      'Use "json" as json module.')
    argparser.add_argument('-J', '--json-result', action='store_true', help='Yield JsonPath result as Json object.')
