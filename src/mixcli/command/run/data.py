"""
A module providing all data and utility class supports for command processing in **script** module.
"""
import codecs
import copy
import json
import shlex
from abc import ABCMeta, abstractmethod
import re
from typing import Dict, Any
from argparse import ArgumentParser
from typing import List, Optional, Tuple, Callable

from mixcli import MixCli
from mixcli.util.logging import Loggable

ARGPARSER_VARARG_SUBVAR_VAL_SEP = '='
"""The separator symbol used in run script command 'var' argument to join substituting variable names and values"""


class VariableSub:
    """
    Utility class to process variable/substituting-value specification and perform lookup and substitution in strings.
    """
    def __init__(self, var_val_pairs: Optional[List[str]]):
        """
        Constructor.

        :param var_val_pairs: A dict where keys are variables (without '$') while values are tuples of compiled Pattern
        instances for the variable (with '$') and values (to substitute) for variables.
        """
        self._ptnmap_var_val: Optional[Dict[str, Tuple[re.Pattern, str]]] = None
        if var_val_pairs:
            self._ptnmap_var_val = dict()
            for var_val_pair in var_val_pairs:
                cnt_eq_sym = var_val_pair.count(ARGPARSER_VARARG_SUBVAR_VAL_SEP)
                if cnt_eq_sym < 1:
                    raise RuntimeError(
                        f'No f{ARGPARSER_VARARG_SUBVAR_VAL_SEP} found in var & value pair: {var_val_pair}')
                elif cnt_eq_sym > 1:
                    raise RuntimeError(f'Only one f{ARGPARSER_VARARG_SUBVAR_VAL_SEP} separator supported ' +
                                       f'in var & value pair: {var_val_pair}')
                var, val = var_val_pair.split(ARGPARSER_VARARG_SUBVAR_VAL_SEP)
                # we must append the backslash here because '$' is a reserved keyword in regexp
                self._ptnmap_var_val[var] = (re.compile('\\$' + var), val)

    def find_matched_var(self, text: str) -> List[Tuple[re.Pattern, str]]:
        """
        Look for variables whose patterns are found in target text.

        :param text: Target text string where occurences of variable patterns will be looked up .
        :return:
        """
        matched_var_val_tuple = []
        for var, tpl_ptn_val in self._ptnmap_var_val.items():
            # unpack
            (ptn_var, val) = tpl_ptn_val
            if ptn_var.search(text):
                matched_var_val_tuple.append(tpl_ptn_val)
        return matched_var_val_tuple

    def sub_text_if_needed(self, src_txt: str, logger: Loggable = None) -> str:
        """
        Replace all substrings in source text that are matched by one pattern in Pattern_to_ReplaceText mapping with
        the corresponding replacement text. Please note that we support only one pattern to match substrings in source
        text: If there are two or more patterns matched, exceptions will be raised.

        :param src_txt: Source text within which matching substrings will be looked up.
        :param logger: mixcli.util.logging.Loggable instance
        :return:
        """
        if not self._ptnmap_var_val:
            return src_txt
        final_text = src_txt
        # We find all the (pattern, repl_text) pairs in attern_to_ReplaceText
        matched_varptn_val: List[Tuple[re.Pattern, str]] = self.find_matched_var(final_text)
        if len(matched_varptn_val) > 1:
            raise RuntimeError(f'More than one var matching {final_text}')
        elif len(matched_varptn_val) == 1:
            ptnvar: re.Pattern = matched_varptn_val[0][0]
            to_repl: str = matched_varptn_val[0][1]
            if logger:
                logger.debug('Replacing "{ptn}" in "{orig_t}" with "{repl_t}"'.
                             format(ptn=ptnvar.pattern.replace("\\", ""),
                                    orig_t=final_text,
                                    repl_t=to_repl))
            final_text = matched_varptn_val[0][0].sub(to_repl, final_text)
        return final_text


