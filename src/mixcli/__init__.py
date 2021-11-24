import codecs
import json
import sys
import os
import os.path
from argparse import ArgumentParser
from collections import namedtuple
from typing import Union, Callable, Optional, Dict

from .command import config_argparser_for_commands
from .util.auth.pyreq_auth import PyReqMixApiAuthHandler
from .util.commands import get_cmd_id
from .util.requests import HTTPRequestHandler, PyRequestsRunner, DEFAULT_API_HOST
from .util.logging import get_logger, Loggable, SUPPORTED_LOG_LEVELS

ENVAR_LOG_LEVEL = "MIXCLI_LOGLEVEL"
DEFAULT_JOB_WAITFOR_INTERVAL = 60
MixCli_CmdArgs_ProcFunc = Callable[['MixCli', ArgumentParser, namedtuple], bool]


def create_mixcli_argparser():
    """
    Create command line cmd_argparser for mixcli
    :return:
    """
    parser = ArgumentParser(prog="mixcli", description="Central Research Python Mix API Cli")

    grp_mix3_token = parser.add_mutually_exclusive_group(required=False)
    grp_mix3_token.add_argument('--token', metavar='TOKEN_STRING',
                                help="The literal Mix API auth token string")
    grp_mix3_token.add_argument('--token-file', metavar='TEXT_FILE_WITH_TOKEN_STRING',
                                help="Plain text file containing the literal Mix API auth token string")
    grp_mix3_token.add_argument('--client-cred', metavar='JSON_WITH_CLIENT_CREDENTIALS',
                                help="Json file containing Mix user client credentials to request API auth tokens")
    parser.add_argument('--host', help='Host against which the Mix3 API should be run')
    mutexgrp_verbose = parser.add_mutually_exclusive_group(required=False)
    mutexgrp_verbose.add_argument('-q', '--quiet', action='store_true',
                                  help='Skip display of descriptive message should tasks are completed successfully')
    mutexgrp_verbose.add_argument('-d', '--debug', action='store_true',
                                  help="Produce most verbose output by setting logging level to DEBUG")
    parser.add_argument('-T', '--token-in-log', action='store_true', default=False, required=False,
                        help='Show auth token string in logging. By default it is truncated.')

    return parser


