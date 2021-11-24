"""
MixCli **auth** command group **client** command.

This command performs the Oauth client credential authorization workflow, as instructed in Mix official documentation.
It is not necessary to run this command before running any other MixCli commands. Such authorization process will be
run behind the scene should MixCli commands need authorization tokens.

This command is mostly useful for 1) generating working Mix API auth tokens for the uses of other programs; 2) triaging
if the client credentials from users are working.
"""
import os
import json
from argparse import ArgumentParser
from typing import Union
from mixcli import MixCli
from mixcli.util import OutWriter
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.auth import client_auth_with_default_json, client_auth_with_json


_TOKEN_OUTTYPE_STR = 'str'
"""Output Mix authorization tokens as literal strings"""
_TOKEN_OUTTYPE_JSON = 'json'
"""Output Mix authorization tokens as JSON literal with meta info like expiration time"""
_TOKEN_OUTTYPES = [_TOKEN_OUTTYPE_STR, _TOKEN_OUTTYPE_JSON]
"""List of supported Mix auth token output types for command line arguments."""


# as the curl_client_cred_auth function is also used by other modules, we chose to
# put it in auth module instead of this command implementation module
def cmd_auth_client(mixcli: MixCli, **kwargs: Union[ArgumentParser, str]):
    """
    Default command when MixCli auth client command is called. This function generates Mix auth tokens
    with client id and service secret, then either display it in STDOUT or write it to file.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    # user should use either cred-json argument alone, or the two arguments 'client-id' and 'service-secret' together
    argparser = kwargs['parser_inst']
    if not kwargs['client_cred'] and not kwargs['client_id'] and not kwargs['service_secret']:
        suc = client_auth_with_default_json(mixcli)
        if not suc:
            argparser.print_help()
            raise ValueError('Must specify either client-cred or {client-id, service-secret}')
        (client_id, srvc_sec) = suc
    elif kwargs['client_cred'] and (kwargs['client_id'] or kwargs['service_secret']):
        argparser.print_help()
        raise ValueError('Can only use client-cred or {client-id, service-secret}')
    elif kwargs['client_cred']:
        path_client_cred_json = kwargs['client_cred']
        if not os.path.isfile(path_client_cred_json):
            raise FileNotFoundError(f"Client credentials Json {path_client_cred_json} not found")
        (client_id, srvc_sec) = client_auth_with_json(path_client_cred_json, logger=mixcli)
    else:
        if not kwargs['client_id'] or not kwargs['service_secret']:
            argparser.print_help()
            raise ValueError('Must specify both client-id and service-secret')
        client_id = kwargs['client_id']
        srvc_sec = kwargs['service_secret']
    out_file = OutWriter.FN_STDOUT
    if 'out_file' in kwargs and kwargs['out_file']:
        out_file = kwargs['out_file']
    mixcli.client_cred_auth(client_id, srvc_sec)
    try:
        with OutWriter.open(out_file) as fho_jsontok:
            if kwargs['out_type'] == 'str':
                fho_jsontok.write(mixcli.client_auth_token.token, eofl='\n')
            else:
                fho_jsontok.write(json.dumps(mixcli.client_auth_token.json_token, indent=2), eofl='\n')
        if out_file != OutWriter.FN_STDOUT:
            mixcli.info(f'Auth token successfully written to {out_file}')
        return True
    except Exception as ex:
        mixcli.error(f'Error writing generated token to {out_file}')
        raise ex


@cmd_regcfg_func('auth', 'client', 'Generate Mix auth tokens with client credentials', cmd_auth_client)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('--client-id', metavar='MIX_CLIENT_ID', required=False,
                               help='Mix user client id, must used with service-secret, not with client-cred')
    cmd_argparser.add_argument('--service-secret', metavar='MIX_SERVICE_SECRET', required=False,
                               help='Mix user service secret, must used with client-id, not with client-cred')
    cmd_argparser.add_argument('--out-type', choices=_TOKEN_OUTTYPES,
                               default=_TOKEN_OUTTYPE_STR, metavar='OUTPUT_TOKEN_TYPE',
                               help='Type to output, ' +
                                    f'"{_TOKEN_OUTTYPE_STR}" for just token string, ' +
                                    f'"{_TOKEN_OUTTYPE_JSON}" for complete Json. ' +
                                    f'By default {_TOKEN_OUTTYPE_STR}.')
    cmd_argparser.add_argument('--out-file', default=OutWriter.FN_STDOUT, metavar='OUTPUT_TOKEN_FILE',
                               help='Output file for writing token, if skipped output to stdout')
