# Make contributions to CR MixCli

## How MixCli git repo is organized

The repo is organized for Python source codes, Pytest tests, setuptools artifact builds, 
sphinx Python code documentation, and Markdown readme documentation.

* __src__: Python source codes
   
* __tests__: Pytest tests
   
* __releases__: Setuptools configuration and working directory for building Pip installation
artifacts like wheel files.

    * __requirements.txt__: Dependencies file for Pip installation so as to run MixCli Python codes
    ```shell
    pip install -r requirements.txt
    ```
    * __setup.py__: Setuptools configuration file.
    ```shell
    # To build wheel artifact for MixCli releases
    python setup.py bdist_wheel
    ```
    * Other dirs: Working and output dirs for setuptools. They are not maintained in VCS. Build results
    of *setup.py* shall be found in *dist* dir.


* __pydocs__: Sphinx configuration and working directory for Python code documentation.
    * __important__: Do **NOT** run **sphinx-quickstart** in this dir unless you are sure. Doing so will override all existing sphinx configs.
   
    * __make.bat/Makefile__: Makefile to run sphinx to build Python docs. These will only work when
    **sphinx** package has been installed in Python environment by Pip.
      
    ```shell
    # Make multi-page HTML 
    make html
    # Make single-page HTML
    make singlehtml
    # Make PDF
    make pdf
    ```
    
    * __source__: Sphinx setup data.
    
        * __index.rst__: Main sphinx content file. Edit this file to add content to Python docs.
        
        * __cmd.rst__: Python docs on MixCli Python codes. Do **NOT** edit this file as it is generated automatically.
    
        * Other dirs: Sphinx config files.
    
    * __build__: Working/output dir for sphinx. This dir. is ignored by VCS. Results of sphinx builds shall
    be found in this directory. For example *make singlehtml* will produce files in *build/singlehtml* dir. 

*  __readme__: Markdown readme files for various documentations like this file.


## How MixCli codes are organized

MixCli codes are essentially separated into two modules, __commad__ and __util__.

__command__ package is the overall package holding all the implementations of MixCli commands.
The command groups will be implemented as children packages of __mixcli.command__ and concrete
commands implemented as modules of those packages. For example, the __sys__ command group is implemented
as __mixcli.command.sys__ package and __version__ command in that group implemented as
__mixcli.command.sys.version__ module.

### mixcli.command package

### mixcli.util package

# Make changes to MixCli Python codes

Source codes of MixCli are maintained in **src** directory. Particulary implementation codes
of MixCli are in **mixcli/command** directory.

# Add new command group(s) and/or new command(s)

## How to add new command group

1. Add a new Json field key-value pair to Json varaible CMD_GROUP_CONFIG in 
mixcli.command.cmd_group_config.py. The key should be a str as name of the command group,
while value is a str of descriptive message about this command group.
2. Add a new package to mixcli.command as we would want to add modules that implement
concrete commands, which belong to this new group, in it. Check the packages in 
mixcli.command for other existing command groups as reference.

## How to add new command
1. First if it should go to a new command group, complete the previous operation
for adding new command groups.
2. Create a module in the right command group package. It is recommended to use
the name of new command as name of module.
3. You should at least create three functions there
   * a command registration function that declares the command group, command name,
command description, and default function to be called when that command is used.
     * The default function should be one taking a positional argument, being a MixCli 
      instance, and rest as keyword arguments.
     * This command registration function should have the register_cmd decorator
      from mixcli.utils.command module, which takes four arguments: name of command
      group, name of command, description of command, and the function object of default
      function
     * The command registration function should receive an ArgumentParser instance as
      argument; Use that ArgumentParser instance to add argument configs for the command.
     * No need to return any values
   * a default processing function when this command is actually used
   * a separated function that actually implement the actions for the command. You are
   recommended to implement that in a separate function in that, by doing so, the functional
   actions can be re-used by other classes/functions. Check mixcli.command.project.reset 
   to see how mixcli.command.project.get is being re-used.
4. Edit **mixcli.command.cmd_config.py**
   1. Make imports of implementing modules from the command group packages
      1. It is recommended to use aliases for the import modules to avoid some possible name crashing
   2. Edit **CMD_CONFIG** Json variable
      2. If the key for command group is already there, just add the imported module to the existing
     set aside of other command modules
      3. If there is no key for the command group, add the key, a str of command group name, and the
     value should be a set '{}' with the imported modules in it.

# Update main README file

Please update the README.md in top level

# Update other README files in Markdown

Please update the files in **readme** directory.

# Update Python code documentations

Please update **index.rst** and/or **conf.py** in **pydocs/source** directory.

# Update Pytest tests

Please update files in **tests/mixcli** directory.