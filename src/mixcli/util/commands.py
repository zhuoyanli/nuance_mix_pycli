"""
Utility class for processing used immediately in registering MixCli commands
"""
from typing import Callable, Optional, Any, Union, Iterable, Dict, Tuple, Set
from types import FunctionType, ModuleType
from argparse import ArgumentParser
from inspect import getmembers, isfunction

from . import is_iterable
from ..command.cmd_group_config import CMD_GROUP_CONFIG as MIXCLI_CMD_GRP_CFG

DEFAULT_MIX_SERVICE_CRED_JSON = 'mix-client-credentials.json'
"""
Default name for Json file containing Mix user client credentials
"""
DEFAULT_MIX_API_TOKEN_FILE = 'mix-api-token'
"""
Default name for plain text file containing assigned Mix auth token as literal string
"""


def wrap_help_call(argparser, id_for_which: str):
    """
    Wrap the print_help method call from ArgumentParser instance for target of 'func' in set_defaults
    :param argparser: ArgumentParser instance
    :param id_for_which: str, an arbitrary string that is set with 'which' attribute in the namespace from parse_args
    :return: None
    """
    # noinspection PyUnusedLocal
    def call_prhelp(*argp: Any, **kwargs: ArgumentParser):
        kwargs['parser_inst'].print_help()

    argparser.set_defaults(which=id_for_which,
                           parser_inst=argparser,
                           func=call_prhelp)
    # func=lambda p, **kwg: kwg['parser_inst'].print_help())


Lambda_Decor = Callable[[], ArgumentParser]
ArgCmdDefFunction = Callable[['MixCli', Any], None]


