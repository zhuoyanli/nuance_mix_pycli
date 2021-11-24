"""
This command makes use of Mix gRPC API(s) to export/download specific deployed models (NLU/ASR/Dialog)
from Mix SaaS gRPC service.

Please note that we expect users to provide Python dependency packages/libraries which are necessary to
connect to Mix gRPC service, most particularly the "grpc(-io)" package and the Mix gRPC API Python proto stub.
We do not include those dependencies as dependency requirement for MixCli, nor expect Python environment
that runs MixCli to have those dependencies installed.
"""
import codecs
import json
import sys
from argparse import ArgumentParser
from typing import List, Dict, Union
import os.path

from mixcli import MixCli, Loggable
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util import assert_json_field_and_type

# this is the default gRPC service endpoint
PROD_MIXAPI_GRPC_URL = "mix.api.nuance.com:443"

GRPC_RESOURCE_NLU = 'NLU'
GRPC_RESOURCE_ASR = 'ASR'
GRPC_RESOURCE_DLG = 'Dialog'
EXPORT_GRPC_RESOURCES = [GRPC_RESOURCE_NLU, GRPC_RESOURCE_ASR, GRPC_RESOURCE_DLG]
_STR_GRPC_RES = '[{l}]'.format(l=','.join(EXPORT_GRPC_RESOURCES))


def add_mix_grpc_dep_pypath(mix_grpc_pypath: Union[str, List[str]], logger: Loggable):
    if isinstance(mix_grpc_pypath, str):
        mix_grpc_pypath = [mix_grpc_pypath]
    for p in mix_grpc_pypath:
        if not os.path.isdir(p):
            raise FileNotFoundError(f'Invalid directory: {p}')
        logger.debug(f'Adding to PYTHONPATH: {p}')
        sys.path.append(p)


def export_grpc_resource(export_cfg: Dict, mix_grpc_pypath: str, auth_token: str, res2export: str,
                         output_file: str, logger: Loggable):
    add_mix_grpc_dep_pypath(mix_grpc_pypath=mix_grpc_pypath, logger=logger)
    logger.debug('Importing dep modules: gRPC')
    try:
        import grpc
        logger.debug('Importing Mix gRPC API Python stubs')
        # these would be the Nuance Mix gRPC config packages
        from nuance.mixapi_pb2 import DownloadAppConfigArtifactsRequest, ListAppConfigsRequest
        from nuance.mixapi_pb2_grpc import AppConfigsStub
    except Exception as ex:
        raise RuntimeError('Failed to import Python pkg grpc/nuance, check Python path: {p}'.format(
            p=mix_grpc_pypath
        ))

    # this funciton essentially taken from MTT
    def create_grpc_channel(service_url, token):
        call_credentials = grpc.access_token_call_credentials(token)
        channel_credentials = grpc.ssl_channel_credentials()
        channel_credentials = grpc.composite_channel_credentials(channel_credentials, call_credentials)
        channel = grpc.secure_channel(service_url, credentials=channel_credentials)
        return channel

    # this function essentially taken from Merlin Python backend
    def download_app_config_artifacts(mixapi_grpc_url, mixapi_token,
                                      app_id, namespace, region_name, env_name,
                                      ctx_tag, lang, res2exp):
        """
        Download Mix project/application artifact as byte string
        :param mixapi_grpc_url: string, URL for Mix gRPC API service endpoint, in form of "FQHN:PORT"
        :param mixapi_token: string, Mix API authentication token
        :param app_id: string, APP_ID for the deployment configuration, find it in Mix MANAGE, Applications, Configs
        :param namespace: string, namespace for the user account that promotes deployment
        :param region_name: string, region for the deployment
        :param env_name: string, environment name for the deployment
        :param ctx_tag: string, context tag, find it in Mix NAMAGE, Applications, Configs
        :param lang: locale name in aaa-AAA format
        :param res2exp: string, NLU, ASR, or Dialog (case-sensitive)
        :return: Bytearray
        """
        """ Returns a byte array """
        logger.debug('Creating gRPC channel')
        with create_grpc_channel(mixapi_grpc_url, mixapi_token) as channel:
            stub = AppConfigsStub(channel)
            req = DownloadAppConfigArtifactsRequest(namespace=namespace,
                                                    region_name=region_name,
                                                    environment_name=env_name,
                                                    app_id=app_id,
                                                    tag=ctx_tag,
                                                    language=lang,
                                                    model_type=res2exp)
            logger.debug('Sending download request')
            ret = b''
            for a in stub.DownloadAppConfigArtifacts(req):
                # DownloadAppConfigArtifactsResponse
                ret += a.chunk
            logger.debug('Resource successfully retrieved')
            return ret

    # we expect the following fields to be available in Json config files
    expected_fields = ['appId', 'namespace', 'regionName', 'environmentName',
                       'contextTag', 'language']
    for ef in expected_fields:
        assert_json_field_and_type(export_cfg, ef)
    export_cfg['modelType'] = res2export
    grpc_url = PROD_MIXAPI_GRPC_URL
    atft = download_app_config_artifacts(mixapi_grpc_url=grpc_url, mixapi_token=auth_token,
                                         app_id=export_cfg['appId'],
                                         namespace=export_cfg['namespace'],
                                         region_name=export_cfg['regionName'],
                                         env_name=export_cfg['environmentName'],
                                         ctx_tag=export_cfg['contextTag'],
                                         lang=export_cfg['language'],
                                         res2exp=export_cfg['modelType'])
    # this would be a bit tricky because I have not tested what format the actual
    # artifacts would be in when the modelType is NLU or dlg. They (very likely) may not
    # be ZIP archives
    if atft:
        logger.debug(f'Saving downloaded content to: {output_file}')
        try:
            with codecs.open(output_file, 'wb') as fho_atft:
                fho_atft.write(atft)
            logger.info(f'Successfully saved exported resource(s) to: {output_file}')
        except Exception as ex:
            raise RuntimeError(f'Failed to write to: {output_file}') from ex


