"""
MixCli **project** command group **reset** command.

This command immediately reset all the models of a Mix project, referred by IDs.

The author has NO ideas whether or not Mix users with privileges such as Global Admin and Global PS would be able to
arbitrary Mix projects with this API, which implies great potential risks on any input errors for specifying project
IDs. For safe-guard purpose this command, and its implementation, asks for confirmation project names as input. The
confirmation names must exactly match the names extracted from meta info, which are in turn retrieved with project IDs.
"""
from argparse import ArgumentParser
from typing import Union

from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD
from .get import get_project_meta
from mixcli.util.cmd_helper import assert_id_int


def pyreq_project_reset(httpreq_handler: HTTPRequestHandler, project_id: int) -> bool:
    """
    Reset a Mix project with ID project_id by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        POST /api/v2/projects/{project_id}/.reset.

    :param httpreq_handler: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :return: True
    """
    api_endpoint = f'api/v2/projects/{project_id}/.reset'
    _ = httpreq_handler.request(url=api_endpoint, method=POST_METHOD, default_headers=True)
    return True


def project_reset(mixcli: MixCli, project_id: Union[str, int], confirm_project_name: str) -> bool:
    """
    Reset a Mix project with ID project_id by POST /api/v2/projects/{project_id}/.reset
    :param mixcli: MixCli instance
    :param project_id: Mix project ID
    :param confirm_project_name:  Confirmation of name of project to be reset
    :return: True
    """
    proj_id = assert_id_int(project_id)
    proj_meta_json = get_project_meta(mixcli, proj_id)
    if not proj_meta_json or 'name' not in proj_meta_json:
        raise ValueError(f'Cannot get meta info for project {proj_id}')
    if proj_meta_json['name'] != confirm_project_name:
        raise ValueError(f'Name from project meta with ID {proj_id} does not match confirmed name: ' +
                         f'{proj_meta_json["name"]}, {confirm_project_name}')
    return pyreq_project_reset(mixcli.httpreq_handler, project_id=proj_id)


def cmd_project_reset(mixcli, **kwargs: str):
    """
    Default function when MixCli project reset command is called. Processing concept list command
    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: True
    """
    proj_id = kwargs['project_id']
    confirm_name = kwargs['confirm_name']
    rv = project_reset(mixcli, project_id=proj_id, confirm_project_name=confirm_name)
    if rv:
        mixcli.info(f"Successfully reset project {proj_id}")
    else:
        raise ValueError(f'Unexpected error while resetting project {proj_id}, try --debug mode')
    return True


@cmd_regcfg_func('project', 'reset', 'Reset a Mix project', cmd_project_reset)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-c', '--confirm-name', metavar='CONFIRM_PROJECT_NAME', required=True,
                               help='Confirm reset request with project name')
