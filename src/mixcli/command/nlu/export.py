"""
MixCli **nlu** command group **export** command.

This command will export NLU model, from a particular locale, including particular data elements, of a Mix project
as TRSX artifact. If the 'out-file' argument is a directory,
a file name <PROJ_ID>__<PROJ_NAME>__nlu__<DATETIME>.json will be created in that output dir.

TRSX artifacts of NLU models from Mix projects can contain (training) samples, ontology, entities and their
literals and values. If no arguments are specified all elements would be included in TRSX exports.

"""
import os.path
import shutil
import zipfile
from argparse import ArgumentParser
from io import BytesIO
from pathlib import Path
from typing import Union, List, Set

from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, get_project_id_file, MixLocale
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD
from ..project.get import get_project_meta

""" Enums of NLU data types in TRSX specification"""
TRSX_DATATYPES = ["ONTOLOGY", "CONCEPT_LITERALS", "SAMPLES"]
""" A descriptive string of TRSX_DATATYPES"""
_STR_DATATYPES = '[{dt}]'.format(dt=','.join(TRSX_DATATYPES))
"""Mix NLU export type"""
EXPORT_ARTIFACT_TRSX = 'trsx'
EXPORT_ARTIFACT_QNLP = 'qnlp'
EXPORT_TYPES = [EXPORT_ARTIFACT_TRSX, EXPORT_ARTIFACT_QNLP]
_STR_EXPORT_TYPES = '[{dt}]'.format(dt=','.join(EXPORT_TYPES))


def pyreq_nlu_export_trsx(httpreq_hdlr: HTTPRequestHandler, project_id: int, locale: str, out_trsx: str,
                          export_types: List[str]):
    """
    Export project NLU models to TRSX by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        GET "/api/v1/data/{project_id}/export?type=TRSX&filename=save.trsx&{extype_args}&locales={locale}"
        extype_args = '&'.join([f"data_types={et}" for et in export_types])
        export_types = [{ONTOLOGY|CONCEPT_LITERALS|SAMPLES}[,...]]


    :param httpreq_hdlr: a HTTPRequestHandler instance
    :param project_id: Mix project id
    :param locale: Mix project locale code in aa_AA
    :param out_trsx: path of expected output TRSX
    :param export_types: list of TRSX data types included in export, each being enum from TRSX_DATATYPES
    :return: None
    """
    # We must safeguard here against in that this function may be called by other functions directly
    if not [t for t in filter(lambda dt: dt in TRSX_DATATYPES, export_types)]:
        raise ValueError(f'Not all specified types in {repr(export_types)} are supported')
    extype_args = '&'.join([f"data_types={et}" for et in export_types])
    end_point = f"api/v1/data/{project_id}/export?type=TRSX&filename=save.trsx&{extype_args}&locale={locale}"
    resp: bytes = httpreq_hdlr.request(url=end_point, method=GET_METHOD, default_headers=True, stream=True,
                                       byte_resp=True)
    if resp:
        try:
            with open(out_trsx, 'wb') as fho_trsx:
                fho_trsx.write(resp)
                httpreq_hdlr.info(f"Project {project_id} successfully exported to {out_trsx}")
        except Exception as ex:
            raise IOError(f"Error writing NLU model TRSX to {out_trsx}") from ex


def nlu_export_trsx(mixcli: MixCli, project_id: Union[str, int], locale: str, out_trsx: str,
                    export_types: List[str]):
    """
    Export NLU models from Mix project with project_id, locale, to out_trsx.

    :param mixcli: a MixCli instance
    :param project_id: Mix project id
    :param locale: Mix project locale code in aa_AA
    :param out_trsx: path of expected output TRSX
    :param export_types: list of TRSX data types included in export, each being enum from
    TRSX_DATATYPES
    :return: None
    """
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    pyreq_nlu_export_trsx(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc,
                          out_trsx=out_trsx, export_types=export_types)


def pyreq_nlu_export_quicknlp(httpreq_hdlr: HTTPRequestHandler, project_id: int):
    """
    Export project NLU models to QuickNLP project by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        GET "/api/v1/data/{project_id}/export?type=TRSX&filename=save.trsx&{extype_args}&locales={locale}"
        extype_args = '&'.join([f"data_types={et}" for et in export_types])
        export_types = [{ONTOLOGY|CONCEPT_LITERALS|SAMPLES}[,...]]


    :param httpreq_hdlr: a HTTPRequestHandler instance
    :param project_id: Mix project id
    :return: QuickNLP project archive byte content
    """
    end_point = f"nlu/api/v1/projects/{project_id}/export?type=QNLP&withWork=true"
    resp = httpreq_hdlr.request(url=end_point, method=GET_METHOD, default_headers=True, json_resp=False,
                                stream=True, byte_resp=True)
    return resp


