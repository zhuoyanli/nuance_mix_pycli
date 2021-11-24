"""
MixCli **ns** command **group** list command

This command would list all affiliated namespaces for the user account represented by auth token.
Affiliated namespace is one namespace of which the user account is a member.
"""
import json
from argparse import ArgumentParser
from typing import List, Dict, Union
from mixcli import MixCli
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import write_result_outfile


def pyreq_list_affiliated_ns(httpreq_handler: HTTPRequestHandler) -> List[Dict[str, Union[int, str]]]:
    """
    List all affiliated namespaces for user account by sending requests to API endpoint with Python 'requests' package.
    API endpoint ::
        GET /bolt/namespaces

    :param httpreq_handler: A HTTPRequestHandler instance
    :return: A list of Json object(s). Each Json object conveys the meta info for one affiliated namespace.
    """

    # it is also possible to use the following endpoint
    # f'/admin/admin-api/namespaces?sort=%2Bid&limit=50&string_query={quoted_ns_name}', according to Merlin
    # this endpoint would only return the namespaces of which the current user is a member
    api_endpoint = '/bolt/namespaces'
    resp = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, default_headers=True, json_resp=True)
    """
    Example payload of result ::
        {
          "data": [
            {
              "id": 1, 
              "name": "Nuance Communications, Inc.", 
              "path": "nuance", "url": "www.nuance.com", 
              "is_personal": false, "accurate_model_enabled": false, 
              "is_member": true
            },
            ...
          ]
        }
    """
    # do some empirical sanity checks
    if 'data' not in resp:
        raise ValueError(f'"data" field not found in CURL command result: {json.dumps(resp)}')
    if not isinstance(resp['data'], list) or not resp['data']:
        raise ValueError(f'"data" field is not non-empty list: {json.dumps(resp)}')
    return resp['data']


def list_affiliated_ns(mixcli: MixCli) -> List[Dict[str, Union[int, str]]]:
    """
    List all affiliated naemspaces for user account.

    :param mixcli: The MixCli instance
    :return: A list of Json object(s). Each Json object conveys the meta info for one affiliated namespace.
    """
    return pyreq_list_affiliated_ns(mixcli.httpreq_handler)


def cmd_ns_list(mixcli: MixCli, **kwargs: Union[bool, str]):
    """
    Default function when ns list command is called.

    :param mixcli:  A MixCli instance
    :param kwargs:  keyword arguments from command-line arguments
    :return: None
    """
    result: List[Dict[str, Union[int, str]]] = list_affiliated_ns(mixcli)
    need_tsv = kwargs['tsv']
    out_file = kwargs['out_file']
    out_content_str = ''
    if need_tsv:
        out_content = []
        for ns_meta in result:
            out_content.append('\t'.join([f'{k}\t{v}' for k, v in ns_meta.items()]))
        out_content_str = '\n'.join(out_content)

    if out_file:
        if not need_tsv:
            write_result_outfile(content=json.dumps(result), out_file=out_file)
        else:
            write_result_outfile(out_content_str, out_file=out_file, is_json=False)
        mixcli.info(f'Namespace list successfully written to {out_file}')
    else:
        if not need_tsv:
            mixcli.info('namespace list json: ' + json.dumps(result))
        else:
            mixcli.info('namespace list: \n' + out_content_str)
    return True


@cmd_regcfg_func('ns', 'list', 'List all affiliated namespace(s) for the user represented by auth token', cmd_ns_list)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-t', '--tsv', action='store_true',
                               help='Organize result in TSV format')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

