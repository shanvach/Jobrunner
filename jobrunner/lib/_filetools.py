# Standard libraries
import os
import shutil
import toml
import subprocess
from collections import OrderedDict

# local imports
from . import GetNodeList


def CreateSetupFile(main_dict):
    """
    Create a job.setup file using the list of
    job.setup scripts from main dictionary

    Arguments
    ---------
    main_dict : Dictionary containing details of the
                job configuration in directory tree
    """
    # open job.setup in write mode this
    # will replace existing job.setup
    # in the working directory
    with open(main_dict["job"]["workdir"] + os.sep + "job.setup", "w") as setupfile:

        # write the header for bash script
        setupfile.write("#!/bin/bash\n")
        
        # set -e to return when error is detected
        setupfile.write("set -e\n")

        # set environment variable for
        # working directory
        setupfile.write(f'\nJobWorkDir="{main_dict["job"]["workdir"]}"\n')

        # add commands from job.setup script
        # and place a command to chdir into
        # the node directory
        for nodefile in main_dict["job"]["setup"]:

            # get node directory from nodefile
            nodedir = os.path.dirname(nodefile)

            # chdir into node directory
            setupfile.write(f"\ncd {nodedir}\n")

            # add some spaces
            setupfile.write(f"\n")

            # open nodefile in read mode
            # and write lines to setup script
            with open(nodefile, "r") as entry:
                for line in entry:
                    setupfile.write(line)


def CreateInputFile(main_dict):
    """
    Create an input file for a given simulation
    recursively using job.input between basedir
    and workdir defined in main_dict

    main_dict : Dictionary containing details of the
                job configuration in directory tree
    """
    # check to see if input files are
    # defined in the main dictionary
    if main_dict["job"]["input"]:

        # define main dictionary
        jobtoml = {}

        # loop through the list of
        # source files from job.input
        for nodefile in main_dict["job"]["input"]:

            # Read toml configuration from the
            # nodefile and iterator over groups
            nodetoml = toml.load(nodefile)
            for group in nodetoml.keys():

                # update main dictionary with
                # information from nodetoml
                if group in jobtoml:
                    jobtoml[group].update(nodetoml[group])
                else:
                    jobtoml[group] = nodetoml[group]

        # start writing the job.input file
        with open(main_dict["job"]["workdir"] + os.sep + "job.input", "w") as inputfile:

            # Iterate over groups and start looping over
            # items and populate the main dictionary
            for group in jobtoml.keys():
                for variable, value in OrderedDict(
                    sorted(jobtoml[group].items())
                ).items():
                    if type(value) == str:
                        inputfile.write(f'{group}.{variable} = "{value}"\n')
                    else:
                        inputfile.write(f"{group}.{variable} = {value}\n")


def CreateTargetFile(main_dict):
    """
    Create a job.target for a given simulation
    using values from job.target in main_dict

    Arguments
    ---------
    main_dict : Dictionary containing details of the
                job configuration in directory tree
    """
    # set target file from job.target
    targetfile = main_dict["job"]["target"]

    # check if path to targetfile
    # exists and handle execptions
    if targetfile:
        if os.path.exists(targetfile):

            subprocess.run(
                f"rm -f job.target && ln -s {targetfile} job.target",
                shell=True,
                check=True,
            )

        else:

            # else raise exception
            raise ValueError(f"[jobrunner] {targetfile} not present in path")


def CreateSubmitFile(main_dict):
    """
    Create a job.submit file for using values
    from job.submit list define in main_dict

    Arguments
    ---------
    main_dict : Dictionary containing details of the
                job configuration in directory tree
    """
    # open job.submit in write mode
    # and start populating
    with open(main_dict["job"]["workdir"] + os.sep + "job.submit", "w") as submitfile:

        # write the header
        submitfile.write("#!/bin/bash\n")

        # set -e to return when error is detected
        #submitfile.write("set -e\n")

        # add commands from
        # schedular.options
        submitfile.write(f"\n")
        for entry in main_dict["schedular"]["options"]:
            submitfile.write(f"{entry}\n")

        # set environment variable
        # to working directory
        submitfile.write(f'\nJobWorkDir="{main_dict["job"]["workdir"]}"\n')

        # add commands from job.submit script
        # and chdir into node directory given by
        # the location of script
        for nodefile in main_dict["job"]["submit"]:

            # get node directory from nodefile
            nodedir = os.path.dirname(nodefile)

            # chdir into node directory
            submitfile.write(f"\ncd {nodedir}\n")

            # add some spaces
            submitfile.write(f"\n")

            # open nodefile in read mode
            # and start populating contents
            with open(nodefile, "r") as entry:

                # loop over lines in entry
                for line in entry:

                    # if job.input and job.target used
                    # in nodefile. Make sure they are
                    # defined in the directory tree
                    if (
                        "job.target" in line.split("#")[0]
                        and not main_dict["job"]["target"]
                    ):
                        raise ValueError(
                            f"[jobrunner]: job.target used in {nodefile} but not defined in Jobfile"
                        )

                    if (
                        "job.input" in line.split("#")[0]
                        and not main_dict["job"]["input"]
                    ):
                        raise ValueError(
                            f"[jobrunner]: job.input used in {nodefile} but not defined in Jobfile"
                        )

                    # write to submit file if checks passed
                    submitfile.write(line)


def RemoveNodeFiles(main_dict, nodedir):
    """
    Create an archive of artifacts
    along a directory node

    Arguments
    ---------
    main_dict : Dictionary containing details of the
                job configuration in directory node

    nodedir : path to node directory
    """
    # get a list of directories along the
    # node between basedir and workdir
    node_list = GetNodeList(main_dict["job"]["basedir"], main_dict["job"]["workdir"])

    # perform checks
    if nodedir not in node_list:
        raise ValueError(f"Node {nodedir} directory does not exists in tree")

    # chdir into node directory
    os.chdir(nodedir)

    # create an empty list
    # of file to be removed
    remove_list = []

    # get the list of
    # files in nodedir
    nodefile_list = [
        os.path.abspath(nodefile)
        for nodefile in next(os.walk("."), (None, None, []))[2]
    ]

    # create a reference file list
    # to test which nodefile should
    # be archived
    ref_list = main_dict["job"]["clean"] + [
        nodedir + os.sep + "job.input",
        nodedir + os.sep + "job.setup",
        nodedir + os.sep + "job.submit",
        nodedir + os.sep + "job.target",
        nodedir + os.sep + "job.output",
    ]

    # loop over list of files in nodedir
    # and append to archive_list if file
    # is present in job.archive
    for filename in nodefile_list:
        if filename in ref_list:
            remove_list.append(filename)

    if remove_list:

        # loop over archive_list
        # and archive contents
        for filename in remove_list:
            os.remove(filename)

    # return back to working directory
    os.chdir(main_dict["job"]["workdir"])
