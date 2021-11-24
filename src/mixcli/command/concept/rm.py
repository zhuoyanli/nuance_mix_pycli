"""
MixCli **concept** command group **rm** command.

This command will remove an NLU entity from NLU ontology of a Mix project.
"""
from argparse import ArgumentParser
from typing import Union

from .list import list_concepts
from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, MixLocale
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, DELETE_METHOD

KNOWN_PREDEFINED_CONCEPT_EXCEPTIONS = {'DATE', 'TIME', 'YES_NO'}
"""Set of known exception concepts whose metas look like custom but indeed are predefined"""


def pyreq_rm_concepts(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str, concept: str) -> bool:
    """
    Remove concept from Mix project with project_id and in locale 'locale', by sending requests to API endpoint
    with Python 'requests' package.

    API endpoint
    ::
        DELETE /nlu/api/v1/ontology/{project_id}/concepts/{concept}?locale={locale}.

    :param httpreq_handler: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :param locale: the locale code in aa_AA
    :param concept: name of concept to remove
    :return: True
    """
    api_endpoint = f'/nlu/api/v1/ontology/{project_id}/concepts/{concept}?locale={locale}'
    _ = httpreq_handler.request(url=api_endpoint, method=DELETE_METHOD, default_headers=True, json_resp=False)
    if _:
        raise ValueError(f'No response expected for ' +
                         f'removing concept {concept}: project {project_id} locale {locale}: {_}')
    # no response is expected for removing concept from project NLU models
    return True


def rm_concepts(mixcli: MixCli, project_id: Union[str, int], locale: str, concept: str) -> bool:
    """
    Get the list of concepts from Mix project with project_id and in locale 'locale'.

    :param mixcli: a MixCli instance
    :param project_id: Mix project ID
    :param locale: the locale code in aa_AA
    :param concept: name of concept to remove
    :return: True
    """
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    return pyreq_rm_concepts(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc, concept=concept)


def cmd_concept_rm(mixcli: MixCli, **kwargs: str):
    """
    Default function when MixCli concept list command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    proj_id = kwargs['project_id']
    locale = kwargs['locale']
    concept = kwargs['concept']
    # we take the list of existing custom concepts/entities for validation
    ja_cur_custom_concepts = list_concepts(mixcli, project_id=proj_id, locale=locale, include_predefined=False)
    list_cur_custom_concept = [c_meta['name'] for c_meta in ja_cur_custom_concepts]
    if concept not in list_cur_custom_concept:
        raise ValueError(f'Target concept not found in project {proj_id} locale {locale}: {concept}')
    rm_concepts(mixcli, project_id=proj_id, locale=locale, concept=concept)
    mixcli.info(f'Successfully removed concept "{concept} from project {proj_id} locale {locale}')
    return True


@cmd_regcfg_func('concept', 'rm', 'Remove concept for Mix project NLU models', cmd_concept_rm)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='aa_AA_LOCALE', required=True, help='aa_AA locale code')
    cmd_argparser.add_argument('-c', '--concept', metavar='CONCEPT_NAME', required=True,
                               help='Name of concept to remove')
