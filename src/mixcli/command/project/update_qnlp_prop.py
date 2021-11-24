"""
MixCli **project** command group **update-qnlp-prop** command.

This command will update the value of a given property (referred by key name) of native QuickNLP
project for a specific locale of specific Mix project.

Please note that for each locale of a Mix project, there is a underlying native QuickNLP project with
which the NLU model is built. If there are two or more native QuickNLP projects, they are separated.
So are their properties. As a result locale of Mix project must be specified in order to identify the
specific native QuickNLP project.

There are no easy ways to verify if a specific property in indeed available in QuickNLP. As a
result, we actually perform the validation after sending property update/assignment requests.
If a specific property (key/name) does not exist for the QuickNLP project, sending update
requests on it shouldn't change anything in the QuickNLP project.

This command is SUPPOSED to be used by advanced users who know what they are doing.
"""
import json
from argparse import ArgumentParser
from typing import Union, Dict

from mixcli.util.requests import HTTPRequestHandler, PUT_METHOD
from mixcli.util.cmd_helper import write_result_outfile, assert_id_int, MixLocale
from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func


def pyreq_update_qnlp_prop(httpreq_hdlr: HTTPRequestHandler, project_id: int, locale: str, qnlp_prop_key: str,
                           qnlp_prop_new_value: str) -> Dict:
    """
    Use Mix API endpoint to set the value of given property (by key name) of native QuickNLP project for
    a locale of given Mix project.

    :param httpreq_hdlr:
    :param project_id:
    :param locale:
    :param qnlp_prop_key:
    :param qnlp_prop_new_value:
    :return: The complete properties after update
    """
    api_endpoint = f'api/v1/properties/{project_id}?protected=True&locale={locale}'
    req_payload = json.dumps({
        qnlp_prop_key: qnlp_prop_new_value
    })
    resp: Dict = httpreq_hdlr.request(url=api_endpoint, method=PUT_METHOD, default_headers=True, data=req_payload,
                                      json_resp=True)
    return resp


def project_update_qnlp_prop(mixcli: MixCli, project_id: Union[str, int], locale: str, qnlp_prop_key: str,
                             qnlp_prop_new_value: str) -> Dict:
    """
    Update the value of a specific property of a native QuickNLP project for a specific locale of a Mix project
    to a new value.

    :param locale: Specific locale the QuickNLP project for which should have property updated
    :param mixcli: MixCli instance
    :param project_id: Id of Mix project
    :param qnlp_prop_key: Key (name) of QuickNLP property
    :param qnlp_prop_new_value:  New value for the QuickNLP property
    :return: The complete properties after update
    """
    proj_id = assert_id_int(project_id, 'project')
    loc = MixLocale.to_mix(locale)
    return pyreq_update_qnlp_prop(mixcli.httpreq_handler, project_id=proj_id, locale=loc, qnlp_prop_key=qnlp_prop_key,
                                  qnlp_prop_new_value=qnlp_prop_new_value)


def cmd_project_update_qnlp_prop(mixcli: MixCli, **kwargs: str):
    """
    Default function when MixCli project update-qnlp-prop command is called.

    :param mixcli: MixCli, a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: True
    """
    proj_id = kwargs['project_id']
    proj_loc = kwargs['locale']
    qnlp_prop_key = kwargs['qnlp_prop_key']
    qnlp_prop_new_value = kwargs['qnlp_prop_new_value']
    props_after_update = project_update_qnlp_prop(mixcli, project_id=proj_id, locale=proj_loc,
                                                  qnlp_prop_key=qnlp_prop_key,
                                                  qnlp_prop_new_value=qnlp_prop_new_value)
    # the props_after_update is a Json/dict object of all available QuickNLP properties in the target
    # QuickNLP project
    # We want to confirm if the specified property (key/name) actually available in QuickNLP project
    if qnlp_prop_key not in props_after_update:
        mixcli.error(f'Specified QuickNLP property {qnlp_prop_key} not available in QuickNLP project')
        mixcli.error(json.dumps(props_after_update))
        raise RuntimeError(f'Specified QuickNLP property {qnlp_prop_key} not available in QuickNLP project')
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=props_after_update, is_json=True, out_file=out_file, logger=mixcli)
    else:
        mixcli.log(f'QuickNLP properties of #{proj_id} after update: '+json.dumps(props_after_update))
    return True


@cmd_regcfg_func('project', 'update-qnlp-prop',
                 'Update specific property to new value of native QuickNLP project for a locale of Mix project',
                 cmd_project_update_qnlp_prop)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', dest='project_id',
                               metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', dest='locale',
                               metavar='LOCALE', required=True,
                               help='The specific locale in Mix project in aa-AA form')
    cmd_argparser.add_argument('-k', '--prop-key', dest='qnlp_prop_key', metavar='QNLP_PROPERTY_KEY', required=True,
                               help='Key (name) of QuickNLP property')
    cmd_argparser.add_argument('-v', '--prop-value', dest='qnlp_prop_new_value', metavar='QNLP_PROPERTY_NEW_VALUE',
                               required=True, help='New value of QuickNLP property')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")
