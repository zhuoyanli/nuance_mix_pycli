from mixcli import MixCli
import sys


def main(*cmd_args):
    mixcli = MixCli.get_cli()
    args = mixcli.cmd_argparser.parse_args(args=list(cmd_args))
    mixcli.proc_cmd_args(argparser=mixcli.cmd_argparser, cmd_args=args)


if __package__ is not None:
    main(*sys.argv[1:])
