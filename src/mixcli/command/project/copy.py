"""
MixCli **project** command group **cp-create** command.

This command would create 'copies' of given source Mix project. By 'copies' the settings on NLU locales,
ASR/DLG datapack topic name (this can be overriden), and dialog channels/targets, will be replicated. Replication
of those settings are particularly useful to move any existing backends/clients, which are coupled with source
Mix project, so as to couple with the new copies conveniently. The greatest merit of this command is it removes
the need to visually copy those settings from source project in project creation steps, if doing so in Mix UI.

Please note that this command currently does NOT copy over the ASR/NLU/dialog models from source project. Users
still need to, possibly first export those models from source, import model exports from source project to complete
full copying.
"""
import os
import os.path
import json
from argparse import ArgumentParser
from typing import Union, List, Optional, Dict

from ..job.status import job_id_from_meta
from ..job.wait import job_wait_sync
from mixcli import MixCli
from .create import project_create
from .get import get_project_meta as proj_get_meta, FIELD_ASR_DP_TOPIC, FIELD_LOCALES
from ..channel.get import get_project_channels
from ..ns.search import ns_search
from ..nlu.export import nlu_export_trsx, TRSX_DATATYPES
from ..nlu.nimport import nlu_import_trsx
from ..dlg.export import dlg_export
from ..dlg.dimport import dlg_import_json
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, project_id_from_meta, get_project_id_file, \
    MixLocale


def copy_nlu_models(mixcli: MixCli, src_proj_id: int, src_proj_meta: Dict, target_locales: List[str],
                    dst_proj_id: int, workdir: str):
    """
    Copy NLU model(s) in target locales from source project ID <src_proj_id> to destination project ID <dst_proj_id>,
    with working dir <workdir>

    :param mixcli: MixCli instance
    :param src_proj_id: source project ID
    :param src_proj_meta: meta data for source project
    :param target_locales: target locale(s) NLU model(s) to be copied
    :param dst_proj_id: destination project ID
    :param workdir: Copy working dir for creating export artifacts of models
    :return: None
    """
    mixcli.debug(f'Start copying NLU model(s) from {src_proj_id} to {dst_proj_id}')
    # 1. Create NLU export file
    # Get a identifiable file name for export file
    export_trsx = get_project_id_file(project_id=src_proj_id, project_meta=src_proj_meta,
                                      model='NLU', ext='.trsx')
    # Get the complete path for export file
    path_export_trsx = os.path.join(workdir, export_trsx)
    for target_loc in target_locales:
        mixcli.debug(f'Start copying NLU model in locale {target_loc} from {src_proj_id} to {dst_proj_id}')
        # 2. export src project NLU model from new_proj_loc to path_export_trsx
        mixcli.debug(f'Exporting NLU model in locale {target_loc} from {src_proj_id} to {path_export_trsx}')
        nlu_export_trsx(mixcli, project_id=src_proj_id, locale=target_loc, out_trsx=path_export_trsx,
                        export_types=TRSX_DATATYPES)
        # 3. import path_export_trsx to new_proj_id
        mixcli.debug(f'Importing NLU model from {path_export_trsx} to {dst_proj_id}')
        import_rslt = nlu_import_trsx(mixcli, project_id=dst_proj_id, import_src=path_export_trsx)
        # 4. wait for import job to complete
        job_id = job_id_from_meta(import_rslt)
        mixcli.debug(f'Start waiting for job {job_id} to complete for {dst_proj_id}')
        job_meta, suc = job_wait_sync(mixcli, dst_proj_id, job_id, infinite_wait=True, json_resp=True)
        if not suc:
            raise RuntimeError(f'Import job failed for project {dst_proj_id} ' +
                               f'with {path_export_trsx}: {json.dumps(job_meta)}')
        mixcli.debug(f'NLU model import job {job_id} completed for {dst_proj_id}')
    mixcli.info(f'Successfully copied NLU model(s) from all locales of {src_proj_id} to {dst_proj_id}')


