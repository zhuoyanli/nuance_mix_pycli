"""
mixcli example cmd_as_module command
This package shows how to add new mixcli concrete command as packages
"""

# Do not forget to add the imported package to the list of concrete commands of command group,
# in dictionary CMD_GROUP_SETUP of mixcli.command.__init__.py

# Please pay attention to the relative import, the level for modules is different with that for packages.
# Other than this, implementing a concrete processing command is largely same with modules as with packages.
from argparse import ArgumentParser

from mixcli import MixCli
from mixcli.util.requests import HTTPRequestHandler
# from mixcli.util.commands import cmd_regcfg_func


# noinspection PyUnusedLocal
# (suppress PyCharm warning)
def example_cmd_as_module(httpreq_handler: HTTPRequestHandler):
    """
    We recommend to put the actual processing that supports the command in standalone function, so as that
    the processing can be re-used by other modules/codes in more convenient way
    :param httpreq_handler: As all the operations against Mix APIs are done by Python requests package,
    we expect to have CurlRunner instances here
    :return:
    """
    httpreq_handler.info("example command group cmd_as_module command actual processing")


# noinspection PyUnusedLocal
def cmd_example_cmd_as_module(mixcli: MixCli, **kwargs):
    """
    This function would be called by the processing of ArgumentParser. The contract is the positional argument
    would be a MixCli instance and the rest are passed as keyword arguments.
    We recommend to name this function as cmd_<name_of_group>_<name_of_command>
    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments
    :return:
    """
    mixcli.info("example command group cmd_as_module ArgumentParser support function")
    example_cmd_as_module(mixcli.httpreq_handler)
    return True


# noinspection PyUnusedLocal
# @cmd_regcfg_func('example', 'cmd_as_mod', 'Example of implementing commands as modules', cmd_example_cmd_as_module)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    # cmd_argparser.add_argument(...)
    pass