class MixCliCmd:
    """
    Representation of a MixCli command, including command group, end command, and optionally arguments.
    """
    def __init__(self, cmd_group: str, cmd: str, args: Optional[List[str]] = None,
                 line_no: Optional[int] = None, cmd_no: Optional[int] = None):
        self._cmd_grp = cmd_group
        self._cmd = cmd
        self._args: Optional[List[str]] = None if not args else copy.copy(args)
        self._cmdline_cmd: List[str] = [self._cmd_grp, self._cmd]
        if self._args:
            self._cmdline_cmd += self._args
        self._repr_ = None
        self._line_no: Optional[int] = line_no
        self._cmd_no: Optional[int] = cmd_no

    @classmethod
    def from_strs(cls, str_list: List[str], line_no: Optional[int] = None, cmd_no: Optional[int] = None):
        """
        Build a MixCliCmd instance from a list of string, which are supposed to make up for the complete command.
        That being said, this list of string shall contain at least two elements, command group and end command

        :param cmd_no:
        :param line_no:
        :param str_list: List of strings
        :return: MixCliCmd instance
        """
        if len(str_list) < 2:
            raise RuntimeError(f'At least two strings expected (group, cmd) for MixCliCmd: {repr(str_list)}')
        return MixCliCmd(str_list[0], str_list[1], str_list[2:], line_no=line_no, cmd_no=cmd_no)

    def cmdline_command(self) -> List[str]:
        return self._cmdline_cmd

    def cmdline_cmd_repr(self, cmdline_cmd: List[str]):
        s = shlex.join(cmdline_cmd)
        if self._line_no:
            return f'line #{self._line_no}: '+s
        elif self._cmd_no:
            return f'cmd #{self._cmd_no}: '+s
        else:
            return s

    def __repr__(self) -> str:
        if not self._repr_:
            self._repr_ = self.cmdline_cmd_repr(self._cmdline_cmd)
        return self._repr_

    def __str__(self):
        return self.__repr__()


ScParserYieldCmdType = Tuple[int, bool, MixCliCmd]


class ScriptParser(metaclass=ABCMeta):
    """
    Abstraction of a Parser on MixCli command scripts. The main function would be **commands** which return
    a list of command(s) from parsing scripts.
    """
    def __init__(self, script_path, var_val_sub: Optional[VariableSub] = None):
        self._script = script_path
        self._var_val_sub = var_val_sub

    @abstractmethod
    def commands(self, logger: Loggable) -> List[ScParserYieldCmdType]:
        pass

    @property
    def script(self) -> str:
        return self._script


class ShellScriptParser(ScriptParser):
    """
    Run sequence of MixCli commands from shell script format files.
    The expected shell script style file is a file where one non-empty line contains a MixCli command and arguments,
    except for lines starting with '#', which are considered comments and to be skipped from execution.
    For example, a valid shell-script format script for this function may contain the following two lines:

    sys version |br|
    project get --project-id 11037 --out-file project_meta_11037.json |br|

    The variable-value substitution feature of this **run script** command is also supported for those shell-script
    format scripts. For example, a script with following two lines, when running with **-v PROJ_ID=11037** argument,
    is equivalent to the aforementioned example script:

    sys version |br|
    project get --project-id $PROJ_ID --out-file project_meta_$PROJ_ID.json
    """
    PTN_SCRIPT_COMMENTLINE = re.compile(r'^\s*#')

    def __init__(self, path_shell_script: str, var_val_sub: VariableSub):
        ScriptParser.__init__(self, script_path=path_shell_script, var_val_sub=var_val_sub)

    @classmethod
    def is_commentline(cls, ln: str):
        match = cls.PTN_SCRIPT_COMMENTLINE.search(ln)
        if not match:
            return False, None
        return True, ln[match.end():]

    def commands(self, logger: Loggable) -> List[ScParserYieldCmdType]:
        with codecs.open(self._script, 'r', 'utf-8') as fhi_shscript:
            cmd_seq = []
            for ln_no, ln in enumerate(fhi_shscript):
                sln = ln.strip()
                if not sln:
                    continue
                # if the line is empty or start with SHSCRIPT_COMMENT_CHAR, default '#'
                to_skip, commented_content = self.is_commentline(sln)
                if to_skip:
                    sln = commented_content
                ln_final = sln
                # split the line in shell script syntax
                try:
                    cmd_chunks = []
                    # remove quoting if exist
                    for chunk in shlex.split(ln_final):
                        if chunk[0] == '"' and chunk[-1] == '"':
                            cmd_chunks.append(chunk[1:-1])
                        elif chunk[0] == "'" and chunk[-1] == "'":
                            cmd_chunks.append(chunk[1:-1])
                        else:
                            cmd_chunks.append(chunk)
                    # do variable replacement if necessary
                    if self._var_val_sub:
                        cmd_chunks = [self._var_val_sub.sub_text_if_needed(src_txt=c, logger=logger)
                                      for c in cmd_chunks]
                    cmd_seq.append((ln_no, to_skip, MixCliCmd.from_strs(cmd_chunks, line_no=ln_no+1)))
                except Exception as ex:
                    raise RuntimeError(f'Error parsing script with shell syntax: Line #{ln_no}, {ln_final}') from ex
            return cmd_seq


_JSP_CMD_BLK_CMD_FIELD = 'cmd'
_JSP_CMD_BLK_ARGS_FIELD = 'args'
_JSP_CMD_SKIP_FIELD = '.'
"""Add a field '.': true to the JSON cmd block to skip the command from execution"""


