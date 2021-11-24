Nuance Central Research MixPy Cli for Mix APIs
======================

## Quick link: Download latest build of Central Research MixPy, Python client for Mix 3 APIs

[Latest build artifact](https://git.labs.nuance.com/nlp-research/core-tech-tools/-/jobs/artifacts/master/download?job=build_mixcli_wheel)

The build artifact being downloaded, which is a ZIP archive will contain two elements:

- A Python wheel file that could be installed by pip via the command: pip install [--force-reinstall] <path\_to\_wheel\_file>
    - Attention: If you have already installed released wheel file(s) of CR MixCli, you MUST add the '--force-reinstall' switch so that pip will 'override' previously installed data
- A ZIP archive containing the Python source codes of CR MixCli as 'portable' release. Users could simply 
    - expand the Python codes to a directory and run command 'python -m mixcli' to use CR MixCli
    - expand the content to their working source directory so as to use MixCli in Python codes.


## How to get working CR MixPy instance

### Get on-GRID Python environment ready for use

The python virtual-env is available at `/gpfs/lm/data/scratch/crnlu_cron/pyenv/3.8.7-mixcli/`, where all the dependencies
and CR MixPy build had been installed.

**VERY IMPORTANT**: This pre-installed Python virtual-env is created with a Python binary that has been built on the
latest NRG5-UNN OS, which is CentOS 7. However, GRID user nodes a.k.a. UNV+ still run with the old CentOS 6.9. As a
result, this Python virtual-env would **NOT RUN** if user logins are on UNV+, even if the programs are found from
GRID paths. That being said, users must log in one of the UNNs in order to use this pre-installed Python virtual env.

The easiest way to use is activate the pre-installed Python venv, then use 'mixcli' program available in `$PATH`. 

*   Use in activated Python virtual env
    ```shell
    source /gpfs/lm/data/scratch/crnlu_cron/pyenv/3.8.7-mixcli/bin/activate
    # now the program 'mixcli' is available in $PATH
    mixcli <mixcli_command> ...
    # or run the module
    python3 -m mixcli <mixcli_command> ...
    ```

*  Or use the Python interpreter from the virtual env
    ```shell
    /gpfs/lm/data/scratch/crnlu_cron/pyenv/3.8.7-mixcli/bin/python3 -m mixcli <mixcli_command> ...
    ```

### Build CR MixCli from source

1. Checkout the CR MixCli git repo: `git@git.labs.nuance.com:nlp-research/core-tech-tools.git`
   
2. MixCli is located in **mix-cli** directory.
   
3. Install the dependencies for CR MixCli with pip, and the requirements.txt file from git repo

```shell
python3 -m pip install -r releases/requirements.txt
```

4. Build CR MixCli

```shell
cd releases
python3 setup.py bdist_wheel 
```

5. The built wheel file will be found at the path `releases/dist/mixcli-<version>-py3-none-any.whl`

6. Install teh wheel file with pip

```bash
# if this is the first time installing MixCli wheel file
python3 -m pip install dist/mixcli-<version>-py3-none-any.whl

# if MixCli wheel file has already been installed and we want to update
python3 -m pip install -U --force-reinstall dist/mixcli-<version>-py3-none-any.whl
```

## How to use CR MixCli

### As command line CLI program

1. Run with Python interpreter

Here we take the assumption that the pre-installed GRID Python venv has been activated or MixCli package has been
installed for the Python env being used.

```shell
python3 -m mixcli <cmd_group> <cmd> args ...
```

2. If you are in the on-GRID shared virtual-env, there is a wrapper command *mixcli* available in $PATH.

```shell
mixcli <cmd_group> <cmd> args ...
```

### As Python module

Coders would need to 

1.  Import MixCli class from *mixcli* package
    
2.  Perform authorization either with default configuration files lookup or explicit reference

```python
# import MixCli class
from mixcli import MixCli
# create the instance
mix_cli = MixCli.get_cli()
# perform Mix authorization by performing look-up of credential config files in default location.
mix_cli.do_mixauth()
# Or with external files as in command line
# mix_cli.do_mixauth(client_cred=client_cred_cfg_json)
# Or directly with client credentials
# mix_cli.do_mixauth(client_id=CLIENT_ID, service_secret=SRVC_SECRET)
# confirm we do get the auth token
print(mix_cli.auth_handler.token)
```

Then coders can choose to mimic command line actions:

```python
# Run the sys version command
# The following line is to suppress warning in PyCharm markdown editor
# noinspection PyUnresolvedReferences 
mix_cli.run_cmd('sys', 'version')
```

Or call the implementation Python functions

```python
from typing import Dict, Optional
from mixcli.command.project.get import get_project_meta
...
# noinspection PyUnresolvedReferences
proj_meta: Optional[Dict] = get_project_meta(mixcli=mix_cli, project_id=12345)
if proj_meta:
    ...
```

## Prepare Mix Client Credentials for Authorization process

CR MixCli includes support for the latest Mix Oauth client credentials authorization workflow, and we expect Nuance 
internal users to run CR MixCli by performing such authorization workflow.

What MixCli users need to do is prepare a file named (exactly) as **mix-client-credentials.json**. 
This **mix-client-credentials.json** file should look like the following

```json
{
  "client-id": "mix-api-client:...",
  "service-secret": "..."
}
```

### Locations of mix-client-credentials.json file

There are two options to place this **mix-client-credentials.json** file

* In the working directory where MixCli is run, or
* In a directory which is referenced by environment variable **MIXCLI_USERHOME**

For more information on Mix (API) authorization and/or client credentials, please consult 
[confluence page](https://confluence.labs.nuance.com/display/NLPRES/Mix+authorization) or 
[Mix doc](https://docs.mix.nuance.com/images/mix-api/common/generate_client_secret_service-bb89953d.png)

### Specify client credentials for MixCli Python binding

```python
from mixcli import MixCli
from mixcli.util.auth import MixApiAuthFailureError
mixcli = MixCli.get_cli()
my_client_id: str = ...
my_service_sec: str = ...
try:
    mixcli.client_cred_auth(client_id=my_client_id, service_secret=my_service_sec)
except MixApiAuthFailureError as auth_exc:
    ...
```

## Readme on MixCli commands
Please consult the **command_readme.md** file in the **readme** directory.

## Relay meta-info between MixCli commands along Shell scripts
One major and common concern for Mix API users when writing their automation shell scripts is pass important meta-info
between different usages of Mix API operations, where those meta-info are present as part of Mix API response
payloads and can NOT be preset in scripts. For example, users use **mixcli project create** command to create a new
Mix project, and later on need the ID of new project to run **mixcli nlu import** command. The ID of new project would
only be found from result of **project create** command.

To account for this, **MixCli** has provided two features to make passing meta-info between command invocations easier.

### "--out-file" argument to serialized MixCli command results
Most MixCli commands offer an argument named "out-file", which would send MixCli command results, mostly response
payloads from Mix API endpoints, to specified offline files. Usually those response payloads are JSON objects whic are
always compliant with particular schemas. That being said, users can expect to always find JSON values with 
preset JSON keys on same MixCli commands.

### "util jsonpath" command to process JSON files and extract values
It is users' choices to pick the tools for processing JSON files, such as 'jq' program. MixCli has always provided
a utility command **util jsonpath** to help. This command would run specified JsonPath query, much like jQuery, on 
JSON files and return query results. 

There are several important notes to read before using this command

* The JsonPath queries in MixCli are handled by jsonpath-ng Python project, whose official project page
could be found at &nbsp;[https://github.com/h2non/jsonpath-ng](https://github.com/h2non/jsonpath-ng). JsonPath is a 
  general proposal and specific implementations could have different detailed specificiation and limitations. Please do
  consult the project page if you plan on using complicated JsonPath expressions/queries.
  
* This Jsonpath-ng implementation **always** return a list as container of query results, even empty list for no match. 
  That being said, even query from user is supposed to match one single Json value, it would still result in a list. 
  MixCli provides two options to furture extract elements from those lists:
  * If query result lists are empty, none of the following post-processing purpose arguments/switches would be applied. 
  * Users could either use '--always-first'   switch to specify that, if result list is not empty, the first element 
     of list should be returned as end result.
  * Users could use --postproc-pyexpr argument to specify Python expressions. Those expressions will be evaluated on 
    result lists and evaluation results will be returned as command's end results.
    * Users should use **r** as reference of result lists. For example, expression **r[0]** gets the first element of 
      result list.
    * Users should note the different between **expressions** and **statements**. For example, **a = r[0]** is 
      **statement** and will yield no results for output upon evaluation.
    * Obviously `--postproc-pyexpr "r[0]"` will achieve the same end result as `-always-first`
  * `--always-first` switch and `--postproc-pyexpr EXPR` are mutually excluding arguments, only one of either could 
    be specified.
  * All end results, with or without post-processing, will be output as literal strings. That being said, Python 
    variables and objects will be **printed** as if running Python code `print(str(repr(var)))`
    
With the two aforementioned features from MixCli, the following usages in shell scripts would be possible

```shell
mixcli project create --name 'MyTempMixPrj' --out-file proj_create_out.json
PROJ_ID=$(mixcli util jsonpath --infile proj_create_out.json --jsonpath '$.id' --always-first)
mixcli project get --project-id ${PROJ_ID} --out-file proj_get_meta.json
...
```

## Special notes on Mix app config deployment with "config create" command
This MixCli program provides an important feature to **create** new Mix application configurations (for deployment)
and to **deploy** those recently created configurations, however there are certain limitations on that feature;
please read the following notes carefully. (also available from command epilogue)

1. The **config create** command expects users to specify a namespace, a Mix app config group, and (app) context tag to 
    identify a Mix application. The app config groups created for regular Mix users by default would be of name
    'Mix Sample App'. Please note it is case-sensitive and comes with space. That is already set as default value for the
    "--cfg-group" argument of the command. So users could just skip the argument to avoid typing the complete quoted 
    string in commands.
   
2. The **context tag** used in the command must be an already existing tag in Mix platform. That being said, if users 
    want to use some totally new context tags, they must first manually create those tags in Mix MANAGE UI. This limitation 
    should not be a big issue for using the command, given that a context tag can take arbitrary projects and model builds. 
    So users could create some placeholder context tags ahead of time and use those tags in command.
   
3. The **deploy** action covered in the command refers to actually **deploy** a new build configs, and the associated models to target servers; this is
    typically achieved in Mix UI by checking check-boxes for target servers and then clicking **Deploy** buttons. Expected
    Mix models would only be available over gRPC SaaS after such deployment actions are done. 


## Highlights of MixCli use cases

Note: We use **mixcli** as short for command **python -m mixcli**, 
and we assume the client credential config file has been prepared in the working directory.

### Generate Mix API authorization tokens

Please note that, if client ID and service credential are available, MixCli itself does **NOT** require specified
Mix auth tokens: It would manage generation process as needed. This use case is for people who need explicit Mix
auth tokens in other usages.

```shell
# the following commands assume that client credential file is available through MIXCLI_USERHOME environment var
# generate token as literal string to STDOUT
mixcli auth client
# generate token to a specific file
mixcli auth client --out-file <token_in_txt>
# generate token as JSON that contains meta-info such as token (approximate) token expiration time
mixcli auth client --out-type json [--out-file <token_in_json]

# users could alternatively specify the file through cmd line argument
mixcli --client-cred <path_to_client_cred_json> auth client
mixcli --client-cred <path_to_client_cred_json> auth client --out-file <token_in_txt>
mixcli --client-cred <path_to_client_cred_json> auth client --out-type json [--out-file <token_in_json]
```

### Import/export NLU/Dialog models from Mix project ID 12345

```shell
mixcli nlu export --project-id 12345 --locale en_US --out-file 12345_nlu_export.trsx
mixcli dlg export --project-id 12345 --out-json 12345_dialog_export.json
mixcli nlu import --project-id 12345 --src 12345_nlu.trsx --wait
mixcli dlg import --project-id 12345 --src 12345_dialog.json
# or export to directory with file names in preset patterns
mixcli nlu export --project-id 12345 --locale en_US --out-file export_dir
# export file will be  export_dir/12345**<prj_name>**NLU**<timestamp>.trsx
mixcli dlg export --project-id 12345 --out-json export_dir
# export file will be  export_dir/12345**<prj_name>**DIALOG**<timestamp>.json
# or one-stop command model-export
mixcli project model-export --project-id 12345 --locale en_US --model nlu dialog --out-dir export_dir 
```
### Launch model builds and deploy them
In this example, we will 
1. Launch ASR/NLU (en-US)/Dialog model builds for Mix project ID 12345

   1.1. Use build note "This is a MixCli build"     
   
2.  Wait till builds are completed

3.  Create a new deployment config in **namespace** `nobody@nuance.com`, **deployment group** MySampleApp, **tag**
Prj12345, with the latest build verion of NLU models

    *   Use version number **0** to refer to **latest** build version
    
    *   If users want to deploy the NLU/ASR/Dialog models, they **MUST** specify the **--{nlu/asr/dlg}-version**
        argument(s). Skipping the corresponding arguments means models would **NOT** be used in deployment.
        
    *   The **tag**, e.g. Prj12345, must be an existing tag in the config group, e.g. MySampleApp. For the moment the
        command **CAN NOT** create a new deployment tag from scratch.

4.  In the end we **promote** the new config

**IMPORTANT NOTE**: The **promote** feature currently would only work with users on
NA/Canada production server.

```shell
mixcli project build --project-id 12345 --locale en-US --note 'This is a MixCli build'
mixcli app new-deploy --namespace nobody@nuance.com --cfg-group MySampleApp --cfg-tag Prj12345 \
    --project-id 12345 --locale en-US --nlu-version 0 --promote \  

# if we want to take snapshots of model source for the build and save them in directory build_model_src
mixcli project build --project-id 12345 --locale en-US --note 'This is a MixCli build' --export build_model_src
```

### Create a new project, import TRSX NLU model, build and deploy models

1. Create a new Mix project with 
   *  **name** TmpProject
   *  **ASR datapack topic** 'gen'
   *  **locales** en-US, en-GB
2. Import NLU model in TRSX proj_nlu_backup.trsx to the new project
3. Build the NLU model of new project and deploy it

```shell
# Create the project with project create command, send command result to prj_create_result.json
mixcli project create --name 'TmpProject' --dp-topic 'gen' --locales en-US en-GB --namespace nobody@nuance.com --out-file prj_create_result.json
# process the JSON file which is the project creation result payload and extract ID of the new project
NEW_PROJ_ID=$(mixcli util jsonpath --infile prj_create_result.json --jsonpath "$.id" --always-first)
mixcli nlu import --project-id $NEW_PROJ_ID --src proj_nlu_backup.trsx --wait
mixcli project build --project-id $NEW_PROJ_ID --model nlu --locale en-US --note 'NLU build by MixCli'
# use version number 0 to refer to latest build version
mixcli app new-deploy --namespace nobody@nuance.com --cfg-group MySampleApp --cfg-tag TmpProj --project-id $NEW_PROJ_ID --locale en-US --nlu-version 0 --promote 
```

## Make contribution to MixCli

Please consult **contrib.md** in the **readme** directory
