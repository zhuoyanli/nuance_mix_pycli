"""
MixCli **project** command group **model-export** command.

This command serves as a push-button automation of exporting multiple models, currently NLU/dialog, from Mix projects,
effectively combination of 'nlu export' and 'dlg export' commands.
"""
import os.path
from argparse import ArgumentParser
from typing import Union, List
from mixcli import MixCli
from ..nlu.export import EXPORT_ARTIFACT_TRSX, TRSX_DATATYPES, cmd_nlu_export
from ..dlg.export import cmd_dlg_export
from mixcli.util.commands import cmd_regcfg_func

""" Enums of models for a Mix project"""
_MODEL_NLU = 'nlu'
_MODEL_DLG = 'dialog'
_MODEL_ASR = 'asr'
_PROJ_MDL_TYPES = [_MODEL_NLU, _MODEL_DLG]
""" A descriptive string of NLU_TRSX_DATATYPES"""
_STR_PROJECT_MODEL_TYPES = '[{mt}]'.format(mt=','.join(_PROJ_MDL_TYPES))
"""Mix NLU export type"""
_NLU_EXPORT_TYPE = EXPORT_ARTIFACT_TRSX


def cmd_project_model_export(mixcli: MixCli, **kwargs: Union[str, List[str]]):
    """
    Default function when MixCli project model-export command is called,
    export Mix project NLU models to TRSX and Dialog models to JSON.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    out_dir = kwargs['out_dir']
    if not os.path.isdir(out_dir):
        raise ValueError(f'Must specify a valid output directory: {out_dir}')
    export_models = kwargs['model']
    ofn_tmplt = kwargs['file_tmplt']
    if _MODEL_NLU in export_models:
        if not kwargs['locale']:
            raise ValueError('Must specify locale for NLU model export')
        cmd_nlu_export(mixcli, project_id=proj_id, locale=loc, export_type=EXPORT_ARTIFACT_TRSX,
                       data_types=TRSX_DATATYPES, out_file=out_dir, fn_tmplt=ofn_tmplt)
    if _MODEL_DLG in export_models:
        cmd_dlg_export(mixcli, project_id=proj_id, out_json=out_dir, fn_tmplt=ofn_tmplt)
    mixcli.info(f'Successfully export Mix project {proj_id} models to {os.path.realpath(out_dir)}')
    return True


@cmd_regcfg_func('project', 'model-export',
                 'Export models (currently NLU/DLG) for a project by calling {nlu,dlg} export commands.',
                 cmd_project_model_export)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='aa_AA_LOCALE', required=False,
                               help='aa_AA locale code, this is for NLU model')
    cmd_argparser.add_argument('-m', '--model', required=False, nargs='+',
                               choices=_PROJ_MDL_TYPES, default=_PROJ_MDL_TYPES,
                               metavar='PROJECT_MODEL_TO_EXPORT', help='Model(s) to export for Mix project')
    cmd_argparser.add_argument('-T', '--file-tmplt', metavar='EXPORT_FILE_TMPLT', required=False,
                               help='File name template for exported model files. See nlu/dlg export for help.')
    cmd_argparser.add_argument('-o', '--out-dir', metavar='OUTPUT_DIRECTORY', required=True,
                               help='Output directory for exported project models')