def copy_dlg_model(mixcli: MixCli, src_proj_id: int, src_proj_meta: Dict, dst_proj_id: int, workdir: str):
    """
    Copy Dialog model from source project ID <src_proj_id> to destination project ID <dst_proj_id>,
    with working dir <workdir>

    :param mixcli: MixCli instance
    :param src_proj_id: source project ID
    :param src_proj_meta: meta data for source project
    :param dst_proj_id: destination project ID
    :param workdir: Copy working dir for creating export artifacts of models
    :return: None
    """
    mixcli.debug(f'Start copying Dialog model from {src_proj_id} to {dst_proj_id}')
    # 1. Create Dialog export file
    # Get a identifiable file name for export file
    export_dlgjson = get_project_id_file(project_id=src_proj_id, project_meta=src_proj_meta,
                                         model='DLG', ext='.json')
    # Get the complete path for export file
    path_export_dlgjson = os.path.join(workdir, export_dlgjson)
    # 2. Export src project Dialog model to path_export_dlgjson
    mixcli.debug(f'Exporting Dialog model from {src_proj_id} to {path_export_dlgjson}')
    dlg_export(mixcli, project_id=src_proj_id, output_json=path_export_dlgjson)
    # 3. Import path_export_dlgjson to new_proj_id
    mixcli.debug(f'Importing Dialog model from {path_export_dlgjson} to {dst_proj_id}')
    dlg_import_json(mixcli, project_id=dst_proj_id, import_src=path_export_dlgjson)
    mixcli.info(f'Successfully copied Dialog model of {src_proj_id} to {dst_proj_id}')


def project_copy_create(mixcli: MixCli, new_project_name: str, src_project_id: Union[int, str],
                        new_asr_topic: Optional[str], dest_ns: Optional[str] = None,
                        dest_ns_id: Optional[int] = None, copy_nlu: Optional[bool] = None,
                        copy_dlg: Optional[bool] = None, copy_all_models: Optional[bool] = None,
                        copy_workdir: Optional[str] = None):
    """
    Create a new Mix project, in specific namespace, by copying attributes from source Mix project,
    optionally including NLU and/or Dialog model(s). The model copying is done by creating export model export
    from source project and then import the artifact into new project. The attributes to be copied include
    NLU locale(s), channel settings, and ASR datapack topic name. Callers can overwrite the ASR datapack topic
    name. dest_ns and dest_ns_id are mutually excluded. When copy_nlu or copy_dlg is False, copy_all_models can not
    be True.

    :param mixcli: MixCli instance needed for all the API operations.
    :param new_project_name: Name for the new project
    :param src_project_id: ID of source project
    :param new_asr_topic: Name of ASR datapack topic name for new project. None to take the name from source
    :param dest_ns: Namespace name where new project shall be created, mutually excluded with dest_ns_id
    :param dest_ns_id: Namespace ID where new project shall be created, mutually excluded with dest_ns
    :param copy_nlu: If True or skipped, copy NLU model(s) from source to new project, of all locales in source.
    :param copy_dlg: If True or skipped, copy Dialog model from source to new project
    :param copy_all_models: If True, should copy all models from source to new project
    :param copy_workdir: Path to working dir for model copy operations.
    :return:
    """
    if dest_ns and dest_ns_id:
        raise RuntimeError('Cannot use destination namespace (name) and id at the same time')
    if copy_all_models is True:
        if copy_nlu is False or copy_dlg is False:
            raise RuntimeError('Cannot copy all models when copy_nlu and/or copy_dlg False')
    src_proj_id = assert_id_int(src_project_id, 'project')
    src_proj_meta = proj_get_meta(mixcli, project_id=src_proj_id)
    src_proj_ch_metas = get_project_channels(mixcli, project_id=src_proj_id, project_meta=src_proj_meta)
    if not src_proj_ch_metas:
        raise ValueError(f'Cannot retrieve channels info from source project with ID: {src_proj_id}')
    src_proj_locs = src_proj_meta[FIELD_LOCALES]
    if dest_ns:
        dest_ns_id = ns_search(mixcli, dest_ns)
        if not dest_ns_id:
            raise ValueError(f'Namespace with name {dest_ns} not found, try correct errors or using namespace ID')
    if not new_asr_topic:
        # take the one from source
        new_asr_topic = src_proj_meta[FIELD_ASR_DP_TOPIC]
    mixcli.debug('Now create new project with expected meta')
    cpcr_result = project_create(mixcli, proj_name=new_project_name, namespace_id=dest_ns_id,
                                 asr_dp_topic=new_asr_topic, locales=src_proj_locs, proj_channel_json=src_proj_ch_metas)
    nlu_copied = False
    dlg_copied = False

    # if we do not need to copy models, then just return
    if not (copy_nlu or copy_dlg or copy_all_models):
        if copy_workdir:
            mixcli.info('"workdir" arg only effective when at least one of "cp-*" arg is used')
    else:
        # record new project ID
        new_proj_meta = cpcr_result
        new_proj_id = project_id_from_meta(new_proj_meta)
        new_proj_locs = []
        for src_loc in src_proj_locs:
            new_proj_locs.append(MixLocale.to_mix(src_loc))

        if copy_workdir:
            # need to validate workdir
            if os.path.isfile(copy_workdir):
                raise FileExistsError(f'Work dir cannot be existing file: {copy_workdir}')
            elif not os.path.isdir(copy_workdir):
                raise FileNotFoundError(f'Work dir not found: {copy_workdir}')
            # make sure we have the canonical path
            cp_workdir = os.path.realpath(copy_workdir)
        else:
            # we just use CWD as workdir
            cp_workdir = os.getcwd()
        mixcli.debug(f'Project model copy work dir: {cp_workdir}')

        if not new_proj_id or not new_proj_meta or not new_proj_locs:
            raise RuntimeError('Something wrong! No meta data for new copied project are available!')
        if copy_nlu or copy_all_models:
            # need to copy NLU model
            copy_nlu_models(mixcli, src_proj_id, src_proj_meta, new_proj_locs, new_proj_id, cp_workdir)
            nlu_copied = True
        if copy_dlg or copy_all_models:
            # need to copy Dialog model
            copy_dlg_model(mixcli, src_proj_id, src_proj_meta, new_proj_id, cp_workdir)
            dlg_copied = True
    return src_proj_meta, cpcr_result, nlu_copied, dlg_copied


