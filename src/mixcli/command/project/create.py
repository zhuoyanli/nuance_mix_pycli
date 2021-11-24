"""
MixCli **project** command group **create** command.

This command would create new Mix projects with given specifications, such as names of new projects, locales of NLU
models, containing namespaces, and etc. It is effectively what users would do in Mix UI project creation steps.

One note is that this command may not seem so convenient if used to create dialog applications, where users need to
create complicated channels/targets configurations, as the command asks for literal JSON content to denote the configs,
which would be difficult to produce in command line. It has been implemented this way due to the expectation of Mix
API endpoints for requests. If users of this command are not focus on dialog aspects of new projects, simply skip the
'channel' argument and the default omni-channel will be created as default config.
"""
from argparse import ArgumentParser
import json
from typing import Dict, List, Union, Optional
from mixcli import MixCli
from ..ns import search as ns_search
from mixcli.util.auth import MixApiAuthTokenExpirationError
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, MixLocale

PROJ_TARGET_TYPE_OMNI = 'omni'
DEFAULT_CHANNEL_CFG_OMNI = [{
    "color": "#871699",
    "name": "Omni Channel VA",
    "modes": [
        "Audio Script", "DTMF", "Interactivity", "Rich Text", "TTS"
    ]
}]
CHANNEL_CONFIG_OMNI = json.dumps(DEFAULT_CHANNEL_CFG_OMNI)


# noinspect PyNoLocalUse
def pyreq_project_create(httpreq_handler: HTTPRequestHandler, proj_name: str, namespace_id: int, proj_dp_topic: str,
                         proj_loc_list: List[str], proj_channel_json: List[Dict]) -> Dict:
    """
    Create new Mix project by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        POST api/v3/projects'

    :param httpreq_handler: a HTTPRequestHandler instance
    :param proj_name: name of the new project
    :param namespace_id: ID of namespace in which new project is created
    :param proj_dp_topic: name of (ASR) datapack topic
    :param proj_loc_list: list of str each being a locale code in 'aa_AA' format
    :param proj_channel_json: Json object of the channels/targets settings for project
    :return: Dict, project creation result in Json
    """
    def_headers = httpreq_handler.get_default_headers()
    def_headers['Content-Type'] = 'application/json'
    data = json.loads('{}')
    data['name'] = proj_name
    data['app_type'] = "asr+nlu+dialog"
    data['languages'] = proj_loc_list
    data['namespace_id'] = namespace_id
    data['base_datapack'] = proj_dp_topic
    data['channels'] = proj_channel_json
    data['type'] = PROJ_TARGET_TYPE_OMNI
    data['category'] = "app"
    api_endpoint = 'api/v3/projects'
    try:
        resp = httpreq_handler.request(url=api_endpoint, method=POST_METHOD, headers=def_headers, data=json.dumps(data),
                                       json_resp=True)
        return resp
    except MixApiAuthTokenExpirationError as ex:
        raise ex
    except Exception as ex:
        ex_msg = str(ex)
        new_ex_msg = f"Error reported while creating project {proj_name} with msg: {ex_msg}." + \
                     "Project may still have been created but compromised. Please check in Mix dashboard!"
        raise RuntimeError(new_ex_msg) from ex


def project_create(mixcli: MixCli, proj_name: str, namespace_id: Union[str, int], asr_dp_topic: str,
                   locales: List[str], proj_channel_json: List[Dict]) -> Dict:
    """
    Create new Mix project with the following settings: project name, namespace id, name of (ASR) datapack topic,
    list of locales the NLU model(s) project would support, Json object for the project channels/targets setting.

    :param mixcli: a MixCli instance
    :param proj_name: name of the new project
    :param namespace_id: the ID of namespace in which new project is created
    :param asr_dp_topic: name of (ASR) datapack topic
    :param locales: list of str each being a locale code in 'aa_AA' format
    :param proj_channel_json: Json object of the channels/targets settings for project
    :return: Dict, project creation result in Json
    """
    # 'type' = 'omni' is the hidden magic attribute we must add to the
    # payload of request so as to get the 'Omni Channle VA' channel
    namespace_id = assert_id_int(namespace_id, 'namespace')
    # make sure ASR DP topic name is lowercase
    asr_dp_topic = asr_dp_topic.lower()
    result = pyreq_project_create(mixcli.httpreq_handler, proj_name, namespace_id, asr_dp_topic,
                                  locales, proj_channel_json)
    return result


CHANNEL_JSON_BLK_FIELDS = {"color", "name", "modes"}
CHANNEL_JSON_BLK_MODES_FIELD = "modes"


