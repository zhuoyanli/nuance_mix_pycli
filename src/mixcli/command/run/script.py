"""
MixCli **run** command group **script** command.

This command would run sequences of MixCli commands from supported scripts. Currently this command supports the scripts
are prepared in tshell-script syntax files.

**Shell-script syntax files**: Those files are written in the same way as regular BASH shell scripts, except that

1. instead of BASH commands and/or executables, MixCli commands are used.

2. only supporting one line per command, no line-spanning

3. like shell-scripts, use '#' as first non-space char in the line to make the line as comment

The following content is an example script in shell-script syntax with three commands:

| # check system version
| sys version
| # get project meta data and save command out to JSON file
| project get --project-id 11037 --out-file project_meta_11037.json
| # build the project
| project build --project-id 11037 --locale en-US --note 'Build from MixCli'

Please take note that if there is failing command in the middle of execution, command would stop the execution and
all the remaining commands will be aborted.
"""
import re
from argparse import ArgumentParser
from re import Pattern
from typing import Dict, List, Tuple, Union, Optional

from .data import ARGPARSER_VARARG_SUBVAR_VAL_SEP, ScriptRunner, VariableSub, ShellScriptParser
from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func


def cmd_run_script(mixcli: MixCli, **kwargs: Union[bool, str, List[str]]) -> bool:
    """
    Default function when MixCli sys version command is called. Check Mix platform system version.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: json, command result in Json
    """
    # process substitution variables
    sub_var_val: Optional[List[str]] = kwargs['var']
    ptnmap_var_val: Dict[str, Tuple[Pattern, str]] = dict()
    if sub_var_val:
        for var_val_pair in sub_var_val:
            cnt_eq_sym = var_val_pair.count(ARGPARSER_VARARG_SUBVAR_VAL_SEP)
            if cnt_eq_sym < 1:
                raise RuntimeError(f'No f{ARGPARSER_VARARG_SUBVAR_VAL_SEP} found in var & value pair: {var_val_pair}')
            elif cnt_eq_sym > 1:
                raise RuntimeError(f'Only one f{ARGPARSER_VARARG_SUBVAR_VAL_SEP} separator supported ' +
                                   f'in var & value pair: {var_val_pair}')
            var, val = var_val_pair.split(ARGPARSER_VARARG_SUBVAR_VAL_SEP)
            # we must append the backslash here because '$' is a reserved keyword in regexp
            ptnmap_var_val[var] = (re.compile('\\$'+var), val)
    dryrun = kwargs['dryrun']
    if dryrun:
        mixcli.info('Using dry-run mode')
    var_val_sub = VariableSub(var_val_pairs=sub_var_val)
    shell_script = kwargs['shell']
    parser = ShellScriptParser(path_shell_script=shell_script, var_val_sub=var_val_sub)
    sc_runner = ScriptRunner(script_parser=parser)
    sc_runner.run_script(mixcli, dry_run=dryrun)
    return True


# noinspection PyUnusedLocal
@cmd_regcfg_func('run', 'script', 'Run mixcli commands from script', cmd_run_script)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('--shell', metavar='SCRIPT_IN_SHELLCMD', required=True,
                               help='Run mixcli commands as listed in shell-script format file')
    cmd_argparser.add_argument('-v', '--var', metavar='VAR_SUB_PAIRS', nargs='*', required=False,
                               help='Variable substitution pair as VAR_NAME=VAR_VALUE. ' +
                                    '$VAR_NAME in script will get replaced as VAR_VALUE')
    cmd_argparser.add_argument('--dryrun', action='store_true', help='Do not actually run the command')
