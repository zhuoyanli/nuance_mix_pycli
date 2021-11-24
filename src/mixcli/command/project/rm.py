"""
MixCli **project** command group **rm** command.

This command removes/deletes a Mix project. Like 'project reset' command, we ask users to enter names of projects
to be removed in command line as safeguard measures to reduce chances of errors like entering wrong project IDs.
"""
from argparse import ArgumentParser
from typing import Union
from .get import get_project_meta, project_name_from_meta
from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, DELETE_METHOD
from mixcli.util.cmd_helper import assert_id_int

FIELD_ASR_DP_TOPIC = 'baseDatapack'
FIELD_LOCALES = 'languages'


def pyreq_get_project_meta(httpreq_hdlr: HTTPRequestHandler, project_id: int):
    """
    Delete Mix project by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        DELETE /api/v3/projects/{projectID}

    :param httpreq_hdlr: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :return: None
    """
    api_endpoint = f'api/v3/projects/{project_id}'
    # the response JSON will be empty!
    httpreq_hdlr.request(url=api_endpoint, method=DELETE_METHOD, default_headers=True)


def rm_project(mixcli: MixCli, project_id: Union[str, int], confirm_project_name: str):
    """
    Remove a Mix project.

    :param mixcli: a MixCli instance
    :param project_id: ID of Mix project to delete
    :param confirm_project_name: Confirmation of name of project to be removed
    :return: json object, the project meta info in Json
    """
    """
    from the json payload
    namespace: json['namespace_name']
    namespace_id: json['namespace_id']
    project_id: json['id']
    project_name: json['name']
    channels_meta: json['channels']
    NLU build meta: json['nlu_builds'] -> List[...]
    ASR build meta: json['asr_builds'] -> List[...]
    DIALOG build meta: json['dialog_builds'] -> List[...]
    """
    proj_id = assert_id_int(project_id, 'project')
    proj_meta_json = get_project_meta(mixcli, proj_id)
    proj_name_in_meta = project_name_from_meta(proj_meta_json)
    if confirm_project_name != proj_name_in_meta:
        raise RuntimeError(f'Project name from meta {proj_name_in_meta} NOT match cmd line: {confirm_project_name}')
    pyreq_get_project_meta(mixcli.httpreq_handler, project_id=proj_id)


def cmd_project_rm(mixcli: MixCli, **kwargs: str):
    """
    Default function when MixCli project get command is called. Processing concept list command
    :param mixcli: MixCli, a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: True
    """
    proj_id = kwargs['project_id']
    proj_name_confirm = kwargs['confirm']
    mixcli.debug('Confirmed name from cmd-line matched the one in meta, proceed.')
    rm_project(mixcli, project_id=proj_id, confirm_project_name=proj_name_confirm)
    mixcli.info(f'Successfully deleted Mix project {proj_id} {proj_name_confirm}')
    return True


# the name of the actual register function can be whatever
@cmd_regcfg_func('project', 'rm', 'Delete Mix project with ID', cmd_project_rm)
def register_my_cmd(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-c', '--confirm', metavar='CONFIRM_PROJECT_NAME', required=True,
                               help='Project name to confirm for deletion')