class JsonScriptParser(ScriptParser):
    """
    This module provides support to parse JSON files compliant with expected schema into a list of MixCli commands.
    The function to call should be script_to_cmd_list

    The whole JSON file should be a JSON rray whose elements are JSON objects that are of the following
    structure: A field named **cmd** whose value is a JSON array of JSON strings, and a field named **args**
    whose value is a JSON array, elements of which are either JSON strings or JSON number. The following content is
    an example script in JSON with two MixCli commands:

    [
      {<br/>
        "cmd": ["project", "build"],<br/>
        "args": ["--project-id", 11037, "--locale", "en-US", "--note", "Build from MixCli"]<br/>
      },<br/>
      {<br/>
        "cmd": ["app", "new-deploy"],<br/>
        "args": ["--ns", "zhuoyan.li@nuance.com", "--cfg-group", "ZhuoyanMixApps",
          "--cfg-tag", "NuanceNextBankingDemo", "-p", 5736, "-l", "en-US", "--promote"]<br/>
      }
    ]

    """
    def __init__(self, json_script_path: str, var_val_sub: Optional[VariableSub] = None):
        ScriptParser.__init__(self, script_path=json_script_path, var_val_sub=var_val_sub)

    @classmethod
    def _should_skip_json_cmd_blk(cls, cmd_blk: Dict) -> bool:
        """
        If we should skip the CMD block in JSON script, by checking if there is a field with name _JSP_CMD_SKIP_FIELD

        :param cmd_blk: JSON object representing a command block from JSON script.
        :return: True if should skip, False otherwise
        """
        return _JSP_CMD_SKIP_FIELD in cmd_blk

    @classmethod
    def _assert_json_cmd_blk(cls, cmd_blk) -> bool:
        """
        Assert the block of command from JSON script is valid JSON object and compliant with expected schema/model.

        :param cmd_blk: JSON object representing a command block from JSON script.
        :return: True
        """
        assert isinstance(cmd_blk, dict), f'Command block must be JSON objects: {cmd_blk}'
        cmd_toskip = False
        if cls._should_skip_json_cmd_blk(cmd_blk):
            cmd_toskip = True
            cmd_blk.pop(_JSP_CMD_SKIP_FIELD)
        assert _JSP_CMD_BLK_CMD_FIELD in cmd_blk, f"Command block should include '{_JSP_CMD_BLK_CMD_FIELD}' field"
        cmd_field = cmd_blk[_JSP_CMD_BLK_CMD_FIELD]
        violated = False
        if isinstance(cmd_field, list):
            for cmd_trunk in cmd_field:
                if not isinstance(cmd_trunk, str):
                    violated = True
                    break
        else:
            violated = True
        assert not violated, "Command block must be an array of string(s)"
        assert (len(cmd_blk) == 2 and _JSP_CMD_BLK_ARGS_FIELD in cmd_blk) or len(cmd_blk) == 1, \
            f"Command block can include either only '{_JSP_CMD_BLK_CMD_FIELD}' field or " + \
            f"'{_JSP_CMD_BLK_CMD_FIELD}' & '{_JSP_CMD_BLK_ARGS_FIELD}' (array) fields"
        if len(cmd_blk) == 2 and _JSP_CMD_BLK_ARGS_FIELD in cmd_blk:
            cmd_blk_args_field = cmd_blk[_JSP_CMD_BLK_ARGS_FIELD]
            violated = False
            if isinstance(cmd_blk_args_field, str) or isinstance(cmd_blk_args_field, int):
                ...
            elif isinstance(cmd_blk_args_field, list):
                for arg_blk in cmd_blk_args_field:
                    if not isinstance(arg_blk, str) and not isinstance(arg_blk, int):
                        violated = True
                        break
            else:
                violated = True
            assert not violated, f'{_JSP_CMD_BLK_ARGS_FIELD} block must be string/int or array of string/int'
        if cmd_toskip:
            cmd_blk[_JSP_CMD_SKIP_FIELD] = True
        return True

    @classmethod
    def _assert_cmd_json_script(cls, script_as_jsonobj: Any) -> bool:
        """
        Assert the JSON object from parsing the script file is compliant with expected model.

        :param script_as_jsonobj: The JSON object generated by parsing script as JSON.
        :return: True
        """
        assert isinstance(script_as_jsonobj, list), "JSON script must be list of cmd block(s)"
        for cmd_blk in script_as_jsonobj:
            cls._assert_json_cmd_blk(cmd_blk)
        return True

    def commands(self, logger: Loggable = None) -> List[ScParserYieldCmdType]:
        with codecs.open(self._script, 'r', 'utf-8') as fhi_jss:
            json_script = json.load(fhi_jss)
            self._assert_cmd_json_script(json_script)
            cmd_list = []
            blk_idx = 0
            for cmd_blk in json_script:
                cmd_chunks = []
                cmd_chunks.extend(cmd_blk['cmd'])
                if _JSP_CMD_BLK_ARGS_FIELD in cmd_blk:
                    cur_arg = cmd_blk[_JSP_CMD_BLK_ARGS_FIELD]
                    # do not forget we need to check if the argument string/text contains variables
                    # that should be substituted by their corresponding values from command line
                    if isinstance(cur_arg, str):
                        cur_arg = self._var_val_sub.sub_text_if_needed(src_txt=cur_arg, logger=logger)
                        cmd_chunks.append(cur_arg)
                    else:
                        for cur_arg in cmd_blk[_JSP_CMD_BLK_ARGS_FIELD]:
                            cur_arg = self._var_val_sub.sub_text_if_needed(src_txt=str(cur_arg), logger=logger)
                            cmd_chunks.append(cur_arg)
                to_skip = self._should_skip_json_cmd_blk(cmd_blk)
                cmd_list.append((blk_idx, to_skip, MixCliCmd.from_strs(cmd_chunks)))
                blk_idx += 1
        return cmd_list