def cmd_project_cp_create(mixcli: MixCli, **kwargs: Union[str, List[str], bool]):
    """
    Default function when project copy command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return:
    """
    new_proj_nm = kwargs['name']
    src_proj_id = kwargs['src_proj_id']
    new_topic = kwargs['asr_dp_topic']
    dest_nsnm = kwargs['dest_ns']
    dest_nsid = kwargs['dest_ns_id']
    cp_nlu = True if kwargs['copy_nlu'] else None
    cp_dlg = True if kwargs['copy_dlg'] else None
    cp_allmdls = kwargs['copy_models']
    cp_workdir = kwargs['workdir']
    mixcli.debug('Now create new project with expected meta, and copy model(s) if asked')
    src_proj_meta, cpcr_result, nlu_copied, dlg_copied \
        = project_copy_create(mixcli, new_project_name=new_proj_nm, src_project_id=src_proj_id, new_asr_topic=new_topic,
                              dest_ns=dest_nsnm, dest_ns_id=dest_nsid, copy_nlu=cp_nlu, copy_dlg=cp_dlg,
                              copy_all_models=cp_allmdls, copy_workdir=cp_workdir)
    new_proj_id = project_id_from_meta(cpcr_result)
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=cpcr_result, is_json=True, out_file=out_file, logger=mixcli)
    else:
        msg_prefix = f'Successfully copy-created from src # {src_proj_id} to new # {new_proj_id} {new_proj_nm}' + \
                     f'with following response payload: '
        mixcli.info(msg_prefix+json.dumps(cpcr_result))
    if nlu_copied:
        mixcli.info('Successfully copied NLU model(s) ')
    return True


@cmd_regcfg_func('project', 'cp-create', 'Create new Mix project by copying source project', cmd_project_cp_create)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('--name', required=True, metavar='NEW_PROJECT_NAME', help='Name of the new project')
    cmd_argparser.add_argument('--src-proj-id', required=True, metavar='SRC_PROJ_ID_TO_CP',
                               help='ID of source Mix project from which settings should copy')
    mutex_grp_ns = cmd_argparser.add_mutually_exclusive_group(required=True)
    mutex_grp_ns.add_argument('--dest-ns', metavar='NAMESPACE_NAME',
                              help='Name of namespace in which the new project shall be created')
    mutex_grp_ns.add_argument('--dest-ns-id', metavar='NAMESPACE_ID',
                              help='ID of namespace in which the new project shall be created')
    cmd_argparser.add_argument('--asr-dp-topic', metavar='ASR_DATAPACK_TOPIC_NAME', required=False,
                               help='Topic name for the ASR/DLM datapack used by the NEW project')
    cmd_argparser.add_argument('--copy-nlu', action='store_true', help='Copy NLU model')
    cmd_argparser.add_argument('--copy-dlg', action='store_true', help='Copy Dialog model')
    cmd_argparser.add_argument('--copy-models', action='store_true', help='Copy all models')
    cmd_argparser.add_argument('--workdir', metavar='MODEL_COPY_WORKDIR', required=False,
                               help='Working dir for model export')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")
