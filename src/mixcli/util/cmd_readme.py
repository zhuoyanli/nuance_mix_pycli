"""
Utility class to generate Markdown table displaying all registered MixCli command group, commands in each group,
and description for the command
"""
import codecs
import sys
from contextlib import contextmanager
from io import StringIO
from argparse import ArgumentParser
# we must import ..command as all the command groups and commands are registered there
# noinspection PyUnresolvedReferences
from typing import Optional
import re

# noinspection PyUnresolvedReferences
from .. import command, Loggable, create_mixcli_argparser, config_argparser_for_commands
from .commands import _cmd_register

cli_argparser = create_mixcli_argparser()
config_argparser_for_commands(cli_argparser)

cmd_grp_skip = {'example', 'model'}


class OutWriter:
    def __init__(self, out_handle, logger: Optional[Loggable] = None):
        self._ohdl = out_handle
        self._logger = logger

    @classmethod
    @contextmanager
    def open(cls, out_file=None, logger: Optional[Loggable] = None):
        if out_file:
            with codecs.open(out_file, 'w', 'utf-8') as fho:
                yield OutWriter(fho, logger=logger)
        else:
            yield OutWriter(sys.stdout, logger=None)

    def write(self, content, end: Optional[str] = None):
        self._ohdl.write(content)
        if end:
            self._ohdl.write(end)

    def println(self, content, end: Optional[str] = None):
        e = '\n'
        if end:
            e = end
        self.write(content=content, end=e)


PTN_RST_LNBLK = re.compile(r'^[ ]*\|(.*)$', re.M)
PTN_EXCESS_LNBLK = re.compile('(<br/>)+\n\n')


def rst_lineblock_to_md_linebreak(docstr: str) -> str:
    match = PTN_RST_LNBLK.search(docstr)
    while match:
        docstr = docstr[:match.start()] + docstr[match.start(1):match.end(1)] + '<br/>' + docstr[match.end(1):]
        # docstr = docstr[:match.start()] + docstr[match.start(1):]
        match = PTN_RST_LNBLK.search(docstr)
    docstr = PTN_EXCESS_LNBLK.sub('\n\n', docstr)
    return docstr


# noinspection PyProtectedMember
def out_md(ow: OutWriter):
    """
    Generate Markdown format content

    :param ow:
    :return:
    """
    ow.println('# Documentation on current MixCli commands', end='\n\n')
    ow.println('This README file is generated by **mixcli.util.readme_md** module. Do NOT edit manually.', end='\n\n')
    ow.println('Command groups and commands in this README are sorted in alphabetical order.', end='\n\n')
    ow.println(f'| <div style="width:50px">Group</div> | <div style="width:70px">Command</div> |' +
               f' <div style="width:200px">Description</div> | Brief command usage |')
    ow.println(f'| --- | --- | --- | --- |')
    cmd_grp_displayed = set()
    for cmd_grp in sorted(_cmd_register._registered_grp):
        if cmd_grp in cmd_grp_skip:
            continue
        cmd_to_argparser = dict()
        for cmd_grp_cmd_tuple, cmd_arg_parser in _cmd_register._cmd_grp_cmd_to_arg_parser.items():
            if cmd_grp_cmd_tuple[0] != cmd_grp:
                continue
            print(f'Processing cmd group {cmd_grp_cmd_tuple[0]}, cmd {cmd_grp_cmd_tuple[1]}')
            cmd_to_argparser[cmd_grp_cmd_tuple[1]] = cmd_arg_parser

        for cmd_in_grp in sorted(cmd_to_argparser.keys()):
            cmd_argparser = cmd_to_argparser[cmd_in_grp]
            cmd_grp_display = ''
            if cmd_grp not in cmd_grp_displayed:
                cmd_grp_display = cmd_grp
                cmd_grp_displayed.add(cmd_grp)
            print_buf = StringIO()
            cmd_argparser.print_usage(print_buf)
            # we strip all visually formatting linebreaks
            # we replace the bars in usage text with unicode so that they do not mess with Markdown table bars
            # we strip the leading 'usage: '
            # '\n' -> '<br/>': replace line breaks with inline-HTML soft line breaks for Markdown paragraphs
            # '|' -> '&#124;': replace any bars with HTML escaped chars
            # '__' ->  r'\_\_': double underscores are empharsizing in Markdown
            # r'usage: ' -> '': remove the leading word
            # 'mixcli ' -> '**mixcli** ' and etc: Make those words in bold
            cmd_usage = print_buf.getvalue().strip().\
                replace('\n', '<br/>'). \
                replace('|', '&#124;').\
                replace('__', r'\_\_').\
                replace(r'usage: ', '').\
                replace('mixcli ', '**mixcli** ').\
                replace(f' {cmd_grp} ', f' **{cmd_grp}** ').\
                replace(f' {cmd_in_grp} ', f' **{cmd_in_grp}** ')
            ow.println(f'| {cmd_grp_display} | {cmd_in_grp} | {cmd_argparser.description} | {cmd_usage} |')
            cmd_module_name = _cmd_register._cmd_grp_cmd_to_docstr[(cmd_grp, cmd_in_grp)]
            # '__' ->  r'\_\_': double underscores are empharsizing in Markdown
            # '\n\n' -> '<br/><br/>': replace empty lines with inline-HTML soft line breaks for Markdown paragraphs
            # '\n' -> '': Remove other line breaks
            cmd_module_docstr = sys.modules[cmd_module_name].__doc__
            if cmd_module_docstr is None:
                raise RuntimeError(f'Command group {cmd_grp} command {cmd_in_grp} does not have module docstring!')
            cmd_module_docstr = rst_lineblock_to_md_linebreak(cmd_module_docstr)
            cmd_module_docstr = cmd_module_docstr.\
                strip(). \
                replace('__', r'\_\_').\
                replace('\n\n', '<br/><br/>').\
                replace('\n', '')

            mod_nm_chunks = cmd_module_name.split(r'.')
            pkg = '.'.join(mod_nm_chunks[:-1])
            module = mod_nm_chunks[-1]
            cell_pkg = f'implementation</br>pkg **{pkg}**</br>module **{module}**'
            ow.println(f'|  | | {cell_pkg} | {cmd_module_docstr} |')