def extract_zip(mixcli: MixCli, zip_bytes: bytes, out_dir: str, reduce_dirs: bool = False) -> Union[str, List[str]]:
    """
    This method extracts the content from an Mix exported ZIP archive to an specified directory.
    If there is only one single immediate child directory in the ZIP archive, we move everything
    under that single child directory to the top-level of output directory

    :param reduce_dirs:
    :param out_dir:
    :param zip_bytes:
    :param mixcli:
    :returns:
    """
    byteio = BytesIO(zip_bytes)
    with zipfile.ZipFile(byteio, 'r') as zip_hdlr:
        if not out_dir:
            # by default we extract to $PWD/exported_quicknlp_project
            outdir_qnlpprj = 'exported_quicknlp_project'
            out_dir = os.path.join(os.getcwd(), outdir_qnlpprj)
        else:
            out_dir = os.path.realpath(out_dir)
        # make sure it exists
        if os.path.isdir(out_dir) is False:
            os.makedirs(out_dir, exist_ok=True)
        zip_hdlr.extractall(out_dir)
        mixcli.info(f"Successfully extracted ZIP to QuickNLP project dir {out_dir}")
        set_top_childdir: Set[str] = {item.split('/')[0] for item in zip_hdlr.namelist()}
        if not reduce_dirs:
            return list(set_top_childdir)
        # we get a set of immediate child dir(s) under path_outdir
        if len(set_top_childdir) > 1:
            # we won't be able to reduce it
            return list(set_top_childdir)

        top_childdir = next(iter(set_top_childdir))
        mixcli.info(f'Reducing the single top-level dir from extracted content: {top_childdir}')
        src_dir = os.path.join(out_dir, top_childdir)
        dst_dir = out_dir
        mixcli.debug(f'Copying everything in {src_dir} to {dst_dir}')
        try:
            for f in Path(src_dir).glob('*'):
                # mixcli.debug(f'Copying {f} to {dst_dir}')
                if os.path.isfile(f):
                    shutil.copy(f, dst_dir)
                else:
                    dst_subdir = os.path.join(dst_dir, os.path.basename(f))
                    #print(dst_subdir)
                    os.mkdir(dst_subdir)
                    shutil.copytree(f, os.path.join(dst_dir, f), dirs_exist_ok=True)
        except Exception as ex:
            mixcli.info(f'Error copying content from [{src_dir}] to [{out_dir}].')
            mixcli.info('Do not use reduce-dirs argument')
            return out_dir
        try:
            # mixcli.debug(f'Removing {src_dir}')
            shutil.rmtree(src_dir)
        except Exception as ex:
            mixcli.info(f'Error removing [{src_dir}] to clean-up.')
            mixcli.info('Do not use reduce-dirs argument')
            return out_dir


def nlu_export_qnlp(mixcli: MixCli, project_id: Union[str, int], out_dir: str, expand_zip: bool = False,
                    reduce_dirs: bool = False) -> Union[str, List[str]]:
    """
    Export NLU model to QuickNLP format project

    :param mixcli:
    :param project_id:
    :param out_dir:
    :param expand_zip: Expand the ZIP archive
    :param reduce_dirs:
    :return:
    """
    proj_id = assert_id_int(project_id, 'project')
    # make sure out_dir is a valid output dir
    if not os.path.isdir(out_dir):
        raise RuntimeError(f'Not a valid output dir: {out_dir}')
    qnlp_zip_bytes: bytes = pyreq_nlu_export_quicknlp(mixcli.httpreq_handler, project_id=proj_id)
    proj_meta = get_project_meta(mixcli, project_id=proj_id)
    if not expand_zip:
        # just save the ZIP archive that contains the QuickNLP project data
        zip_fn_tmplt = '%ID%__%NAME%__QuickNLP_Project.zip'
        zip_fn = get_project_id_file(project_id=proj_id, project_meta=proj_meta, fn_tmplt=zip_fn_tmplt)
        zip_outpath = os.path.join(out_dir, zip_fn)
        mixcli.debug(f'Saving received QuickNLP project ZIP to {zip_outpath}')
        try:
            with open(zip_outpath, 'wb') as fho_zip:
                fho_zip.write(qnlp_zip_bytes)
            return zip_outpath
        except Exception as ex:
            raise RuntimeError(f'Error writing ZIP file: {zip_outpath}') from ex
    else:
        # we should extract the ZIP content from the bytes
        expdir_nm_tmplt = '%ID%__%NAME%__QuickNLP_Project'
        expdir_nm = get_project_id_file(project_id=proj_id, project_meta=proj_meta, fn_tmplt=expdir_nm_tmplt)
        path_expdir = os.path.join(out_dir, expdir_nm)
        return extract_zip(mixcli, zip_bytes=qnlp_zip_bytes, out_dir=path_expdir, reduce_dirs=reduce_dirs)


