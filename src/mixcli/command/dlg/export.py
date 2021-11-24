"""
MixCli **dlg** command group **export** command.

This command will export dialog model of a Mix project as JSON artifact. If the 'out-json' argument is a directory,
a file name <PROJ_ID>__<PROJ_NAME>__DIALOG__<DATETIME>.json will be created in that output dir.

Please note that Mix API endpoint will take some considerable processing time on the request before sending back
the response payload.The content of the payload is that JSON artifact.
"""
import codecs
import json
import os.path
from argparse import ArgumentParser
from typing import Union

from ..project.get import get_project_meta
from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD
from mixcli.util.cmd_helper import assert_id_int, get_project_id_file


def pyreq_dlg_export(httpreq_hdlr: HTTPRequestHandler, project_id: int, output_json: str):
    """
    Export dialog model from Mix project project_id to output JSON file output_json, by sending requests to
    API endpoint with Python 'requests' package.

    API endpoint
    ::
        GET /api/v3beta1/dialog/projects/{project_id}/export.

    :param httpreq_hdlr: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :param output_json: path to expected output Json
    :return: None
    """
    api_endpoint = f"/api/v3beta1/dialog/projects/{project_id}/export"
    # we do NOT validate the response as JSON, in that the response payload will be in JSON format
    # but NOT a regular API response payload. The response will be the content of the exported JSON artifact.
    resp = httpreq_hdlr.request(url=api_endpoint, method=GET_METHOD, default_headers=True, json_resp=False)
    if resp:
        _ = json.loads(resp)
        try:
            # We must write the content as-is!
            with codecs.open(output_json, 'w', 'utf-8') as fho_export_json:
                fho_export_json.write(resp)
                httpreq_hdlr.info(f"Project {project_id} successfully exported to {output_json}")
        except Exception as ex:
            raise IOError("Cannot write dialog model JSON to {out_json}".format(out_json=output_json), ex)


def dlg_export(mixcli: MixCli, project_id: Union[str, int], output_json: Union[str, int]):
    """
    Export dialog model from Mix project project_id to out JSON file output_json.

    :param mixcli: a MixCli instance
    :param project_id: Mix project ID
    :param output_json: path to expected output Json
    :return: None
    """
    project_id = assert_id_int(project_id, 'project')
    pyreq_dlg_export(mixcli.httpreq_handler, project_id=project_id, output_json=output_json)


def cmd_dlg_export(mixcli, **kwargs: str):
    """
    Default function when MixCli dlg export command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    proj_id = kwargs['project_id']
    out_json = kwargs['out_json']
    expfn_tmplt = kwargs['fn_tmplt'] if 'fn_tmplt' in kwargs else None
    if os.path.isdir(out_json):
        mixcli.debug('Only output dir specified, need to generate an export JSON file name')
        proj_meta = get_project_meta(mixcli, project_id=proj_id)
        proj_id = int(proj_id)
        jsonf_basename = get_project_id_file(project_id=proj_id, project_meta=proj_meta, ext='.json', model='DIALOG',
                                             fn_tmplt=expfn_tmplt)
        out_json = os.path.join(out_json, jsonf_basename)
    mixcli.debug(f'Output JSON: {out_json}')
    dlg_export(mixcli, proj_id, out_json)
    return True


@cmd_regcfg_func('dlg', 'export', 'Export Mix project DIALOG model as Json', cmd_dlg_export)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-o', '--out-json', metavar='OUTPUT_JSON', required=True, help='Path of output Json')
    cmd_argparser.add_argument('-T', '--fn-tmplt', metavar='EXPORT_FILENAME_TMPLT', required=False,
                               help="Template for name of exported file/archive. See epilog for available specifiers")
    cmd_argparser.epilog = """The following specifiers can be used in tmplt:
%ID% for project ID, %NAME% for project name, %MODEL% for *model_name* argument,
%TIME% for time stamp which should be datetime formatter string and by default '%Y%m%dT%H%M%S'"""
