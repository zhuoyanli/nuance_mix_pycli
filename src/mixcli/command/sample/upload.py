"""
Mix **sample** command group **upload** command.

This command is useful to upload single utt or list of such, optionally for given intent, into NLU model of Mix project.
"""
import codecs
import json
import os.path
from argparse import ArgumentParser
from typing import Union, Optional, Dict, List

from mixcli import MixCli
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import assert_id_int, MixLocale, write_result_outfile


def pyreq_sample_upload_utts(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str,
                             src_utts: List[str], dest_intent: Optional[str] = None):
    """
    API endpoint: POST /nlu/api/v1/data/<proj_id>/utterances?type=TXT&locale=<locale>[&intent=<dest_intent>]

    :param httpreq_handler:
    :param project_id:
    :param locale:
    :param src_utts:
    :param dest_intent:
    :return:
    """
    api_endpoint = f'/nlu/api/v1/data/{project_id}/utterances?type=TXT&locale={locale}'
    if dest_intent:
        api_endpoint += f'&intent={dest_intent}'
    data_str = json.dumps(src_utts)
    headers = httpreq_handler.get_default_headers()
    headers.update({'Content-Type': 'application/json'})
    upload_resp = httpreq_handler.request(url=api_endpoint, method=POST_METHOD, headers=headers, data=data_str,
                                          data_as_str=True, json_resp=True)
    return upload_resp


def sample_upload_txt(mixcli: MixCli, project_id: Union[int, str], locale: str,
                      src_utt: Optional[str] = None, src_utt_txt: Optional[str] = None,
                      dest_intent: Optional[str] = None) -> Dict:
    """
    Upload raw sample(s) from plain text txt file one per line to NLU model of Mix project by
    sending request to Mix API endpoint with 'requests' package.

    :param src_utt: Raw utterance/sample to be uploaded, mutually exclude with src_utt_txt
    :param mixcli: MixCli instance
    :param project_id: Mix project ID
    :param locale: Locale of NLU model to which new samples are to be uploaded.
    :param src_utt_txt: Path to source plain text file containing raw utterance/sample one per line
    :param dest_intent: Intent name to be assigned to new sample(s), if skipped samples go to **UNASSIGNED_SAMPLES**
    :return:
    """
    if src_utt and src_utt_txt:
        raise RuntimeError(f'Cannot use both src_utt and src_utt_txt for sample_upload_txt')
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    # need a list
    src_raw_utts = []
    if src_utt:
        src_raw_utts.append(src_utt)
    else:
        rp_src_txt = src_utt_txt
        try:
            rp_src_txt = os.path.realpath(src_utt_txt)
            with codecs.open(rp_src_txt, 'r', 'utf-8') as fhi_srcutt:
                for ln in fhi_srcutt.readlines():
                    sln = ln.strip()
                    if not sln:
                        continue
                    src_raw_utts.append(sln)
        except FileNotFoundError as ex:
            raise RuntimeError(f'Invalid input file: {rp_src_txt}') from ex
        except Exception as ex:
            raise RuntimeError(f'Error reading raw utt from plain text file: {rp_src_txt}') from ex
    upload_resp = pyreq_sample_upload_utts(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc,
                                           src_utts=src_raw_utts, dest_intent=dest_intent)
    return upload_resp


def cmd_sample_upload(mixcli: MixCli, **kwargs):
    """
    Default function when command is invoked on command line

    :param mixcli: MixCli instance
    :param kwargs:
    :return:
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    dst_intent = kwargs['dest_intent']
    src_txt = kwargs['intxt']
    src_utt = kwargs['utt']
    upload_resp = sample_upload_txt(mixcli, project_id=proj_id, locale=loc, src_utt=src_utt, src_utt_txt=src_txt,
                                    dest_intent=dst_intent)
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=json.dumps(upload_resp), out_file=out_file, logger=mixcli)
    else:
        mixcli.info(json.dumps(upload_resp))
        info_msg = f'Successfully uploaded raw NLU samples from {src_txt} to project {proj_id} locale {loc}'
        if dst_intent:
            info_msg += f' intent {dst_intent}'
        mixcli.info(info_msg)
    return True


@cmd_regcfg_func('sample', 'upload', 'Upload samples to NLU model of Mix project', cmd_sample_upload)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='aa_AA_LOCALE', required=True,
                               help='aa_AA locale code')
    cmd_argparser.add_argument('-d', '--dest-intent', metavar='DEST_INTENT', required=False,
                               help='Intent name to be assigned for the new samples')
    mutexgrp_src = cmd_argparser.add_mutually_exclusive_group(required=True)
    mutexgrp_src.add_argument('-i', '--intxt', metavar='PLAINTEXT_FILE',
                              help='Plain text file containing raw utterances one per line')
    mutexgrp_src.add_argument('--utt', type=str, metavar='NEW SAMPLE', help='New raw sample to be uploaded.')
    cmd_argparser.add_argument('-o', '--out-file', metavar='OUTPUT_FILE', required=False,
                               help='Output file for upload result')