RST_TMPLT_PARENT_MOD = """{parent_mod_name}
{cmd_grp_mod_underline}
    
{parent_mod_docstr}
    
"""

RST_TMPLT_CMD_MOD = """{cmd_mod_name}
{cmd_mod_underline}

MixCli command and implementation: {cmd_desc}

..  automodule:: {cmd_mod_full_name}
    :members:

"""


# noinspection PyProtectedMember
def out_rst(ow: OutWriter):
    """
    Generate reStructureText format content

    :param ow:
    :return:
    """
    cmd_grp_displayed = set()
    for cmd_grp in sorted(_cmd_register._registered_grp):
        if cmd_grp in cmd_grp_skip:
            continue
        for cmd_grp_cmd_tuple, cmd_arg_parser in _cmd_register._cmd_grp_cmd_to_arg_parser.items():
            if cmd_grp_cmd_tuple[0] != cmd_grp:
                continue
            cmd = cmd_grp_cmd_tuple[1]
            tuple_cmd_grp_cmd = (cmd_grp, cmd)
            cmd_module_name = _cmd_register._cmd_grp_cmd_to_docstr[tuple_cmd_grp_cmd]
            if cmd_grp not in cmd_grp_displayed:
                cmd_grp_displayed.add(cmd_grp)
                parent_mod_name = '.'.join(cmd_module_name.split('.')[:-1])
                cmd_grp_underline = '=' * len(parent_mod_name)
                parent_mod_docstr = sys.modules[parent_mod_name].__doc__.strip()
                ow.println(RST_TMPLT_PARENT_MOD.format(parent_mod_name=parent_mod_name,
                                                       cmd_grp_mod_underline=cmd_grp_underline,
                                                       parent_mod_docstr=parent_mod_docstr))
            cmd_underline = '_' * len(cmd_module_name)
            cmd_desc = cmd_arg_parser.description
            ow.println(RST_TMPLT_CMD_MOD.format(cmd_mod_name=cmd_module_name,
                                                cmd_mod_underline=cmd_underline,
                                                cmd_mod_full_name=cmd_module_name,
                                                cmd_desc=cmd_desc))


OUTTYPE_MD = 'md'
OUTTYPE_RST = 'rst'
OUTTYPES = [OUTTYPE_RST, OUTTYPE_MD]


def get_argparser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument('-t', '--type', type=str, choices=OUTTYPES, default=OUTTYPE_MD,
                        help='Output format, either "md" for markdown or "rst" for (Sphinx) reStructureTxt')
    parser.add_argument('-o', '--out', type=str, metavar='OUTPUT_FILE',
                        help='Output file')
    return parser


def main():
    argparser = get_argparser()
    args = argparser.parse_args()
    with OutWriter.open(args.out) as fho:
        out_format = args.type
        if out_format == OUTTYPE_MD:
            out_md(fho)
        elif out_format == OUTTYPE_RST:
            out_rst(fho)
        else:
            raise RuntimeError(f'Unsupported output format: {args.type}')


if __name__ == '__main__':
    main()