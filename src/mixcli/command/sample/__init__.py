"""
mixcli (NLU) sample command group
"""
from mixcli import MixCli
from ..intent.list import list_nlu_intent as list_intent


def assert_intent_in_nlu_locale(mixcli: MixCli, project_id: int, locale: str, intent: str):
    """
    Assert if a give intent (name) exists in locale of NLU model of Mix project

    :param mixcli: MixCli instance
    :param project_id: Mix project ID
    :param locale: locale of NLU model
    :param intent: name of intent to verify existence
    :return: if intent not in the list of intent names from locale of NLU model of project, raise RuntimeError,
    else return True.
    """
    # we want to verify if intent exists for locale of NLU model in project
    intent_names = list_intent(mixcli, project_id=project_id, locale=locale)
    if intent not in intent_names:
        raise RuntimeError(f'Specified intent {intent} not exist for ' +
                           f'project #{project_id} locale {locale}: {repr(intent_names)}')
    return True
