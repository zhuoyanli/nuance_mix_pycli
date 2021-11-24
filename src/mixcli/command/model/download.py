"""
module for model download command, command to download artifacts from deployed models
"""
from argparse import ArgumentParser

from mixcli import MixCli
# from mixcli.util.commands import cmd_regcfg_func


# noinspection PyUnusedLocal
def model_dl(mixcli: MixCli, **kwargs):
    mixcli.info('Placeholder for command to download model artifacts through gRPC')


# noinspection PyUnusedLocal
def cmd_model_download(mixcli: MixCli, **kwargs):
    """
    Default function when MixCli model download command is called
    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command line
    :return: None
    """
    mixcli.info('Placeholder for command to download model artifacts through gRPC')
    model_dl(mixcli, **kwargs)


# noinspection PyUnusedLocal
# @cmd_regcfg_func('model', 'download', 'Download artifacts of deployed models through gRPC', cmd_model_download)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Command cmd_argparser creation and registration function
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    pass
