"""
MixCli **channel** command group **get** command.

This command will retrieve channels' configuration information from Mix projects, referred by IDs. The configs of Mix
projects' channels/targets will be mostly used when users want to create 'new' Mix projects whose channels/targets'
configs are exactly same as the source/reference projects. By doing so clients that have been coupled with the
source/reference projects can be easily ported for coupling of 'new' projects.

The implementation of this command is being used by project command group, cp-create command.
"""
import copy
import json
from typing import List, Dict, Optional, Union
from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile
from ..project.get import get_project_meta

_FIELD_PROJ_ID = 'id'
_FIELD_CHANNELS_PROJ_META = 'channels'
_ERR_MSG_CHANNELS_NOT_FOUND = 'Cannot retrieve channel meta-info for project with ID {proj_id}'
_FIELDS_KEEP_IN_CONCISE_CHANNEL_META = ['color', 'name', "modes"]


def get_project_channels(mixcli: MixCli, project_id: Union[int, str],
                         project_meta: Dict = None) -> Optional[List[Dict]]:
    """
    Get the channel/targets configuration for Project with ID project_id.

    :param mixcli: MixCli, a MixCli instance
    :param project_id: str, project id
    :param project_meta: Json object of project meta-info to be used
    :return: None if channels meta-info for project cannot be retrieved, otherwise
    list of Json objects eaching for one channel
    """
    """
    Example response payload
    [
    {"color": "#7894F2", "name": "ivr", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#DA2B7F", "name": "web", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#F8DC4F", "name": "sms", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#2EB8B5", "name": "other1", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#BDCBDB", "name": "other2", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#FE6D6D", "name": "other3", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#A86315", "name": "other4", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#5CBCF0", "name": "other5", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#6D7E97", "name": "other6", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}, 
    {"color": "#B58AF5", "name": "other7", "modes": ["Audio Script", "Interactivity", "Rich Text", "TTS"]}
    ]
    """
    project_id = assert_id_int(project_id, 'project')
    proj_meta = project_meta
    if not proj_meta:
        proj_meta = get_project_meta(mixcli, project_id=project_id)
    else:
        assert int(project_id) == proj_meta[_FIELD_PROJ_ID], \
            f'ID in given meta Json does not match project ID {project_id}'
    if _FIELD_CHANNELS_PROJ_META not in proj_meta:
        raise ValueError(f'Expected field {_FIELD_CHANNELS_PROJ_META} missing in response: {json.dumps(proj_meta)}')
    concise_channel_metas = []
    for channel_meta in proj_meta[_FIELD_CHANNELS_PROJ_META]:
        concise_meta = json.loads('{}')
        for field_copy in _FIELDS_KEEP_IN_CONCISE_CHANNEL_META:
            concise_meta[field_copy] = copy.copy(channel_meta[field_copy])
        concise_channel_metas.append(concise_meta)
    return concise_channel_metas


def cmd_channel_get(mixcli: MixCli, **kwargs: str):
    """
    Default function when channel get command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from keyword arguments
    :return: None
    """
    proj_id = kwargs['project_id']
    proj_meta = get_project_meta(mixcli, proj_id)
    if not proj_meta:
        raise RuntimeError(f'Cannot get meta info for project with ID {proj_id}')
    channel_metas = get_project_channels(mixcli, proj_id, project_meta=proj_meta)
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=channel_metas, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(info_msg=f'Channel meta for project with ID {proj_id}: '+json.dumps(channel_metas))
    return True


# the name of the actual register function can be whatever
@cmd_regcfg_func('channel', 'get', 'Get Mix project channel info in Json', cmd_channel_get)
def register_my_cmd(cmd_argparser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")
