from setuptools import setup

setup(
    name='mixpy',
    version='1.0.1',
    packages=['mixcli', 'mixcli.util', 'mixcli.util.auth', 'mixcli.command', 'mixcli.command.ns',
              'mixcli.command.config', 'mixcli.command.asr', 'mixcli.command.dlg', 'mixcli.command.grpc',
              'mixcli.command.job', 'mixcli.command.nlu', 'mixcli.command.intent',
              'mixcli.command.run', 'mixcli.command.sys', 'mixcli.command.auth',
              'mixcli.command.channel', 'mixcli.command.concept', 'mixcli.command.util',
              'mixcli.command.project', 'mixcli.command.sample'],
    package_dir={
        'mixcli': '../src/mixcli'
    },
    url='',
    license='MIT',
    author='Zhuoyan Li',
    author_email='zhuoyan.li@nuance.com',
    description='Nuance Central Research MixPy Mix Python Cli'
)
