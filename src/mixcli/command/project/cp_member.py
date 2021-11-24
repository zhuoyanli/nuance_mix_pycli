"""
MixCli **project** command group **cp-member** command.

This command would copy the granted member/access setting from source Mix project to target project.
"""
from argparse import ArgumentParser
from typing import Union, List, Dict

from mixcli import HTTPRequestHandler
from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import GET_METHOD, POST_METHOD

AVAILABLE_ROLE_LEVEL = ['owner', 'admin', 'viewer']


def pyreq_get_proj_members(httpreq_runner: HTTPRequestHandler, project_id: int):
    api_endpoint = f'/bolt/projects/{project_id}/collaborators'
    resp = httpreq_runner.request(url=api_endpoint, method=GET_METHOD, default_headers=True, json_resp=True)
    return resp


def extract_member_email_role(member_meta: Dict):
    member_setting = [(mbr_meta['email'], mbr_meta['role_level']) for mbr_meta in member_meta['collaborators']]
    return member_setting


def pyreq_set_proj_member(httpreq_runner: HTTPRequestHandler, project_id: int, member_email: str, member_role: str):
    if member_role not in AVAILABLE_ROLE_LEVEL:
        raise RuntimeError(f'Specified member role level not available: {member_role}')
    api_endpoint = f'bolt/projects/{project_id}/collaborators'
    req_payload = {
        "email": member_email,
        "role_level": member_role
    }
    resp = httpreq_runner.request(url=api_endpoint, method=POST_METHOD, data=req_payload, default_headers=True)
    return resp


def cp_proj_member(mixcli: MixCli, src_proj_id: Union[str, int], dest_proj_id: Union[str, int]):
    src_proj_id = assert_id_int(src_proj_id, 'source project')
    dest_proj_id = assert_id_int(dest_proj_id, 'destination project')
    proj_member_meta = pyreq_get_proj_members(httpreq_runner=mixcli.httpreq_handler, project_id=src_proj_id)
    mbr_email_role = extract_member_email_role(proj_member_meta)
    mixcli.debug('Found following member/access setting: {}'.format(repr(mbr_email_role)))
    for tpl_em_role in mbr_email_role:
        (mbr_em, mbr_role) = tpl_em_role
        mixcli.debug(f'Setting {mbr_em} as {mbr_role}')
        try:
            pyreq_set_proj_member(httpreq_runner=mixcli.httpreq_handler, project_id=dest_proj_id,
                                  member_email=mbr_em, member_role=mbr_role)
        except:
            mixcli.debug(f'Exception on setting {mbr_em} as {mbr_role}, it is possible.')


def cmd_project_cp_member(mixcli: MixCli, **kwargs: Union[str, List[str], bool]):
    """
    Default function when project copy command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return:
    """
    src_proj_id = kwargs['src_proj_id']
    dest_proj_id = kwargs['dest_proj_id']
    cp_proj_member(mixcli=mixcli, src_proj_id=src_proj_id, dest_proj_id=dest_proj_id)
    return True


@cmd_regcfg_func('project', 'cp-member', 'Copy project member/access setting from source project',
                 cmd_project_cp_member)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-spi', '--src-proj-id', dest='src_proj_id', required=True, metavar='SRC_PROJ_ID',
                               help='ID of source Mix project from which setting of member/access should be copied')
    cmd_argparser.add_argument('-dpi', '--dst-proj-id', dest='dest_proj_id', required=True, metavar='DEST_PROJ_ID',
                               help='ID of destination project into which setting of member/access should be copied')