def assert_channel_json(channel_json_literal: str) -> List[Dict]:
    """
    Assert that the literal string for JSON of Mix project channel config is a valid literal JSON and is valid
    per expected schema.

    :param channel_json_literal: JSON of Mix project channel config in literal string representation.
    :return: The JSON object from parsing the literal string.
    """
    # noinspection PyUnusedLocal
    channel_json: Optional[List[Dict]] = None
    try:
        # we make sure the 'channel' argument is a valid JSON
        channel_json = json.loads(channel_json_literal)
    except Exception as ex:
        raise RuntimeError('"channel" argument is not a valid JSON literal') from ex
    if not isinstance(channel_json, list):
        raise RuntimeError('JSON of "channel" argument must be a JSON array')
    for cjblk in channel_json:
        # make sure all fields are present
        for cjblkf in CHANNEL_JSON_BLK_FIELDS:
            if cjblkf not in cjblk:
                raise RuntimeError(f'Field "{cjblkf}" missing in channel config block "{json.dumps(cjblk)}"')
        # make sure the 'modes' field is again an non-empty list
        if not isinstance(cjblk[CHANNEL_JSON_BLK_MODES_FIELD], list) or not cjblk[CHANNEL_JSON_BLK_MODES_FIELD]:
            raise RuntimeError(f'Field "modes" in channel config "{json.dumps(cjblk)}" must be non-empty list')
        for cjblkmd in cjblk[CHANNEL_JSON_BLK_MODES_FIELD]:
            if not isinstance(cjblkmd, str):
                raise RuntimeError('Element in field "modes" in channel config ' +
                                   f'"{json.dumps(cjblk)}" must be string: {repr(cjblkmd)}')
    return channel_json


def cmd_project_create(mixcli: MixCli, **kwargs: Union[str, List[str], bool]):
    """
    Default function when project create command is used.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return:
    """
    proj_name = kwargs['name']
    proj_dp_topic = kwargs['dp_topic']
    locs = kwargs['locales']
    asst_locales = []
    for loc in locs:
        asst_locales.append(MixLocale.to_mix(loc))
    # ns and ns_id will both be there, value of one being None
    ns_name = ''
    if kwargs['ns']:
        ns_name = kwargs['ns']
        ns_id = ns_search.ns_search(mixcli, namespace=ns_name, json_resp=False)
        if not ns_id:
            raise ValueError(f'Invalid namespace {ns_name}, try correct it or use id')
    else:
        ns_id = kwargs['ns_id']
    channel_json = CHANNEL_CONFIG_OMNI
    if kwargs['channel_json']:
        channel_json = assert_channel_json(kwargs['channel_json'])
    cr_result = project_create(mixcli, proj_name=proj_name, namespace_id=ns_id, asr_dp_topic=proj_dp_topic,
                               locales=asst_locales, proj_channel_json=channel_json)
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=cr_result, is_json=True, out_file=out_file, logger=mixcli)
    else:
        loc_list = "[{ls}]".format(ls=','.join(locs))
        ns_repr = ns_name if kwargs['ns'] else f'ID {ns_id}'
        msg_prefix = f'Successfully created project with name {proj_name}, locale(s) {loc_list}, preset channels, ' + \
                     f'(ASR) DP topic {proj_dp_topic}, namespace {ns_repr} ' + \
                     f'with following response payload: '
        mixcli.log(msg_prefix+json.dumps(cr_result))
    return True


@cmd_regcfg_func('project', 'create', 'Create new Mix project', cmd_project_create)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('--name', required=True, metavar='PROJECT_NAME', help='Name of the new project')
    cmd_argparser.add_argument('-t', '--dp-topic', required=True, metavar='ASR_DP_TOPIC',
                               help='Name of topic for ASR datapack')
    cmd_argparser.add_argument('-l', '--locales', required=True, nargs='+', metavar='LOCALES',
                               help='List of locales supported in the new project')
    cmd_argparser.add_argument('-c', '--channel-json', required=False, metavar='CHANNEL_CONFIG_JSON_LITERAL',
                               help='A literal Json string for the configuration of channel')
    mutex_grp_ns = cmd_argparser.add_mutually_exclusive_group(required=True)
    mutex_grp_ns.add_argument('--ns', metavar='NAMESPACE_NAME',
                              help='Name of namespace in which the new project shall be created')
    mutex_grp_ns.add_argument('--ns-id', metavar='NAMESPACE_ID',
                              help='ID of namespace in which the new project shall be created')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")