def cmd_nlu_export(mixcli: MixCli, **kwargs: Union[bool, str, List[str]]):
    """
    Default function when Mixcli nlu export command is called, export Mix project NLU models to TRSX.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    proj_id = assert_id_int(kwargs['project_id'], 'project')
    loc = kwargs['locale']
    out_file = kwargs['out_file']
    export_type = kwargs['export_type']
    expfn_tmplt = kwargs['fn_tmplt'] if 'fn_tmplt' in kwargs else None

    def valid_qnlp_only_args(arg_nm, **kwas):
        if arg_nm in kwas and kwas[arg_nm]:
            raise RuntimeError(f'"{arg_nm}" only available when "export-type" is {EXPORT_ARTIFACT_QNLP}')

    # perform preliminary validation regarding exporting to QuickNLP project
    if export_type == EXPORT_ARTIFACT_QNLP:
        if not os.path.isdir(out_file):
            raise RuntimeError(f'"out-file" must be existing dir when export to QuickNLP data: {out_file}')
    else:
        # if export type is not qnlp, some arguments should not be used
        valid_qnlp_only_args('expand-zip', **kwargs)
        valid_qnlp_only_args('reduce-dirs', **kwargs)

    if export_type == EXPORT_ARTIFACT_TRSX:
        _data_types = kwargs['data_types']
        str_data_types = '[{list_types}]'.format(list_types=','.join(_data_types))
        if out_file and os.path.isdir(out_file):
            proj_meta = get_project_meta(mixcli, project_id=proj_id)
            file_basename = get_project_id_file(project_id=proj_id, project_meta=proj_meta, model='NLU', ext='.trsx',
                                                fn_tmplt=expfn_tmplt)
            out_file = os.path.join(out_file, file_basename)
        mixcli.info(f"Export NLU model with {str_data_types} from "
                    f"project {proj_id} locale {loc} "
                    f"to TRSX {out_file}")
        nlu_export_trsx(mixcli, project_id=proj_id, locale=loc, out_trsx=out_file, export_types=_data_types)
    elif export_type == EXPORT_ARTIFACT_QNLP:
        # out-file must be an existing directory when exporting to QuickNLP
        exp_zip: bool = kwargs['expand_zip']
        red_dirs: bool = kwargs['reduce_dirs']
        nlu_export_qnlp(mixcli, project_id=proj_id, out_dir=out_file, expand_zip=exp_zip, reduce_dirs=red_dirs)
    else:
        raise ValueError(f'Unsupported NLU models export type: {export_type}')
    return True


@cmd_regcfg_func('nlu', 'export', 'Export NLU model to a TRSX file', cmd_nlu_export)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='aa_AA_LOCALE', required=True,
                               help='aa_AA locale code')
    cmd_argparser.add_argument('-t', '--export-type', required=False,
                               choices=EXPORT_TYPES, default=EXPORT_ARTIFACT_TRSX, metavar='NLU_EXPORT_TYPE',
                               help=f'Type of artifact to export NLU models, choose from {_STR_EXPORT_TYPES}')
    cmd_argparser.add_argument('-o', '--out-file', metavar='OUTPUT_FILE', required=True,
                               help='Output file for NLU model export')
    cmd_argparser.add_argument('-d', '--data-types', nargs='+', choices=TRSX_DATATYPES, required=False,
                               default=TRSX_DATATYPES, metavar='DATA_TYPES_IN_EXPORT',
                               help=f'NLU data type(s) to include in TRSX, enums from {_STR_DATATYPES}')
    cmd_argparser.add_argument('-e', '--expand-zip', action='store_true',
                               help='When export to QuickNLP project, expand the received ZIP archive')
    cmd_argparser.add_argument('-r', '--reduce-dirs', action='store_true',
                               help='Try to reduce directory levels in extracted content from QuickNLP ZIP')
    cmd_argparser.add_argument('-T', '--fn-tmplt', metavar='EXPORT_FILENAME_TMPLT', required=False,
                               help="Template for name of exported file/archive. See epilog for available specifiers")
    cmd_argparser.epilog = """The following specifiers can be used in tmplt:
%ID% for project ID, %NAME% for project name, %MODEL% for *model_name* argument,
%TIME% for time stamp which should be datetime formatter string and by default '%Y%m%dT%H%M%S'"""
