"""
MixCli **nlu** command group **import** command.

This command will import a TRSX artifact, which should be result of a NLU model export of Mix projects. The import
will be sort of incremental merging processing between the current NLU model and the one represented by TRSX. If there
are conflicts between the two, such as same training sample in both current NLU model and TRSX, non-fatal errors will
be raised and that sample will be skipped for import.

Another thing to note is that Mix project NLU model TRSX import is asynchronous process. Mix platform will create
asynchronous import jobs and meta info of those jobs will be returned as response payload. It is users'
responsibility to query appropriate Mix API endpoints to keep track of the status of those jobs.

This in turn introduces an important feature of this nlu import command: If users specify '--wait' argument, this
command will do the tracking routine for users: Receive the response payloads to extract import job IDs, keep querying
API endpoints for the status of jobs, and only return when jobs are completed, either 'completed' for success or
'failed' for failure. The tracking of job status is done with the implementations of job list/status/wait commands.
"""
import os.path
from argparse import ArgumentParser
from typing import Union

from mixcli import MixCli
from ..ns.list import list_affiliated_ns

from ..project.get import get_project_id
from ..project.create import project_create, DEFAULT_CHANNEL_CFG_OMNI
from ..nlu.nimport import nlu_import, NLU_IMPORT_TYPE_TRSX
from ..nlu.export import nlu_export_qnlp
from ..project.rm import rm_project
from mixcli.util.cmd_helper import MixLocale
from mixcli.util.commands import cmd_regcfg_func

_NLU_IMPORT_TYPE_TRSX = 'trsx'
WORKPROJ_CONV_NM = 'TMP_PROJ_MIXCLI_NLU_TRSX2QNLP'
# this must be lowercase
DEFAULT_DP_TOPIC = 'gen'


def cmd_nlu_trsx2qnlp(mixcli: MixCli, **kwargs: Union[str, int]):
    """
    Default function when nlu import command is called.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command line
    :return: None
    """
    # we just use user name as namespace name
    usr_ns_name = kwargs['user']
    ns_list = list_affiliated_ns(mixcli)
    usr_ns_id = None
    for ns_meta in ns_list:
        if ns_meta['name'] == usr_ns_name:
            usr_ns_id = ns_meta['id']
            break
    if not usr_ns_id:
        # no matching namespace found!
        raise RuntimeError(f'No namespace found for user name: {usr_ns_name}')
    loc = MixLocale.to_mix(kwargs['locale'])
    src_trsx: str = kwargs['src_trsx']
    dst_outdir: str = kwargs['out_dir']
    # validate input TRSX
    if not os.path.isfile(src_trsx):
        raise RuntimeError(f'Invalid input TRSX: {src_trsx}')
    # validate output dir
    if not os.path.isdir(dst_outdir):
        raise RuntimeError(f'Invalid output directory: {dst_outdir}')

    newproj_meta = project_create(mixcli, proj_name=WORKPROJ_CONV_NM, namespace_id=usr_ns_id,
                                  asr_dp_topic=DEFAULT_DP_TOPIC, locales=[loc],
                                  proj_channel_json=DEFAULT_CHANNEL_CFG_OMNI)
    # print(json.dumps(newproj_meta))
    newproj_id = get_project_id(newproj_meta)
    mixcli.info(f'Successfully created tmp working project {WORKPROJ_CONV_NM} #{newproj_id}')
    nlu_import(mixcli, project_id=newproj_id, import_type=NLU_IMPORT_TYPE_TRSX, import_src=src_trsx, wait_for=True)
    mixcli.info(f'Successfully imported TRSX into project [{WORKPROJ_CONV_NM}] #{newproj_id}: {src_trsx}')
    exported_paths = nlu_export_qnlp(mixcli, project_id=newproj_id, out_dir=dst_outdir)
    repr_expaths = repr(exported_paths)
    mixcli.info(f'Successfully exported project [{WORKPROJ_CONV_NM}] #{newproj_id} to: {repr_expaths}')
    mixcli.info(f'Successfully converted {src_trsx} to {repr_expaths}')
    try:
        rm_project(mixcli, project_id=newproj_id, confirm_project_name=WORKPROJ_CONV_NM)
    except Exception as ex:
        raise RuntimeError(f'Failed to rm working project {WORKPROJ_CONV_NM} #{newproj_id} for cleanup') from ex
    return True


@cmd_regcfg_func('nlu', 'trsx2qnlp', 'Convert TRSX model to QuickNLP project', cmd_nlu_trsx2qnlp)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-s', '--src-trsx', required=True, metavar='SRC_TRSX',
                               help='Path to source TRSX file to be converted')
    cmd_argparser.add_argument('-o', '--out-dir', required=True, metavar='OUTPUT_DIR',
                               help=f'Path to output dir where ZIP with converted QuickNLP project will be placed.')
    cmd_argparser.add_argument('-l', '--locale', required=True, metavar='TRSX_LOCALE',
                               help='Locale of the TRSX file')
    cmd_argparser.add_argument('-u', '--user', required=True, metavar='MIX_USERNAME',
                               help='Mix user account used for the conversion work')
