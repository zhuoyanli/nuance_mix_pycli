"""
MixCli **nlu** command group **try** command.

This command would replicate the 'Try' function in Mix.nlu UI to get a trial annotation from the latest run-time
NLU model, if exist.
"""
import codecs
import json
from argparse import ArgumentParser
from typing import Union, Optional, Dict, List

from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, MixLocale
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, PUT_METHOD, get_api_resp_payload_data


def nlu_intps_from_resp_payload(resp_payload: Dict) -> List[Dict]:
    return get_api_resp_payload_data(resp_payload)['data']


def pyreq_nlu_try_utt(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str, utt: str) -> Optional[Dict]:
    """
    Get try-annotation on utterance with latest run-time NLU model for a Mix project and locale, by sending requests
    to Mix API endpoint with Python 'requests' package.

    API endpoint: PUT nlu/api/v1/nlu/{proj_id}/engine/
    annotation?apiVersion=v2&withRuntimeJson=true&sources=nuance_custom_data&locale={loc}
    Request payload: A JSON array that contains a JSON string that is the utterance.

    :param httpreq_handler: HTTPRequestHandler to process requests and responses
    :param project_id: Mix project ID
    :param locale: Mix project NLU locale
    :param utt: The utterance to try annotation
    :return: JSON reponse payload from API endpoint
    """
    api_endpoint = f'nlu/api/v1/nlu/{project_id}/engine/' + \
                   f'annotation?apiVersion=v2&withRuntimeJson=true&sources=nuance_custom_data&locale={locale}'
    data = json.loads('[]')
    data.append(utt)
    resp = httpreq_handler.request(url=api_endpoint, method=PUT_METHOD, data=data,
                                   default_headers=True, json_resp=True)
    return resp


def nlu_try_utt(mixcli: MixCli, project_id: Union[int, str], locale: str,
                utt: Optional[str] = None, utt_file: Optional[str] = None
                ) -> Union[Optional[Dict], List[Optional[Dict]]]:
    """
    Get try-annotation on utterance with latest run-time NLU model for a Mix project and locale.

    :param utt_file:
    :param mixcli: MixCli instance
    :param project_id: Mix project ID
    :param locale: NLU locale
    :param utt:
    :return:
    """
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)

    if utt:
        try_resp = pyreq_nlu_try_utt(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc, utt=utt)
        # we return the same content that Mix.nlu 'TRY' UI would display 'as JSON'
        return try_resp
    elif utt_file:
        try_resps = []
        try:
            with codecs.open(utt_file, 'r', 'utf-8') as fhi_uttf:
                for ln in fhi_uttf.readlines():
                    ln_utt = ln.strip()
                    if not ln_utt:
                        continue
                    try_resp = pyreq_nlu_try_utt(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc, utt=ln_utt)
                    try_resps.append(try_resp)
            return try_resps
        except Exception as ex:
            raise RuntimeError(f'Error processing utts from file: {utt_file}') from ex
    else:
        raise RuntimeError('Not expecting both utt and utt_file args to be None')


def cmd_nlu_tryutt(mixcli: MixCli, **kwargs) -> bool:
    """
    Default functio when command is invoked in command line

    :param mixcli: MixCli instance
    :param kwargs:
    :return: True shall function successfully completes.
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    utt = kwargs['utt']
    uttf = kwargs['utt_file']
    nlu_try_anno = nlu_try_utt(mixcli, project_id=proj_id, locale=loc, utt=utt, utt_file=uttf)
    out_file = kwargs['out_file']
    if not out_file:
        mixcli.info(json.dumps(nlu_try_anno))
    else:
        write_result_outfile(content=nlu_try_anno, out_file=out_file, logger=mixcli, is_json=True)
    return True


@cmd_regcfg_func('nlu', 'try-utt', 'Try to annotate utterance with latest run-time NLU model', cmd_nlu_tryutt)
def config_cmd_argparser(argparser: ArgumentParser):
    """
    Configure the ArgumentParser for the command.

    :param argparser: The ArgumentParser instance that supports this command.
    :return: None
    """
    argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help="Mix project ID")
    argparser.add_argument('-l', '--locale', metavar='LOCALE', required=True, help='Locale for the NLU model')
    mutexgrp_utt = argparser.add_mutually_exclusive_group(required=True)
    mutexgrp_utt.add_argument('-u', '--utt', metavar='UTT_TO_TRY', help='Utterance to try to annotate')
    mutexgrp_utt.add_argument('-uf', '--utt-file', metavar='FILE_OF_UTT_TO_TRY',
                              help='File containing one utterance per line to try to annotate')
    argparser.add_argument('-o', '--out-file', metavar='OUTPUT_FILE', required=False, help='Send output to file')