class ScriptRunner:
    """
    Utility class to run commands from parsing of MixCli scripts with ScriptParser instance, and do logging accordingly.
    """
    def __init__(self, script_parser: ScriptParser):
        """
        Constructor.

        :param script_parser: The ScriptParser instance to parse MixCli scripts and yield MixCli commands
        """
        self._script_parser = script_parser

    @classmethod
    def _log_command(cls, cmd: MixCliCmd, logger: Loggable, log_level: Optional[int] = None,
                     cmd_to_str: Callable[[MixCliCmd], str] = None):
        """
        Log the processing on a command.

        :param cmd: A list of string represent a complete MixCli command, which includes command group, command name,
        and optionally the arguments for command.
        :param logger: A Loggable instance.
        :param log_level: Logging level from system 'logging' module
        :param cmd_to_str: A function to generate representation string for the MixCli command.
        :return: None
        """
        if not cmd_to_str:
            cs = repr(cmd)
        else:
            cs = cmd_to_str(cmd)

        if not log_level:
            logger.info(cs)
        else:
            logger.log(log_msg=cs, log_level=log_level)

    def skip_cmd(self, cmd: MixCliCmd, logger: Loggable):
        """
        Skip command

        :param cmd: MixCliCmd instance
        :param logger: A Loggable instance.
        :return: None
        """
        def _repr(c):
            return 'Skipped: ' + repr(c)
        self._log_command(cmd, logger=logger, cmd_to_str=_repr)

    def do_dryrun(self, cmd: MixCliCmd, logger: Loggable):
        """
        Do a dry-run on command that is represented by a list of strings.

        :param cmd: MixCliCmd instance
        :param logger: A Loggable instance.
        :return: None
        """
        def _repr(c):
            return 'Dry-run: ' + repr(c)
        self._log_command(cmd, logger=logger, cmd_to_str=_repr)

    def log_run_cmd(self, cmd: MixCliCmd, logger: Loggable):
        """
        Log the running of a MixCli command

        :param cmd: MixCliCmd instance
        :param logger: A Loggable instance.
        :return: None
        """
        def _repr(c):
            return 'Running ' + repr(c)
        self._log_command(cmd, logger=logger, cmd_to_str=_repr)

    def run_script(self, mixcli: MixCli, dry_run: bool = False) -> bool:
        """
        Run sequence of MixCli commands from JSON script

        :param mixcli: MixCli instance
        :param dry_run:
        :return: True
        """
        try:
            cmd_list: List[ScParserYieldCmdType] = self._script_parser.commands(logger=mixcli)
        except Exception as ex:
            raise RuntimeError(f'Error parsing MixCli cmd script: {self._script_parser.script}') from ex

        def _skip_repr(c):
            return 'Skipped: ' + repr(c)
        for cmd_no, to_skip, mc_cmd in cmd_list:
            if to_skip:
                self._log_command(mc_cmd, logger=mixcli, cmd_to_str=_skip_repr)
                continue
            if dry_run:
                self.do_dryrun(mc_cmd, logger=mixcli)
                continue
            self.log_run_cmd(mc_cmd, logger=mixcli)
            try:
                mixcli_argparser: ArgumentParser = mixcli.cmd_argparser
                try:
                    cmd_args = mixcli_argparser.parse_args(mc_cmd.cmdline_command())
                except SystemExit:
                    raise RuntimeError(f'Invalid MixCli command: {repr(mc_cmd)}')
                mixcli.proc_cmd_args(argparser=mixcli_argparser, cmd_args=cmd_args)
            except Exception as ex:
                raise RuntimeError(f'Cmd failed and run aborted: {repr(mc_cmd)}') from ex
        return True