class MixCliCmdRegister:
    """
    Utility class to produce decorator functions
    """

    def __init__(self, cmd_grp_cfg):
        self._cmd_grp_cfg = cmd_grp_cfg
        self._root_argparser = None
        self._cmd_group_container = None
        self._cmd_mod_to_reg_func = dict()
        self._cmd_grp_name_to_subparser_action = dict()
        self._registered_grp: Set[str] = set()
        self._cmd_grp_cmd_to_arg_parser: Dict[Tuple, ArgumentParser] = dict()
        self._cmd_grp_cmd_to_docstr: Dict[Tuple, str] = dict()

    @property
    def root_argparser(self):
        return self._root_argparser

    @root_argparser.setter
    def root_argparser(self, new_root_argparser: ArgumentParser):
        """
        Set the root cmd arg parser for MixCli
        :param new_root_argparser: The top ArgumentParser instance
        :return:
        """
        self._root_argparser = new_root_argparser
        # adding extensions of sub-parsers
        self._cmd_group_container = new_root_argparser.add_subparsers(help="Sub-command groups for MixCli")

    def get_cmd_id(self, cmd_group_name: str, cmd_name: str) -> Optional[str]:
        """
        Get the internal ID for command in command group
        :param cmd_group_name: Name of command group
        :param cmd_name: name of command
        :return:
        """
        if cmd_group_name not in self._registered_grp:
            return None
        return f'{cmd_group_name}__{cmd_name}'

    def is_cmd_module_registered(self, cmd_mod_name: str) -> bool:
        """
        :param cmd_mod_name: str, package or module name
        :return: True if cmd_mod_name is already in _cmd_mod_to_reg_func, False otherwise
        """
        return cmd_mod_name in self._cmd_mod_to_reg_func

    def get_cmd_group_subparser_action(self, cmd_group_name: str) -> Optional[ArgumentParser]:
        """
        Get the cmd_argparser container for the command group with name
        :param cmd_group_name: str, name of command group
        :return:
        """
        if cmd_group_name in self._cmd_grp_name_to_subparser_action:
            return self._cmd_grp_name_to_subparser_action[cmd_group_name]
        return None

    def register_cmd_group(self, cmd_group_name: str, cmd_group_desc: str):
        """
        Register a command group with meta
        :param cmd_group_name: str, name of command group
        :param cmd_group_desc: str, descriptive string for command group
        :return: None
        """
        if not self._cmd_group_container:
            raise RuntimeError('If you are importing command module, must create MixCli instance first!')
        parser_cmdgrp = self._cmd_group_container.add_parser(cmd_group_name, help=cmd_group_desc)
        wrap_help_call(parser_cmdgrp, cmd_group_name)
        # grp_subparser_action = parser_cmdgrp.add_subparsers(help=f"Sub-parsers for {cmd_group_name} group")
        grp_subparser_action = parser_cmdgrp.add_subparsers(help=self._cmd_grp_cfg[cmd_group_name])
        # print(f'register_cmd_group: adding {cmd_group_name}')
        self._cmd_grp_name_to_subparser_action[cmd_group_name] = grp_subparser_action

    def register_cmd(self, cmd_group_name: str, cmd_name: str, cmd_desc: str, cmd_deffunc: ArgCmdDefFunction):
        """
        Register a MixCli concrete command with meta
        :param cmd_group_name: str, name of command group to which the command belongs
        :param cmd_name: str, name of command, used in command argument parser
        :param cmd_desc: str, descriptive string of the command
        :param cmd_deffunc: str, the default function to be called when command is used
        :return:
        """
        if self.get_cmd_group_subparser_action(cmd_group_name) is None:
            raise ValueError(f'Command group {cmd_group_name} undefined')

        self._registered_grp.add(cmd_group_name)

        """
        Decorator on command register functions
        :param cmd_name: str, Name of MixCli command, used by argument cmd_argparser to process arguments
        :param cmd_desc: str, Descriptive messages on the command
        :param cmd_deffunc: function, the default function to be called when the command is used. The function
        will be called with a positional parameter, a MixCli instance, and followed by keyword arguments.
        :return:
        """

        def __cmd_register(cmd_register_func: FunctionType) -> Lambda_Decor:
            """
            Decorator for the command register function
            :param cmd_register_func: Function object, the command register function on which cmd_register is applied.
            :return: The wrapper function wrap_cmd_register_func
            """
            func_name: str = cmd_register_func.__name__
            func_mod_nm: str = cmd_register_func.__module__
            cmd_id = self.get_cmd_id(cmd_group_name, cmd_name)
            cmd_group_subparser_action = self._cmd_grp_name_to_subparser_action[cmd_group_name]
            # we must only store the names, then later call the functions by
            # func_inst = getattr(module_inst, func_name)
            # func_inst()
            # this way the decorations would be activated
            # if we store the immediate function instances here and call them, the decorations would NOT
            # be activated
            self._cmd_mod_to_reg_func[func_mod_nm] = func_name

            # noinspection PyUnusedLocal
            def wrap_cmd_register_func() -> ArgumentParser:
                """
                Wrapper on the command's register function.
                :return: An ArgumentParser-like instance by calling .add_parser on the special action object
                return ArgumentParser.add_subparsers()
                """
                # print(f'wrap_cmd_register_func: {cmd_name}')
                arg_parser = cmd_group_subparser_action.add_parser(cmd_name, help=cmd_desc, description=cmd_desc)
                cmd_register_func(arg_parser)
                arg_parser.set_defaults(parser_inst=arg_parser, which=cmd_id, func=cmd_deffunc)
                # add this to the dict
                tuple_cmd_grp_cmd = (cmd_group_name, cmd_name)
                self._cmd_grp_cmd_to_arg_parser[tuple_cmd_grp_cmd] = arg_parser
                self._cmd_grp_cmd_to_docstr[tuple_cmd_grp_cmd] = func_mod_nm
                return arg_parser

            # print(f'Decorating function {func_name} from {func_mod}')
            return wrap_cmd_register_func
        return __cmd_register

    def setup_cmd_argparser(self, cmd_impl: ModuleType):
        """
        Helper method to create a ArgumentParser command from the command implementation package or module
        :param cmd_impl: a package or module, implementation of a concrete processing command
        :return: None
        """
        # print(f'setup_cmd_argparser: {cmd_group_name}, {cmd_impl.__name__}')
        register_cmd_name = self.get_cmd_register_func(cmd_impl.__name__)
        if register_cmd_name:
            register_cmd_func_wrapper = getattr(cmd_impl, register_cmd_name)
            register_cmd_func_wrapper()
        else:
            raise ValueError('Module not yet registered for command, import mixcli.command package first!: ' +
                             f'{cmd_impl.__name__}')

    def get_cmd_register_func(self, cmd_module: str) -> Optional[str]:
        """
        :param cmd_module: str, Name of the module/package that implements the command
        :return: None if no stored command register function for the module by decorator, the function otherwise
        """
        if cmd_module in self._cmd_mod_to_reg_func:
            return self._cmd_mod_to_reg_func[cmd_module]
        else:
            return None

    def get_cmd_arg_parser(self, cmd_group: str, cmd: str) -> Optional[ArgumentParser]:
        """
        Get the ArgumentParser instance associated with the MixCli command, identified
        by command group and command names
        :param cmd_group: Command group name
        :param cmd: Command name
        :return: The ArgumentParser instance associated with the command, or None if that command is not registered
        """
        tuple_cmd_grp_cmd = (cmd_group, cmd)
        if tuple_cmd_grp_cmd in self._cmd_grp_cmd_to_arg_parser:
            return self._cmd_grp_cmd_to_arg_parser[tuple_cmd_grp_cmd]
        else:
            return None