def cmd_grpc_export(mixcli: MixCli, **kwargs: Union[bool, str, List[str]]):
    grpc_export_cfg = kwargs['grpc_export_config']
    mix_grpc_pypath = kwargs['mix_grpc_pypath']
    res2export = kwargs['export_grpc_resource']
    out_file = kwargs['output_file']
    # read JSON from file
    try:
        with codecs.open(os.path.abspath(grpc_export_cfg), 'r', 'utf-8') as fhi_cfgjs:
            export_config = json.load(fhi_cfgjs)
    except Exception as ex:
        print(f"Error processing JSON from file {grpc_export_cfg}")
    export_grpc_resource(export_cfg=export_config, mix_grpc_pypath=mix_grpc_pypath, auth_token=mixcli.auth_token,
                         res2export=res2export, output_file=out_file, logger=mixcli)


@cmd_regcfg_func('grpc', 'export', 'Export NLU model to a TRSX file', cmd_grpc_export)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-c', '--export-cfg', dest='grpc_export_config', metavar='EXPORT_CONFIG', required=True,
                               help='Config used for gRPC resource export')
    cmd_argparser.add_argument('-g', '--grpc-pypath', dest='mix_grpc_pypath', nargs='+', required=True,
                               metavar='MIX_GRPC_PYPATH', help='Path to Mix gRPC Python dependencies')
    cmd_argparser.add_argument('-r', '--export-res', required=False, dest='export_grpc_resource',
                               choices=EXPORT_GRPC_RESOURCES, default=GRPC_RESOURCE_NLU,
                               metavar='GRPC_RESOURCE_AVAILABLE_TO_EXPORT',
                               help=f'Type of artifact to export NLU models, choose from {_STR_GRPC_RES}')
    cmd_argparser.add_argument('-o', '--out-file', dest='output_file', metavar='OUTPUT_FILE', required=True,
                               help='Output file for export')
