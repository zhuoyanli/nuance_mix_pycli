"""
MixCli **sys** command group **version** command.

This command will show Mix platform versions. It is actually useful for two aspects: Firstly serves as functional
test on the end-to-end process of MixCli, i.e. acquiring auth tokens, sending API requests, receiving response
payloads, and process them; secondly, if MixCli is run with some preset authorization tokens, this command can serve as
validation process as we can probe Mix API services with those tokens to see if they are valid.
"""
from argparse import ArgumentParser
from typing import Dict, Union
from mixcli import MixCli
from mixcli.util.requests import HTTPRequestHandler
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import write_result_outfile


def pyreq_mix_sys_version(httpreq_handler: HTTPRequestHandler) -> Dict:
    """
    Query Mix platform/system version by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        GET /api/v2/version.

    :param httpreq_handler: a HTTPRequestHandler instance
    :return: The response payload in JSON
    """
    # by default we use .GET_METHOD as HTTP method
    api_endpoint = 'api/v2/version'
    resp = httpreq_handler.request(url=api_endpoint, default_headers=True, json_resp=True)
    return resp


def mix_sys_version(mixcli: MixCli) -> Dict:
    """
    Query Mix platform/system version.

    :param mixcli: a MixCli instance
    :return: json, the query result
    """
    # return curl_mix_sys_version(mixcli.httpreq_handler)
    return pyreq_mix_sys_version(mixcli.httpreq_handler)


# noinspection PyUnusedLocal
def cmd_sys_version(mixcli, **kwargs: Union[bool, str]):
    """
    Default function when MixCli sys version command is called. Check Mix platform system version.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: json, command result in Json
    """
    """
    example response payload Json:
    {'mix.env': 'us', 'mix.version': '3.5.9'}
    """
    json_result = mix_sys_version(mixcli)
    mixcli.debug('Successfully retrieved system version')
    out_file = kwargs['out_file']
    if not out_file:
        mixcli.info(json_result)
    else:
        write_result_outfile(content=json_result, out_file=out_file, is_json=True, logger=mixcli)
    return True


# noinspection PyUnusedLocal
@cmd_regcfg_func('sys', 'version', 'Check Mix version', cmd_sys_version)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-o', '--out-file', metavar='OUTPUT_FILE', help='Write command result to output file')