_cmd_register = MixCliCmdRegister(MIXCLI_CMD_GRP_CFG)


def get_cmd_id(cmd_group_name: str, cmd_name: str) -> Optional[str]:
    """
    Get the command internal id
    :param cmd_group_name: str, command group name
    :param cmd_name: str, command name
    :return: None if command group with name cmd_group_name not existing, or command with name cmd_name not in that
    command group. Str for the ID otherwise.
    """
    return _cmd_register.get_cmd_id(cmd_group_name, cmd_name)


def register_root_argparser(root_argparser: ArgumentParser):
    """
    Register the root ArgumentParser
    :param root_argparser: ArgumentParser instance
    :return: None
    """
    _cmd_register.root_argparser = root_argparser


def register_cmd_module(cmd_mod: Union[Iterable[ModuleType], ModuleType]):
    """
    Register a command with the implementation module. The register function in the module which is decorated
    with @register_cmd will be used to complete the command registration and prepation
    :param cmd_mod: Union[iterable, package, module], the package or module instance that implements the command,
    or an iterable of such package/module instances.
    :return: None
    """
    if is_iterable(cmd_mod):
        for cm in cmd_mod:
            for mem_func in getmembers(cm, isfunction):
                if mem_func[1] == cmd_regcfg_func:
                    _cmd_register.setup_cmd_argparser(cm)
                    break
    else:
        _cmd_register.setup_cmd_argparser(cmd_mod)


def register_cmd_group(cmd_group_name: str, cmd_group_desc: str):
    """
    Register a command group with meta
    :param cmd_group_name: str, name of command group
    :param cmd_group_desc: str, description of command group
    :return: None
    """
    _cmd_register.register_cmd_group(cmd_group_name, cmd_group_desc)


# what happens what the following decoration is done
# @register_cmd(cmd_name, cmd_desc, cmd_deffunc):
# def some_reg_func
#
# _cmd_register.register(cmd_name_1, cmd_desc_1, cmd_deffunc_1) ->  __cmd_register
# __cmd_register(some_reg_func) -> processing within __cmd_register --> wrap_cmd_register_func
#
# during this process, the following is already determined:
# cmd_id_1 = get_cmd_id(__cmd_register.__module__, cmd_name_1), and
# _cmd_register._cmd_mod_to_reg_func[__cmd_register.__module__] = cmd_register_func.__name__
#
# so when this call takes place in visual code: some_reg_func(cmd_parser_container), what happens are
# wrap_cmd_register_func(cmd_parser_container), then what happens are
#
# cmd_argparser = cmd_parser_container.add_parser(cmd_name_1, help=cmd_desc_1)
# __cmd_register(cmd_argparser)
# cmd_argparser.set_defaults(parser_inst=cmd_argparser, which=cmd_id_1, func=cmd_deffunc_1)
# return cmd_argparser
def cmd_regcfg_func(cmd_group_name: str, cmd_name: str, cmd_desc: str, cmd_deffunc: Callable) -> Callable:
    """
    The decorator
    :param cmd_group_name: Name of command group for the new command
    :param cmd_name: Name of command for the new command
    :param cmd_desc: Descriptive message for the new command
    :param cmd_deffunc: Default function to be called when the new command is called
    :return:
    """
    return _cmd_register.register_cmd(cmd_group_name, cmd_name, cmd_desc, cmd_deffunc)


def get_cmd_argparser(cmd_group: str, cmd: str) -> Optional[ArgumentParser]:
    """
    Get the ArgumentParser instance associated with the MixCli command, identified by cmd group and cmd names
    :param cmd_group: Name of command groupe
    :param cmd: Name of command
    :return: The ArgumentParser instance
    """
    return _cmd_register.get_cmd_arg_parser(cmd_group, cmd)
