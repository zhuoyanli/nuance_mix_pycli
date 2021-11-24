"""
Package to handle setup of command line argument processing for Mix API Cli
"""
from ..util.commands import register_root_argparser, register_cmd_group, register_cmd_module

_cmd_registered = False


def register_commands():
    global _cmd_registered
    if _cmd_registered:
        return
    from .cmd_group_config import CMD_GROUP_CONFIG as MIXCLI_CMD_GRP_CFG
    # we first need to register all the command groups, otherwise the decorator-based command registration
    # from the command implementation modules will failed with exception that command group has not been registered.
    for cmd_grp_name, cmd_grp_desc in MIXCLI_CMD_GRP_CFG.items():
        register_cmd_group(cmd_group_name=cmd_grp_name, cmd_group_desc=cmd_grp_desc)
    from .cmd_config import get_cmd_modules
    for cmd_module in get_cmd_modules():
        # we donot use 'map' here because it is lazy evaluation
        register_cmd_module(cmd_module)
    _cmd_registered = True


def config_argparser_for_commands(root_argparser):
    register_root_argparser(root_argparser)
    register_commands()