class MixCli(Loggable):
    """
    The concrete class to operate on Mix (HTTP) APIs with Curl subprocess calls
    """
    _mixcli_inst: 'MixCli' = None

    def __init__(self, host=None, mix_job_waitfor_intvl=None):
        Loggable.__init__(self, self.__name__)
        # Mix authorization handler
        # self._auth_hdlr = CurlMixApiAuthHandler(mixcli=self)

        self._auth_hdlr = PyReqMixApiAuthHandler(mixcli=self)
        # HOST for Mix API HTTP requests
        if host:
            self._host = host
        else:
            self._host = DEFAULT_API_HOST

        # get the PyRequestsRunner instance
        self._req_runner = PyRequestsRunner(self._auth_hdlr, host=host)

        # TIMEOUT for wait time on Mix submitted jobs
        if mix_job_waitfor_intvl:
            self._job_waitfor_intvl = mix_job_waitfor_intvl
        else:
            self._job_waitfor_intvl = DEFAULT_JOB_WAITFOR_INTERVAL

        self._cmd_argparser: Optional[ArgumentParser] = None
        self._cmd_func: Optional[MixCli_CmdArgs_ProcFunc] = None

        self._cmd_argparser = None
        self._cmd_func = None
        self.register_commands()

        # keep track of client credential config file if used
        self._client_cred_cfg: Optional[str] = None
        self._client_cred_cfg_js: Optional[Dict] = None

    @property
    def __name__(self):
        return "MixCli"

    def set_level(self, new_level: Union[str, int]):
        Loggable.set_level(self, new_level)
        self.auth_handler.set_level(new_level)
        self.httpreq_handler.set_level(new_level)

    @property
    def client_cred_cfg(self) -> Optional[str]:
        """
        Return the path to client credential config JSON if used for this MixCli instance

        :return: path to client credential config JSON, if used, or None
        """
        return self._client_cred_cfg

    @client_cred_cfg.setter
    def client_cred_cfg(self, new_cfg_path: str):
        if not os.path.isfile(new_cfg_path):
            raise RuntimeError(f'Invalid client credential JSON: {new_cfg_path}')
        try:
            with codecs.open(new_cfg_path, 'r', 'utf-8') as fhi_clicredcfg:
                # try to parse as json
                self._client_cred_cfg = new_cfg_path
                self._client_cred_cfg_js = json.load(fhi_clicredcfg)
        except Exception as ex:
            raise RuntimeError(f'Not a valid JSON file as client credential: {new_cfg_path}') from ex

    def config_auth_handler(self, token_str: Optional[str] = None, token_file: Optional[str] = None,
                            service_cred: Optional[str] = None):
        """
        Delegator function for the config function from self._auth_hdlr

        :param token_str: Literal auth token string
        :param token_file: Path to plain text file containing aut token string
        :param service_cred: Path to JSON file with client service credential info.
        :return:
        """
        self._auth_hdlr.config(token_str=token_str, token_file=token_file, client_cred_json=service_cred)

    @property
    def auth_handler(self):
        """
        Get the bound MixApiAuthHandler instance
        :return: MixApiAuthHandler instance
        """
        return self._auth_hdlr

    @auth_handler.setter
    def auth_handler(self, new_auth_hdlr):
        """
        Set the bound MixApiAuthHandler instance
        :param new_auth_hdlr: MixApiAuthHandler instance
        :return: None
        """
        self._auth_hdlr = new_auth_hdlr

    @property
    def httpreq_handler(self) -> HTTPRequestHandler:
        return self._req_runner

    def client_cred_auth(self, client_id, service_secret):
        """
        Do Mix client credentials authorization for this MixCli
        :param client_id: Mix user client ID
        :param service_secret: Mix user service secret
        :return:
        """
        self._auth_hdlr.client_cred_auth(self, client_id=client_id, service_secret=service_secret)

    @property
    def auth_token(self):
        return self._auth_hdlr.token

    @property
    def client_auth_token(self):
        return self._auth_hdlr.client_auth_token

    @client_auth_token.setter
    def client_auth_token(self, new_cli_auth_token):
        self._auth_hdlr.client_auth_token = new_cli_auth_token

    def error_exit(self, err_msg: str, exit_code: int = 1):
        """
        Log a message with ERROR level and then exit program with exit code
        :param err_msg: Message to be logged on ERROR level
        :param exit_code: Exit code to be used, default to 1
        :return:
        """
        self.error(err_msg=err_msg)
        sys.exit(exit_code)

    def register_commands(self):
        if self.cmd_argparser is not None:
            return
        parser = create_mixcli_argparser()
        config_argparser_for_commands(parser)
        self.cmd_argparser = parser
        self.cmd_func = self.proc_cmd_args

    @property
    def cmd_argparser(self) -> Optional[ArgumentParser]:
        """
        Get the ArgumentParser instance bound with MixCli instance
        :return: the ArgumentParser instance bound with MixCli instance
        """
        return self._cmd_argparser

    @cmd_argparser.setter
    def cmd_argparser(self, new_argparser: ArgumentParser):
        """
        Set the ArgumentParser instance bound with MixCli instance
        :param new_argparser: The new ArgumentParser instance bound with MixCli instance
        :return:
        """
        self._cmd_argparser = new_argparser

    @property
    def cmd_func(self) -> Optional[MixCli_CmdArgs_ProcFunc]:
        """
        Get the process function that process ArgumentParser parsed arguments to run MixCli. The process function
        should take a MixCli instance, an ArgumentParser instance, and ArgumentParser parsed namespace as parameters,
        and return a boolean.
        :return: the process function that process ArgumentParser parsed arguments to run MixCli
        """
        return self._cmd_func

    @cmd_func.setter
    def cmd_func(self, new_cmdfunc: MixCli_CmdArgs_ProcFunc):
        """
        Set the process function that process ArgumentParser parsed arguments to run MixCli. The process function
        should take a MixCli instance, an ArgumentParser instance, and ArgumentParser parsed namespace as parameters,
        and return a boolean.
        :param new_cmdfunc: the process function that process ArgumentParser parsed arguments to run MixCli
        :return: the process function that process ArgumentParser parsed arguments to run MixCli
        """
        self._cmd_func = new_cmdfunc

    def do_mixauth(self, **kwargs):
        if not self.auth_handler:
            raise RuntimeError('MixCli instance not yet have auth handler configured')
        if 'client_id' in kwargs and 'service_secret' in kwargs:
            self.auth_handler.client_cred_auth(self, **kwargs)
        else:
            self.auth_handler.auth_with_cmd_sources(**kwargs)

    def auth_with_cmd_sources(self, token_str: Optional[str] = None, token_file: Optional[str] = None,
                              client_cred_file: Optional[str] = None):
        # setup auth handler
        # are we already authorized?
        # yes, we only redo that if arguments explicitly specified
        if not self._auth_hdlr.token:
            (used_tok, used_tokf, used_clicred) = self._auth_hdlr.\
                auth_with_cmd_sources(token_str=token_str, token_file=token_file, client_cred_file=client_cred_file)
            # keep track of the client credential file
            if used_clicred:
                self.client_cred_cfg = used_clicred
                self.debug(f'Setting up client credential file: {used_clicred}')

    def proc_cmd_args(self, argparser: ArgumentParser, cmd_args: namedtuple) -> bool:
        """
        Process parsed arguments from MixCli ArgumentParser instance
        :param argparser: The ArgumentParser instance for the specific command
        :param cmd_args:
        :return:
        """
        if hasattr(cmd_args, 'debug') and cmd_args.debug:
            self.set_level('DEBUG')
        elif hasattr(cmd_args, 'quiet') and cmd_args.quiet:
            self.set_level('ERROR')
        elif ENVAR_LOG_LEVEL in os.environ:
            # we check if the environment variable is set
            envar_loglevel_val = os.environ[ENVAR_LOG_LEVEL]
            if envar_loglevel_val in SUPPORTED_LOG_LEVELS:
                self.info(f'Setting log level from env variable {ENVAR_LOG_LEVEL}: {envar_loglevel_val}')
                self.set_level(envar_loglevel_val)

        if not hasattr(cmd_args, 'func'):
            argparser.print_help()
            sys.exit()

        if cmd_args.which == get_cmd_id('auth', 'clicent'):
            # we know that we do not need tokens for auth client command
            kwargs = vars(cmd_args)
            cmd_args.func(self, **kwargs)
            return True

        if hasattr(cmd_args, 'token_in_log'):
            self.httpreq_handler.no_token_log = not cmd_args.token_in_log

        self.auth_with_cmd_sources(token_str=cmd_args.token, token_file=cmd_args.token_file,
                                   client_cred_file=cmd_args.client_cred)

        kwargs = vars(cmd_args)
        rv = cmd_args.func(self, **kwargs)
        if rv is not False:
            return True

    def run_cmd(self, *cmd: str):
        """
        Run command as list of command line arguments. This is equivalent to python -m mixcli <cmd>
        :param cmd: Variable arguments of strings.
        :return:
        """
        if not self._cmd_argparser:
            raise RuntimeError('MixCli not yet have ArgumentParser configured')
        args = self._cmd_argparser.parse_args(cmd)
        self.proc_cmd_args(self._cmd_argparser, args)
        return True

    @classmethod
    def get_cli(cls) -> 'MixCli':
        return cls._mixcli_inst


MixCli._mixcli_inst = MixCli()
