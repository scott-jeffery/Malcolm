#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Battelle Energy Alliance, LLC.  All rights reserved.

import sys

sys.dont_write_bytecode = True

import argparse
import datetime
import errno
import fileinput
import getpass
import glob
import gzip
import json
import os
import platform
import re
import secrets
import shutil
import signal
import stat
import string
import tarfile
import tempfile
import time

from malcolm_common import (
    AskForPassword,
    AskForString,
    BoundPath,
    ChooseOne,
    ClearScreen,
    CONTAINER_RUNTIME_KEY,
    DetermineYamlFileFormat,
    DisplayMessage,
    DisplayProgramBox,
    DotEnvDynamic,
    GetUidGidFromEnv,
    KubernetesDynamic,
    LocalPathForContainerBindMount,
    MainDialog,
    MalcolmAuthFilesExist,
    MalcolmPath,
    MalcolmTmpPath,
    OrchestrationFramework,
    OrchestrationFrameworksSupported,
    PLATFORM_WINDOWS,
    posInt,
    ProcessLogLine,
    PROFILE_HEDGEHOG,
    PROFILE_KEY,
    PROFILE_MALCOLM,
    ScriptPath,
    UserInputDefaultsBehavior,
    YAMLDynamic,
    YesOrNo,
)

from malcolm_utils import (
    CountUntilException,
    deep_get,
    dictsearch,
    eprint,
    flatten,
    EscapeAnsi,
    EscapeForCurl,
    get_iterable,
    get_primary_ip,
    LoadStrIfJson,
    ParseCurlFile,
    pushd,
    RemoveEmptyFolders,
    run_process,
    same_file_or_dir,
    str2bool,
    which,
)

from malcolm_kubernetes import (
    CheckPersistentStorageDefs,
    DeleteNamespace,
    get_node_hostnames_and_ips,
    GetPodNamesForService,
    PodExec,
    PrintNodeStatus,
    PrintPodStatus,
    REQUIRED_VOLUME_OBJECTS,
    StartMalcolm,
)

from base64 import b64encode
from collections import defaultdict, namedtuple
from subprocess import PIPE, STDOUT, DEVNULL, Popen, TimeoutExpired
from urllib.parse import urlparse
from itertools import chain, groupby

try:
    from contextlib import nullcontext
except ImportError:

    class nullcontext(object):
        def __init__(self, enter_result=None):
            self.enter_result = enter_result

        def __enter__(self):
            return self.enter_result

        def __exit__(self, *args):
            pass


###################################################################################################
ScriptName = os.path.basename(__file__)

pyPlatform = platform.system()

args = None
dockerBin = None
# dockerComposeBin might be e.g., ('docker', 'compose'), ('podman', 'compose'), or 'docker-compose', etc.
#   it will be flattened in run_process
dockerComposeBin = None
dockerComposeYaml = None
kubeImported = None
opensslBin = None
orchMode = None
shuttingDown = [False]
yamlImported = None
dotenvImported = None
MaxAskForValueCount = 100
UsernameRegex = re.compile(r'^[a-zA-Z][a-zA-Z0-9_\-.]+$')
UsernameMinLen = 4
UsernameMaxLen = 32
PasswordMinLen = 8
PasswordMaxLen = 128

###################################################################################################
try:
    from colorama import init as ColoramaInit, Fore, Back, Style

    ColoramaInit()
    coloramaImported = True
except Exception:
    coloramaImported = False


###################################################################################################
# handle sigint/sigterm and set a global shutdown variable
def shutdown_handler(signum, frame):
    global shuttingDown
    shuttingDown[0] = True


###################################################################################################
def checkEnvFilesAndValues():
    global args
    global dotenvImported

    # if a specific config/*.env file doesn't exist, use the *.example.env files as defaults
    if os.path.isdir(examplesConfigDir := os.path.join(MalcolmPath, 'config')):
        for envExampleFile in glob.glob(os.path.join(examplesConfigDir, '*.env.example')):
            envFile = os.path.join(args.configDir, os.path.basename(envExampleFile[: -len('.example')]))
            if not os.path.isfile(envFile):
                if args.debug:
                    eprint(f"Creating {envFile} from {os.path.basename(envExampleFile)}")
                shutil.copyfile(envExampleFile, envFile)

        # now, example the .env and .env.example file for individual values, and create any that are
        # in the .example file but missing in the .env file
        for envFile in glob.glob(os.path.join(args.configDir, '*.env')):
            envExampleFile = os.path.join(examplesConfigDir, os.path.basename(envFile) + '.example')
            if os.path.isfile(envExampleFile):
                envValues = dotenvImported.dotenv_values(envFile)
                exampleValues = dotenvImported.dotenv_values(envExampleFile)
                missingVars = list(set(exampleValues.keys()).difference(set(envValues.keys())))
                if missingVars:
                    if args.debug:
                        eprint(f"Missing {missingVars} in {envFile} from {os.path.basename(envExampleFile)}")
                    with open(envFile, "a") as envFileHandle:
                        print('', file=envFileHandle)
                        print('', file=envFileHandle)
                        print(
                            f'# missing variables created from {os.path.basename(envExampleFile)} at {str(datetime.datetime.now())}',
                            file=envFileHandle,
                        )
                        for missingVar in missingVars:
                            print(f"{missingVar}={exampleValues[missingVar]}", file=envFileHandle)


###################################################################################################
# perform a service-keystore operation in a container
#
# service - the service in the docker-compose YML file
# keystore_args - arguments to pass to the service-keystore binary in the container
# run_process_kwargs - keyword arguments to pass to run_process
#
# returns True (success) or False (failure)
#
def keystore_op(service, dropPriv=False, *keystore_args, **run_process_kwargs):
    global args
    global dockerBin
    global dockerComposeBin
    global orchMode

    err = -1
    results = []

    # the opensearch containers all follow the same naming pattern for these executables
    keystoreBinProc = f"/usr/share/{service}/bin/{service}-keystore"
    uidGidDict = GetUidGidFromEnv(args.configDir)

    if orchMode is OrchestrationFramework.DOCKER_COMPOSE:
        # if we're using docker-uid-gid-setup.sh to drop privileges as we spin up a container
        dockerUidGuidSetup = "/usr/local/bin/docker-uid-gid-setup.sh"

        # compose use local temporary path
        osEnv = os.environ.copy()
        if not args.noTmpDirOverride:
            osEnv['TMPDIR'] = MalcolmTmpPath

        # open up the docker-compose file and "grep" for the line where the keystore file
        # is bind-mounted into the service container (once and only once). the bind
        # mount needs to exist in the YML file and the local directory containing the
        # keystore file needs to exist (although the file itself might not yet).
        # also get PUID and PGID variables from the docker-compose file.
        localKeystore = None
        localKeystoreDir = None
        localKeystorePreExists = False
        composeFileKeystore = f"/usr/share/{service}/config/persist/{service}.keystore"
        volumeKeystore = f"/usr/share/{service}/config/{service}.keystore"
        volumeKeystoreDir = os.path.dirname(volumeKeystore)

        try:
            localKeystore = LocalPathForContainerBindMount(
                service,
                dockerComposeYaml,
                composeFileKeystore,
                MalcolmPath,
            )
            if localKeystore:
                localKeystore = os.path.realpath(localKeystore)
                localKeystoreDir = os.path.dirname(localKeystore)

            if (localKeystore is not None) and os.path.isdir(localKeystoreDir):
                localKeystorePreExists = os.path.isfile(localKeystore)

                dockerCmd = None

                # determine if Malcolm is running; if so, we'll use docker-compose exec, other wise we'll use docker run
                err, out = run_process(
                    [dockerComposeBin, '--profile', args.composeProfile, '-f', args.composeFile, 'ps', '-q', service],
                    env=osEnv,
                    stderr=False,
                    debug=args.debug,
                )
                out[:] = [x for x in out if x]
                if (err == 0) and (len(out) > 0):
                    # Malcolm is running, we can use an existing container

                    # assemble the service-keystore command
                    dockerCmd = [
                        dockerComposeBin,
                        '--profile',
                        args.composeProfile,
                        '-f',
                        args.composeFile,
                        'exec',
                        # if using stdin, indicate the container is "interactive", else noop (duplicate --rm)
                        '-T' if ('stdin' in run_process_kwargs and run_process_kwargs['stdin']) else '',
                        # execute as UID:GID in docker-compose.yml file
                        '-u',
                        f'{uidGidDict["PUID"]}:{uidGidDict["PGID"]}',
                        # the work directory in the container is the directory to contain the keystore file
                        '-w',
                        volumeKeystoreDir,
                        # the service name
                        service,
                        # the executable filespec
                        keystoreBinProc,
                    ]

                else:
                    # Malcolm isn't running, do 'docker run' to spin up a temporary container to run the ocmmand

                    # "grep" the docker image out of the service's image: value from the docker-compose YML file
                    serviceImage = None
                    composeFileLines = list()
                    with open(args.composeFile, 'r') as f:
                        composeFileLines = [
                            x for x in f.readlines() if f'image: ghcr.io/idaholab/malcolm/{service}' in x
                        ]
                    if (len(composeFileLines) > 0) and (len(composeFileLines[0]) > 0):
                        imageLineValues = composeFileLines[0].split()
                        if len(imageLineValues) > 1:
                            serviceImage = imageLineValues[1]

                    if serviceImage is not None:
                        # assemble the service-keystore command
                        dockerCmd = [
                            dockerBin,
                            'run',
                            # remove the container when complete
                            '--rm',
                            # if using podman, use --userns keep-id
                            ['--userns', 'keep-id'] if dockerBin.startswith('podman') else '',
                            # if using stdin, indicate the container is "interactive", else noop
                            '-i' if ('stdin' in run_process_kwargs and run_process_kwargs['stdin']) else '',
                            # if     dropPriv, dockerUidGuidSetup will take care of dropping privileges for the correct UID/GID
                            # if NOT dropPriv, enter with the keystore executable directly
                            '--entrypoint',
                            dockerUidGuidSetup if dropPriv else keystoreBinProc,
                            '--env',
                            f'PUID={uidGidDict["PUID"]}',
                            '--env',
                            f'DEFAULT_UID={uidGidDict["PUID"]}',
                            '--env',
                            f'PGID={uidGidDict["PGID"]}',
                            '--env',
                            f'DEFAULT_GID={uidGidDict["PGID"]}',
                            '--env',
                            f'PUSER_CHOWN={volumeKeystoreDir}',
                            # rw bind mount the local directory to contain the keystore file to the container directory
                            '-v',
                            f'{localKeystoreDir}:{volumeKeystoreDir}:rw',
                            # the work directory in the container is the directory to contain the keystore file
                            '-w',
                            volumeKeystoreDir,
                            # if     dropPriv, execute as root, as docker-uid-gid-setup.sh will drop privileges for us
                            # if NOT dropPriv, execute as UID:GID in docker-compose.yml file
                            '-u',
                            'root' if dropPriv else f'{uidGidDict["PUID"]}:{uidGidDict["PGID"]}',
                            # the service image name grepped from the YML file
                            serviceImage,
                        ]

                        if dropPriv:
                            # the keystore executable filespec (as we used dockerUidGuidSetup as the entrypoint)
                            dockerCmd.append(keystoreBinProc)

                    else:
                        raise Exception(f'Unable to identify docker image for {service} in {args.composeFile}')

                if dockerCmd is not None:
                    # append whatever other arguments to pass to the executable filespec
                    if keystore_args:
                        dockerCmd.extend(list(keystore_args))

                    dockerCmd[:] = [x for x in dockerCmd if x]

                    # execute the command, passing through run_process_kwargs to run_process as expanded keyword arguments
                    err, results = run_process(dockerCmd, env=osEnv, debug=args.debug, **run_process_kwargs)
                    if (err != 0) or (not os.path.isfile(localKeystore)):
                        raise Exception(f'Error processing command {service} keystore: {results}')

                else:
                    raise Exception(f'Unable formulate keystore command for {service} in {args.composeFile}')

            else:
                raise Exception(
                    f'Unable to identify a unique keystore file bind mount for {service} in {args.composeFile}'
                )

        except Exception as e:
            if err == 0:
                err = -1

            # don't be so whiny if the "create" failed just because it already existed or a 'remove' failed on a nonexistant item
            if (
                (not args.debug)
                and list(keystore_args)
                and (len(list(keystore_args)) > 0)
                and (list(keystore_args)[0].lower() in ('create', 'remove'))
                and localKeystorePreExists
            ):
                pass
            else:
                eprint(e)

    elif orchMode is OrchestrationFramework.KUBERNETES:
        cmd = [keystoreBinProc]
        if keystore_args:
            cmd.extend(list(keystore_args))
        cmd = [x for x in cmd if x]

        podsResults = PodExec(
            service,
            args.namespace,
            [x for x in cmd if x],
            stdin=(
                run_process_kwargs['stdin'] if ('stdin' in run_process_kwargs and run_process_kwargs['stdin']) else None
            ),
        )

        err = 0 if all([deep_get(v, ['err'], 1) == 0 for k, v in podsResults.items()]) else 1
        results = list(chain(*[deep_get(v, ['output'], '') for k, v in podsResults.items()]))

        if args.debug:
            dbgStr = f"{len(podsResults)} pods: {cmd}({run_process_kwargs['stdin'][:80] + bool(run_process_kwargs['stdin'][80:]) * '...' if 'stdin' in run_process_kwargs and run_process_kwargs['stdin'] else ''}) returned {err}: {results}"
            eprint(dbgStr)
            for podname, podResults in podsResults.items():
                dbgStr = f"{podname}: {cmd}({run_process_kwargs['stdin'][:80] + bool(run_process_kwargs['stdin'][80:]) * '...' if 'stdin' in run_process_kwargs and run_process_kwargs['stdin'] else ''}) returned {deep_get(podResults, ['err'], 1)}: {deep_get(podResults, ['output'], 'unknown')}"
                eprint(dbgStr)

    else:
        raise Exception(
            f'{sys._getframe().f_code.co_name} does not yet support {orchMode} with profile {args.composeProfile}'
        )

    return (err == 0), results


###################################################################################################
def status():
    global args
    global dockerComposeBin
    global orchMode

    if orchMode is OrchestrationFramework.DOCKER_COMPOSE:
        # docker-compose use local temporary path
        osEnv = os.environ.copy()
        if not args.noTmpDirOverride:
            osEnv['TMPDIR'] = MalcolmTmpPath

        cmd = [dockerComposeBin, '--profile', args.composeProfile, '-f', args.composeFile, 'ps']
        if args.service is not None:
            cmd.append(args.service)

        err, out = run_process(
            cmd,
            env=osEnv,
            debug=args.debug,
        )
        if err == 0:
            print("\n".join(out))
        else:
            eprint("Failed to display Malcolm status\n")
            eprint("\n".join(out))

    elif orchMode is OrchestrationFramework.KUBERNETES:
        try:
            PrintNodeStatus()
            print()
        except Exception as e:
            if args.debug:
                eprint(f'Error getting node status: {e}')
        try:
            PrintPodStatus(namespace=args.namespace)
            print()
        except Exception as e:
            eprint(f'Error getting {args.namespace} status: {e}')

    else:
        raise Exception(f'{sys._getframe().f_code.co_name} does not yet support {orchMode}')


###################################################################################################
def printURLs():
    global orchMode

    if orchMode is OrchestrationFramework.KUBERNETES:
        addrs = get_node_hostnames_and_ips(mastersOnly=True)
        if not any((addrs['external'], addrs['hostname'])):
            addrs = get_node_hostnames_and_ips(mastersOnly=False)
        if addrs['external']:
            myIp = addrs['external'][0]
        elif addrs['hostname']:
            myIp = addrs['hostname'][0]
        elif addrs['internal']:
            myIp = addrs['internal'][0]
        else:
            myIp = '<cluster IP>'
    else:
        myIp = get_primary_ip()

    print(f"\nMalcolm services can be accessed at https://{myIp}/")
    print("------------------------------------------------------------------------------")


###################################################################################################
def netboxBackup(backupFileName=None):
    global args
    global dockerComposeBin
    global orchMode

    backupFileName, backupMediaFileName = None, None

    uidGidDict = GetUidGidFromEnv(args.configDir)

    if (orchMode is OrchestrationFramework.DOCKER_COMPOSE) and (args.composeProfile == PROFILE_MALCOLM):
        # docker-compose use local temporary path
        osEnv = os.environ.copy()
        if not args.noTmpDirOverride:
            osEnv['TMPDIR'] = MalcolmTmpPath

        dockerCmd = [
            dockerComposeBin,
            '--profile',
            args.composeProfile,
            '-f',
            args.composeFile,
            'exec',
            # disable pseudo-TTY allocation
            '-T',
            # execute as UID:GID in docker-compose.yml file
            '-u',
            f'{uidGidDict["PUID"]}:{uidGidDict["PGID"]}',
            'netbox-postgres',
            'pg_dump',
            '-U',
            'netbox',
            '-d',
            'netbox',
        ]

        err, results = run_process(dockerCmd, env=osEnv, debug=args.debug, stdout=True, stderr=False)
        if (err != 0) or (len(results) == 0):
            raise Exception('Error creating NetBox configuration database backup')

        if (backupFileName is None) or (len(backupFileName) == 0):
            backupFileName = f"malcolm_netbox_backup_{time.strftime('%Y%m%d-%H%M%S')}.gz"

        with gzip.GzipFile(backupFileName, "wb") as f:
            f.write(bytes('\n'.join(results), 'utf-8'))

        backupFileParts = os.path.splitext(backupFileName)
        backupMediaFileName = backupFileParts[0] + ".media.tar.gz"
        with tarfile.open(backupMediaFileName, 'w:gz') as t:
            t.add(os.path.join(os.path.join(MalcolmPath, 'netbox'), 'media'), arcname='.')

    elif orchMode is OrchestrationFramework.KUBERNETES:
        if podsResults := PodExec(
            service='netbox-postgres',
            container='netbox-postgres-container',
            namespace=args.namespace,
            command=[
                'pg_dump',
                '-U',
                'netbox',
                '-d',
                'netbox',
            ],
            maxPodsToExec=1,
        ):
            podName = next(iter(podsResults))
            err = podsResults[podName]['err']
            results = podsResults[podName]['output']
        else:
            err = 1
            results = []

        if (err != 0) or (len(results) == 0):
            raise Exception('Error creating NetBox configuration database backup')

        if (backupFileName is None) or (len(backupFileName) == 0):
            backupFileName = f"malcolm_netbox_backup_{time.strftime('%Y%m%d-%H%M%S')}.gz"

        with gzip.GzipFile(backupFileName, "wb") as f:
            f.write(bytes('\n'.join(results), 'utf-8'))

        # TODO: can't backup netbox/media directory via kubernetes at the moment
        backupMediaFileName = None

    else:
        raise Exception(
            f'{sys._getframe().f_code.co_name} does not yet support {orchMode} with profile {args.composeProfile}'
        )

    return backupFileName, backupMediaFileName


###################################################################################################
def netboxRestore(backupFileName=None):
    global args
    global dockerComposeBin
    global orchMode

    if backupFileName and os.path.isfile(backupFileName):
        uidGidDict = GetUidGidFromEnv(args.configDir)

        if (orchMode is OrchestrationFramework.DOCKER_COMPOSE) and (args.composeProfile == PROFILE_MALCOLM):
            # docker-compose use local temporary path
            osEnv = os.environ.copy()
            if not args.noTmpDirOverride:
                osEnv['TMPDIR'] = MalcolmTmpPath

            dockerCmdBase = [
                dockerComposeBin,
                '--profile',
                args.composeProfile,
                '-f',
                args.composeFile,
                'exec',
                # disable pseudo-TTY allocation
                '-T',
                # execute as UID:GID in docker-compose.yml file
                '-u',
                f'{uidGidDict["PUID"]}:{uidGidDict["PGID"]}',
                # run in the netbox container
                'netbox',
            ]

            # get remote temporary directory for restore
            dockerCmd = dockerCmdBase + ['mktemp', '-d', '-t', 'restore.XXXXXXXXXX']
            err, results = run_process(dockerCmd, env=osEnv, debug=args.debug)
            if (err == 0) and results:
                tmpRestoreDir = results[0]
            else:
                tmpRestoreDir = '/tmp'

            try:
                # copy database backup and media backup to remote temporary directory
                for tmpFile in [
                    x
                    for x in [backupFileName, os.path.splitext(backupFileName)[0] + ".media.tar.gz"]
                    if os.path.isfile(x)
                ]:
                    dockerCmd = dockerCmdBase + ['tee', os.path.join(tmpRestoreDir, os.path.basename(tmpFile))]
                    with open(tmpFile, 'rb') as f:
                        err, results = run_process(
                            dockerCmd, env=osEnv, debug=args.debug, stdout=False, stderr=True, stdin=f.read()
                        )
                    if err != 0:
                        raise Exception(
                            f'Error {err} copying backed-up NetBox file {os.path.basename(tmpFile)} to {tmpRestoreDir}: {results}'
                        )

                # perform the restore inside the container
                dockerCmd = dockerCmdBase + [
                    '/opt/netbox/venv/bin/python',
                    '/usr/local/bin/netbox_init.py',
                    '--preload-backup',
                    os.path.join(tmpRestoreDir, os.path.basename(backupFileName)),
                ]
                err, results = run_process(dockerCmd, env=osEnv, debug=args.debug)
                if err != 0:
                    raise Exception(
                        f'Error {err} restoring NetBox database {os.path.basename(backupFileName)}: {results}'
                    )

            finally:
                # cleanup the remote directory
                if tmpRestoreDir != '/tmp':
                    dockerCmd = dockerCmdBase + ['rm', '-rf', tmpRestoreDir]
                else:
                    dockerCmd = dockerCmdBase + [
                        'bash',
                        '-c',
                        f"rm -f {tmpRestoreDir}/{os.path.splitext(backupFileName)[0]}*",
                    ]
                run_process(dockerCmd, env=osEnv, debug=args.debug)

        elif orchMode is OrchestrationFramework.KUBERNETES:
            # copy database backup and media backup to remote temporary directory
            try:
                service_name = "netbox"
                container_name = "netbox-container"
                tmpRestoreDir = '/tmp'
                tmpRestoreFile = os.path.join(
                    tmpRestoreDir, os.path.splitext(os.path.basename(backupFileName))[0] + '.txt'
                )
                with gzip.open(backupFileName, 'rt') as f:
                    if podsResults := PodExec(
                        service=service_name,
                        namespace=args.namespace,
                        command=['tee', tmpRestoreFile],
                        stdout=False,
                        stderr=True,
                        stdin=f.read(),
                        container=container_name,
                    ):
                        err = 0 if all([deep_get(v, ['err'], 1) == 0 for k, v in podsResults.items()]) else 1
                        results = list(chain(*[deep_get(v, ['output'], '') for k, v in podsResults.items()]))
                    else:
                        err = 1
                        results = []
                if err != 0:
                    raise Exception(
                        f'Error {err} copying backed-up NetBox file {os.path.basename(backupFileName)} to {tmpRestoreFile}: {results}'
                    )

                # perform the restore inside the container
                if podsResults := PodExec(
                    service=service_name,
                    namespace=args.namespace,
                    command=[
                        '/opt/netbox/venv/bin/python',
                        '/usr/local/bin/netbox_init.py',
                        '--preload-backup',
                        tmpRestoreFile,
                    ],
                    container=container_name,
                ):
                    err = 0 if all([deep_get(v, ['err'], 1) == 0 for k, v in podsResults.items()]) else 1
                    results = list(chain(*[deep_get(v, ['output'], '') for k, v in podsResults.items()]))
                else:
                    err = 1
                    results = []
                if err != 0:
                    raise Exception(
                        f'Error {err} restoring NetBox database {os.path.basename(backupFileName)}: {results}'
                    )

            finally:
                # cleanup on other side
                PodExec(
                    service=service_name,
                    namespace=args.namespace,
                    command=[
                        'bash',
                        '-c',
                        f"rm -f {tmpRestoreDir}/{os.path.splitext(backupFileName)[0]}*",
                    ],
                    container=container_name,
                )

        else:
            raise Exception(
                f'{sys._getframe().f_code.co_name} does not yet support {orchMode} with profile {args.composeProfile}'
            )


###################################################################################################
def logs():
    global args
    global dockerBin
    global dockerComposeBin
    global orchMode
    global shuttingDown

    finishedStartingRegEx = re.compile(r'.+Pipelines\s+running\s+\{.*:non_running_pipelines=>\[\]\}')

    osEnv = os.environ.copy()
    # use local temporary path
    if not args.noTmpDirOverride:
        osEnv['TMPDIR'] = MalcolmTmpPath

    if orchMode is OrchestrationFramework.DOCKER_COMPOSE:
        # increase COMPOSE_HTTP_TIMEOUT to be ridiculously large so docker-compose never times out the TTY doing debug output
        osEnv['COMPOSE_HTTP_TIMEOUT'] = '100000000'

        cmd = [dockerComposeBin, '--profile', args.composeProfile, '-f', args.composeFile, 'ps']
        if args.service is not None:
            cmd.append(args.service)
        err, out = run_process(
            cmd,
            env=osEnv,
            debug=args.debug,
        )
        print("\n".join(out))

        cmd = [
            dockerComposeBin,
            '--profile',
            args.composeProfile,
            '-f',
            args.composeFile,
            'logs',
            '--tail',
            str(args.logLineCount) if args.logLineCount else 'all',
            '-f',
        ]
        if args.service is not None:
            cmd.append(args.service)

    elif orchMode is OrchestrationFramework.KUBERNETES:
        if which("stern"):
            cmd = [
                "stern",
                "--kubeconfig",
                args.composeFile,
                "--only-log-lines",
                "--color",
                'auto' if coloramaImported else 'never',
                "--template",
                (
                    '{{.Namespace}}/{{color .PodColor .PodName}}/{{color .ContainerColor .ContainerName}} | {{.Message}}{{"\\n"}}'
                    if args.debug
                    else '{{color .ContainerColor .ContainerName}} | {{.Message}}{{"\\n"}}'
                ),
                '--tail',
                str(args.logLineCount) if args.logLineCount else '-1',
            ]

            if args.namespace:
                cmd.extend(['--namespace', args.namespace])
            else:
                cmd.append('--all-namespaces')
            cmd.append(args.service if args.service else '.*')

        else:
            raise Exception(
                f'{sys._getframe().f_code.co_name} with orchestration mode {orchMode} requires "stern" (https://github.com/stern/stern/releases/latest)'
            )

    else:
        cmd = []
        raise Exception(f'{sys._getframe().f_code.co_name} does not yet support {orchMode}')

    if cmd:
        process = Popen(
            list(flatten(cmd)),
            env=osEnv,
            stdout=PIPE,
            stderr=None if args.debug else DEVNULL,
        )
        while not shuttingDown[0]:
            output = process.stdout.readline()
            if not output:
                if process.poll() is not None:
                    break
                else:
                    time.sleep(0.5)

            elif output := ProcessLogLine(output, debug=args.debug):
                print(output)

            if (
                output
                and (args.cmdStart or args.cmdRestart)
                and (not args.cmdLogs)
                and finishedStartingRegEx.match(output)
            ):
                shuttingDown[0] = True
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except TimeoutExpired:
                    process.kill()

                print("\nStarted Malcolm\n")
                printURLs()

        process.poll()


###################################################################################################
def stop(wipe=False):
    global args
    global dockerBin
    global dockerComposeBin
    global dockerComposeYaml
    global orchMode

    if orchMode is OrchestrationFramework.DOCKER_COMPOSE:
        # docker-compose use local temporary path
        osEnv = os.environ.copy()
        if not args.noTmpDirOverride:
            osEnv['TMPDIR'] = MalcolmTmpPath

        if args.service is not None:
            # stopping a single (or multiple services)
            err, out = run_process(
                [dockerComposeBin, '--profile', args.composeProfile, '-f', args.composeFile, 'stop'] + args.service,
                env=osEnv,
                debug=args.debug,
            )
            if err == 0:
                eprint(f"Stopped Malcolm's {args.service} services\n")
                err, out = run_process(
                    [dockerComposeBin, '--profile', args.composeProfile, '-f', args.composeFile, 'rm', '--force']
                    + args.service,
                    env=osEnv,
                    debug=args.debug,
                )
                if err == 0:
                    eprint(f"Removed Malcolm's {args.service} services\n")
                else:
                    eprint(f"Malcolm's {args.service} services failed to remove\n")
                    eprint("\n".join(out))
                    exit(err)
            else:
                eprint(f"Malcolm's {args.service} services failed to stop\n")
                eprint("\n".join(out))
                exit(err)

        else:
            # stopping malcolm
            # if stop.sh is being called with wipe.sh (after the docker-compose file)
            # then also remove named and anonymous volumes (not external volumes, of course)
            err, out = run_process(
                [dockerComposeBin, '--profile', args.composeProfile, '-f', args.composeFile, 'down', '--volumes'][
                    : 7 if wipe else -1
                ],
                env=osEnv,
                debug=args.debug,
            )
            if err == 0:
                eprint("Stopped Malcolm\n")
            else:
                eprint("Malcolm failed to stop\n")
                eprint("\n".join(out))
                exit(err)

            if wipe:
                # there is some overlap here among some of these containers, but it doesn't matter
                boundPathsToWipe = (
                    BoundPath("filebeat", "/zeek", True, None, None),
                    BoundPath("file-monitor", "/zeek/logs", True, None, None),
                    BoundPath("netbox", "/opt/netbox/netbox/media", True, None, ["."]),
                    BoundPath("netbox-postgres", "/var/lib/postgresql/data", True, None, ["."]),
                    BoundPath("redis", "/data", True, None, ["."]),
                    BoundPath("opensearch", "/usr/share/opensearch/data", True, ["nodes"], None),
                    BoundPath("pcap-monitor", "/pcap", True, ["arkime-live", "processed", "upload"], None),
                    BoundPath("suricata", "/var/log/suricata", True, None, ["."]),
                    BoundPath(
                        "upload",
                        "/var/www/upload/server/php/chroot/files",
                        True,
                        [os.path.join('tmp', 'spool'), "variants"],
                        None,
                    ),
                    BoundPath("zeek", "/zeek/extract_files", True, None, None),
                    BoundPath("zeek", "/zeek/upload", True, None, None),
                    BoundPath("zeek-live", "/zeek/live", True, ["spool"], None),
                    BoundPath(
                        "filebeat",
                        "/zeek",
                        False,
                        ["processed", "current", "live"],
                        ["processed", "current", "live"],
                    ),
                )
                for boundPath in boundPathsToWipe:
                    localPath = LocalPathForContainerBindMount(
                        boundPath.service,
                        dockerComposeYaml,
                        boundPath.target,
                        MalcolmPath,
                    )
                    if localPath and os.path.isdir(localPath):
                        # delete files
                        if boundPath.files:
                            if args.debug:
                                eprint(f'Walking "{localPath}" for file deletion')
                            for root, dirnames, filenames in os.walk(localPath, topdown=True, onerror=None):
                                for file in filenames:
                                    fileSpec = os.path.join(root, file)
                                    if (os.path.isfile(fileSpec) or os.path.islink(fileSpec)) and (
                                        not file.startswith('.git')
                                    ):
                                        try:
                                            os.remove(fileSpec)
                                        except Exception:
                                            pass
                        # delete whole directories
                        if boundPath.relative_dirs:
                            for relDir in get_iterable(boundPath.relative_dirs):
                                tmpPath = os.path.join(localPath, relDir)
                                if os.path.isdir(tmpPath):
                                    if args.debug:
                                        eprint(f'Performing rmtree on "{tmpPath}"')
                                    shutil.rmtree(tmpPath, ignore_errors=True)
                        # cleanup empty directories
                        if boundPath.clean_empty_dirs:
                            for cleanDir in get_iterable(boundPath.clean_empty_dirs):
                                tmpPath = os.path.join(localPath, cleanDir)
                                if os.path.isdir(tmpPath):
                                    if args.debug:
                                        eprint(f'Performing RemoveEmptyFolders on "{tmpPath}"')
                                    RemoveEmptyFolders(tmpPath, removeRoot=False)

                eprint("Malcolm has been stopped and its data cleared\n")

    elif orchMode is OrchestrationFramework.KUBERNETES:
        deleteResults = DeleteNamespace(
            namespace=args.namespace,
            deleteRetPerVol=args.deleteRetPerVol,
        )

        if dictsearch(deleteResults, 'error'):
            eprint(
                f"Deleting {args.namespace} namespace and its underlying resources returned the following error(s):\n"
            )
            eprint(deleteResults)
            eprint()

        else:
            eprint(f"The {args.namespace} namespace and its underlying resources have been deleted\n")
            if args.debug:
                eprint(deleteResults)
                eprint()

        if wipe:
            eprint(f'Data on PersistentVolume storage cannot be deleted by {ScriptName}: it must be deleted manually\n')

    else:
        raise Exception(f'{sys._getframe().f_code.co_name} does not yet support {orchMode}')


###################################################################################################
def start():
    global args
    global dockerBin
    global dockerComposeBin
    global orchMode

    if args.service is None:
        # touch the htadmin metadata file and .opensearch.*.curlrc files
        open(os.path.join(MalcolmPath, os.path.join('htadmin', 'metadata')), 'a').close()
        open(os.path.join(MalcolmPath, '.opensearch.primary.curlrc'), 'a').close()
        open(os.path.join(MalcolmPath, '.opensearch.secondary.curlrc'), 'a').close()

        # make sure the auth files exist. if we are in an interactive shell and we're
        # missing any of the auth files, prompt to create them now
        if sys.__stdin__.isatty() and (not MalcolmAuthFilesExist(configDir=args.configDir)):
            authSetup()

        # still missing? sorry charlie
        if not MalcolmAuthFilesExist(configDir=args.configDir):
            raise Exception(
                'Malcolm administrator account authentication files are missing, please run ./scripts/auth_setup to generate them'
            )

        # if the OpenSearch keystore doesn't exist exist, create empty ones
        if not os.path.isfile(os.path.join(MalcolmPath, os.path.join('opensearch', 'opensearch.keystore'))):
            keystore_op('opensearch', True, 'create')

        # make sure permissions are set correctly for the worker processes
        for authFile in [
            os.path.join(MalcolmPath, os.path.join('nginx', 'htpasswd')),
            os.path.join(MalcolmPath, os.path.join('htadmin', 'config.ini')),
            os.path.join(MalcolmPath, os.path.join('htadmin', 'metadata')),
        ]:
            # chmod 644 authFile
            os.chmod(authFile, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        for authFile in [
            os.path.join(MalcolmPath, os.path.join('nginx', 'nginx_ldap.conf')),
            os.path.join(MalcolmPath, '.opensearch.primary.curlrc'),
            os.path.join(MalcolmPath, '.opensearch.secondary.curlrc'),
        ]:
            # chmod 600 authFile
            os.chmod(authFile, stat.S_IRUSR | stat.S_IWUSR)
        with pushd(args.configDir):
            for envFile in glob.glob("*.env"):
                # chmod 600 envFile
                os.chmod(envFile, stat.S_IRUSR | stat.S_IWUSR)

        # touch the zeek intel file and zeek custom file
        open(os.path.join(MalcolmPath, os.path.join('zeek', os.path.join('intel', '__load__.zeek'))), 'a').close()
        open(os.path.join(MalcolmPath, os.path.join('zeek', os.path.join('custom', '__load__.zeek'))), 'a').close()

        # clean up any leftover intel update locks
        shutil.rmtree(
            os.path.join(MalcolmPath, os.path.join('zeek', os.path.join('intel', 'lock'))), ignore_errors=True
        )

    if orchMode is OrchestrationFramework.DOCKER_COMPOSE:
        if args.service is None:
            # make sure some directories exist before we start
            boundPathsToCreate = (
                BoundPath("file-monitor", "/zeek/logs", False, None, None),
                BoundPath("nginx-proxy", "/var/local/ca-trust", False, None, None),
                BoundPath("netbox", "/opt/netbox/netbox/media", False, None, None),
                BoundPath("netbox-postgres", "/var/lib/postgresql/data", False, None, None),
                BoundPath("redis", "/data", False, None, None),
                BoundPath("opensearch", "/usr/share/opensearch/data", False, ["nodes"], None),
                BoundPath("opensearch", "/opt/opensearch/backup", False, None, None),
                BoundPath("pcap-monitor", "/pcap", False, ["arkime-live", "processed", "upload"], None),
                BoundPath("suricata", "/var/log/suricata", False, ["live"], None),
                BoundPath(
                    "upload",
                    "/var/www/upload/server/php/chroot/files",
                    False,
                    [os.path.join('tmp', 'spool'), "variants"],
                    None,
                ),
                BoundPath("zeek", "/zeek/extract_files", False, None, None),
                BoundPath("zeek", "/zeek/upload", False, None, None),
                BoundPath("zeek", "/opt/zeek/share/zeek/site/custom", False, None, None),
                BoundPath("zeek", "/opt/zeek/share/zeek/site/intel", False, ["Mandiant", "MISP", "STIX"], None),
                BoundPath("zeek-live", "/zeek/live", False, ["spool"], None),
                BoundPath(
                    "filebeat", "/zeek", False, ["processed", "current", "live", "extract_files", "upload"], None
                ),
            )
            for boundPath in boundPathsToCreate:
                localPath = LocalPathForContainerBindMount(
                    boundPath.service,
                    dockerComposeYaml,
                    boundPath.target,
                    MalcolmPath,
                )
                if localPath:
                    try:
                        if args.debug:
                            eprint(f'Ensuring "{localPath}" exists')
                        os.makedirs(localPath)
                    except OSError as exc:
                        if (exc.errno == errno.EEXIST) and os.path.isdir(localPath):
                            pass
                        else:
                            raise
                    if boundPath.relative_dirs:
                        for relDir in get_iterable(boundPath.relative_dirs):
                            tmpPath = os.path.join(localPath, relDir)
                            try:
                                if args.debug:
                                    eprint(f'Ensuring "{tmpPath}" exists')
                                os.makedirs(tmpPath)
                            except OSError as exc:
                                if (exc.errno == errno.EEXIST) and os.path.isdir(tmpPath):
                                    pass
                                else:
                                    raise

        # increase COMPOSE_HTTP_TIMEOUT to be ridiculously large so docker-compose never times out the TTY doing debug output
        osEnv = os.environ.copy()
        osEnv['COMPOSE_HTTP_TIMEOUT'] = '100000000'
        # docker-compose use local temporary path
        if not args.noTmpDirOverride:
            osEnv['TMPDIR'] = MalcolmTmpPath

        # start docker
        cmd = [
            dockerComposeBin,
            '--profile',
            args.composeProfile,
            '-f',
            args.composeFile,
            'up',
            '--detach',
        ]
        if args.service is not None:
            cmd.append(['--no-deps', args.service])

        err, out = run_process(
            cmd,
            env=osEnv,
            debug=args.debug,
        )
        if err != 0:
            eprint("Malcolm failed to start\n")
            eprint("\n".join(out))
            exit(err)

    elif orchMode is OrchestrationFramework.KUBERNETES:
        if CheckPersistentStorageDefs(
            namespace=args.namespace,
            malcolmPath=MalcolmPath,
            profile=args.composeProfile,
        ):
            startResults = StartMalcolm(
                namespace=args.namespace,
                malcolmPath=MalcolmPath,
                configPath=args.configDir,
                profile=args.composeProfile,
            )

            if dictsearch(startResults, 'error'):
                eprint(
                    f"Starting the {args.namespace} namespace and creating its underlying resources returned the following error(s):\n"
                )
                eprint(startResults)
                eprint()

            elif args.debug:
                eprint()
                eprint(startResults)
                eprint()

        else:
            groupedStorageEntries = {
                i: [j[0] for j in j]
                for i, j in groupby(sorted(REQUIRED_VOLUME_OBJECTS.items(), key=lambda x: x[1]), lambda x: x[1])
            }
            raise Exception(
                f'Storage objects required by Malcolm are not defined in {os.path.join(MalcolmPath, "kubernetes")}: {groupedStorageEntries}'
            )

    else:
        raise Exception(f'{sys._getframe().f_code.co_name} does not yet support {orchMode}')


###################################################################################################
def clientForwarderCertGen(caCrt, caKey, clientConf, outputDir):
    global args
    global opensslBin

    clientKey = None
    clientCrt = None
    clientCaCrt = None

    with tempfile.TemporaryDirectory(dir=MalcolmTmpPath) as tmpCertDir:
        with pushd(tmpCertDir):
            err, out = run_process(
                [opensslBin, 'genrsa', '-out', 'client.key', '2048'],
                stderr=True,
                debug=args.debug,
            )
            if err != 0:
                raise Exception(f'Unable to generate client.key: {out}')

            err, out = run_process(
                [
                    opensslBin,
                    'req',
                    '-sha512',
                    '-new',
                    '-key',
                    'client.key',
                    '-out',
                    'client.csr',
                    '-config',
                    clientConf,
                ],
                stderr=True,
                debug=args.debug,
            )
            if err != 0:
                raise Exception(f'Unable to generate client.csr: {out}')

            err, out = run_process(
                [
                    opensslBin,
                    'x509',
                    '-days',
                    '3650',
                    '-req',
                    '-sha512',
                    '-in',
                    'client.csr',
                    '-CAcreateserial',
                    '-CA',
                    caCrt,
                    '-CAkey',
                    caKey,
                    '-out',
                    'client.crt',
                    '-extensions',
                    'v3_req',
                    '-extensions',
                    'usr_cert',
                    '-extfile',
                    clientConf,
                ],
                stderr=True,
                debug=args.debug,
            )
            if err != 0:
                raise Exception(f'Unable to generate client.crt: {out}')

            if os.path.isfile('client.key'):
                shutil.move('client.key', outputDir)
                clientKey = os.path.join(outputDir, 'client.key')
            if os.path.isfile('client.crt'):
                shutil.move('client.crt', outputDir)
                clientCrt = os.path.join(outputDir, 'client.crt')
            clientCaCrt = os.path.join(outputDir, os.path.basename(caCrt))
            if not os.path.isfile(clientCaCrt) or not same_file_or_dir(caCrt, clientCaCrt):
                shutil.copy2(caCrt, clientCaCrt)
            # -----------------------------------------------

    return clientKey, clientCrt, clientCaCrt


###################################################################################################
def authSetup():
    global args
    global opensslBin
    global dotenvImported

    # for beats/logstash self-signed certificates
    logstashPath = os.path.join(MalcolmPath, os.path.join('logstash', 'certs'))
    filebeatPath = os.path.join(MalcolmPath, os.path.join('filebeat', 'certs'))

    txRxScript = None
    if (pyPlatform != PLATFORM_WINDOWS) and which("croc"):
        txRxScript = 'tx-rx-secure.sh' if which('tx-rx-secure.sh') else None
        if not txRxScript:
            txRxScript = os.path.join(
                MalcolmPath, os.path.join('shared', os.path.join('bin', os.path.join('tx-rx-secure.sh')))
            )
            txRxScript = txRxScript if (txRxScript and os.path.isfile(txRxScript)) else '/usr/local/bin/tx-rx-secure.sh'
            txRxScript = txRxScript if (txRxScript and os.path.isfile(txRxScript)) else '/usr/bin/tx-rx-secure.sh'
            txRxScript = txRxScript if (txRxScript and os.path.isfile(txRxScript)) else None

    # don't make them go through every thing every time, give them a choice instead
    authModeChoices = (
        (
            'all',
            "Configure all authentication-related settings",
            True,
            True,
            [],
        ),
        (
            'admin',
            "Store administrator username/password for local Malcolm access",
            False,
            (not args.cmdAuthSetupNonInteractive)
            or (bool(args.authUserName) and bool(args.authPasswordOpenssl) and bool(args.authPasswordHtpasswd)),
            [],
        ),
        (
            'webcerts',
            "(Re)generate self-signed certificates for HTTPS access",
            False,
            not args.cmdAuthSetupNonInteractive
            or (
                args.authGenWebCerts
                or not os.path.isfile(
                    os.path.join(MalcolmPath, os.path.join('nginx', os.path.join('certs', 'key.pem')))
                )
            ),
            [os.path.join(MalcolmPath, os.path.join('nginx', os.path.join('certs', 'key.pem')))],
        ),
        (
            'fwcerts',
            "(Re)generate self-signed certificates for a remote log forwarder",
            False,
            not args.cmdAuthSetupNonInteractive
            or (
                args.authGenFwCerts
                or not os.path.isfile(os.path.join(logstashPath, 'server.key'))
                or not os.path.isfile(os.path.join(filebeatPath, 'client.key'))
            ),
            [
                os.path.join(logstashPath, 'server.key'),
                os.path.join(filebeatPath, 'client.key'),
            ],
        ),
        (
            'remoteos',
            "Configure remote primary or secondary OpenSearch/Elasticsearch instance",
            False,
            False,
            [],
        ),
        (
            'email',
            "Store username/password for OpenSearch Alerting email sender account",
            False,
            False,
            [],
        ),
        (
            'netbox',
            "(Re)generate internal passwords for NetBox",
            False,
            (not args.cmdAuthSetupNonInteractive) or args.authGenNetBoxPasswords,
            [],
        ),
        (
            'arkime',
            "Store password hash secret for Arkime viewer cluster",
            False,
            False,
            [],
        ),
        (
            'txfwcerts',
            "Transfer self-signed client certificates to a remote log forwarder",
            False,
            False,
            [],
        ),
    )[: 9 if txRxScript else -1]

    authMode = (
        ChooseOne(
            'Configure Authentication',
            choices=[x[:-2] for x in authModeChoices],
        )
        if not args.cmdAuthSetupNonInteractive
        else 'all'
    )
    noninteractiveBehavior = (
        UserInputDefaultsBehavior.DefaultsPrompt
        | UserInputDefaultsBehavior.DefaultsAccept
        | UserInputDefaultsBehavior.DefaultsNonInteractive
    )
    defaultBehavior = (
        UserInputDefaultsBehavior.DefaultsPrompt if not args.cmdAuthSetupNonInteractive else noninteractiveBehavior
    )

    try:
        for authItem in authModeChoices[1:]:
            if (
                (authMode == 'all')
                and YesOrNo(
                    f'{authItem[1]}?',
                    default=authItem[3],
                    defaultBehavior=(
                        noninteractiveBehavior
                        if (authItem[4] and (not all([os.path.isfile(x) for x in authItem[4]])))
                        else defaultBehavior
                    ),
                )
            ) or ((authMode != 'all') and (authMode == authItem[0])):
                if authItem[0] == 'admin':
                    # prompt username and password
                    usernamePrevious = None
                    password = None
                    passwordConfirm = None
                    passwordEncrypted = ''

                    loopBreaker = CountUntilException(MaxAskForValueCount, 'Invalid administrator username')
                    while loopBreaker.increment():
                        username = AskForString(
                            f"Administrator username (between {UsernameMinLen} and {UsernameMaxLen} characters; alphanumeric, _, -, and . allowed)",
                            default=args.authUserName,
                            defaultBehavior=defaultBehavior,
                        )
                        if UsernameRegex.match(username) and (UsernameMinLen <= len(username) <= UsernameMaxLen):
                            break

                    loopBreaker = CountUntilException(MaxAskForValueCount, 'Invalid password')
                    while (not args.cmdAuthSetupNonInteractive) and loopBreaker.increment():
                        password = AskForPassword(
                            f"{username} password  (between {PasswordMinLen} and {PasswordMaxLen} characters): ",
                            default='',
                            defaultBehavior=defaultBehavior,
                        )
                        if PasswordMinLen <= len(password) <= PasswordMaxLen:
                            passwordConfirm = AskForPassword(
                                f"{username} password (again): ",
                                default='',
                                defaultBehavior=defaultBehavior,
                            )
                            if password and (password == passwordConfirm):
                                break

                    # get previous admin username to remove from htpasswd file if it's changed
                    authEnvFile = os.path.join(args.configDir, 'auth.env')
                    if os.path.isfile(authEnvFile):
                        prevAuthInfo = defaultdict(str)
                        with open(authEnvFile, 'r') as f:
                            for line in f:
                                try:
                                    k, v = line.rstrip().split("=")
                                    prevAuthInfo[k] = v.strip('"')
                                except Exception:
                                    pass
                        if len(prevAuthInfo['MALCOLM_USERNAME']) > 0:
                            usernamePrevious = prevAuthInfo['MALCOLM_USERNAME']

                    # get openssl hash of password
                    if args.cmdAuthSetupNonInteractive:
                        passwordEncrypted = args.authPasswordOpenssl
                    else:
                        err, out = run_process(
                            [opensslBin, 'passwd', '-1', '-stdin'],
                            stdin=password,
                            stderr=False,
                            debug=args.debug,
                        )
                        if (err == 0) and (len(out) > 0) and (len(out[0]) > 0):
                            passwordEncrypted = out[0]
                        else:
                            raise Exception('Unable to generate password hash with openssl')

                    # write auth.env (used by htadmin and file-upload containers)
                    with open(authEnvFile, 'w') as f:
                        f.write(
                            "# Malcolm Administrator username and encrypted password for nginx reverse proxy (and upload server's SFTP access)\n"
                        )
                        f.write(f'MALCOLM_USERNAME={username}\n')
                        f.write(f'MALCOLM_PASSWORD={b64encode(passwordEncrypted.encode()).decode("ascii")}\n')
                        f.write('K8S_SECRET=True\n')
                    os.chmod(authEnvFile, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

                    # create or update the htpasswd file
                    htpasswdFile = os.path.join(MalcolmPath, os.path.join('nginx', 'htpasswd'))
                    if not args.cmdAuthSetupNonInteractive:
                        htpasswdCmd = ['htpasswd', '-i', '-B', htpasswdFile, username]
                        if not os.path.isfile(htpasswdFile):
                            htpasswdCmd.insert(1, '-c')
                        err, out = run_process(htpasswdCmd, stdin=password, stderr=True, debug=args.debug)
                        if err != 0:
                            raise Exception(f'Unable to generate htpasswd file: {out}')

                    if (
                        (usernamePrevious is not None) and (usernamePrevious != username)
                    ) or args.cmdAuthSetupNonInteractive:
                        htpasswdLines = list()
                        if os.path.isfile(htpasswdFile):
                            with open(htpasswdFile, 'r') as f:
                                htpasswdLines = f.readlines()
                        with open(htpasswdFile, 'w') as f:
                            if args.cmdAuthSetupNonInteractive and username and args.authPasswordHtpasswd:
                                f.write(f'{username}:{args.authPasswordHtpasswd}')
                            for line in htpasswdLines:
                                # if the admininstrator username has changed, remove the previous administrator username from htpasswd
                                if (
                                    (usernamePrevious is not None)
                                    and (usernamePrevious != username)
                                    and (not line.startswith(f"{usernamePrevious}:"))
                                ):
                                    f.write(line)

                    # configure default LDAP stuff (they'll have to edit it by hand later)
                    ldapConfFile = os.path.join(MalcolmPath, os.path.join('nginx', 'nginx_ldap.conf'))
                    if not os.path.isfile(ldapConfFile):
                        ldapDefaults = defaultdict(str)
                        if os.path.isfile(os.path.join(MalcolmPath, '.ldap_config_defaults')):
                            ldapDefaults = defaultdict(str)
                            with open(os.path.join(MalcolmPath, '.ldap_config_defaults'), 'r') as f:
                                for line in f:
                                    try:
                                        k, v = line.rstrip().split("=")
                                        ldapDefaults[k] = v.strip('"').strip("'")
                                    except Exception:
                                        pass
                        ldapProto = ldapDefaults.get("LDAP_PROTO", "ldap://")
                        ldapHost = ldapDefaults.get("LDAP_HOST", "ds.example.com")
                        ldapPort = ldapDefaults.get("LDAP_PORT", "3268")
                        ldapType = ldapDefaults.get("LDAP_SERVER_TYPE", "winldap")
                        if ldapType == "openldap":
                            ldapUri = 'DC=example,DC=com?uid?sub?(objectClass=posixAccount)'
                            ldapGroupAttr = "memberUid"
                            ldapGroupAttrIsDN = "off"
                        else:
                            ldapUri = 'DC=example,DC=com?sAMAccountName?sub?(objectClass=person)'
                            ldapGroupAttr = "member"
                            ldapGroupAttrIsDN = "on"
                        with open(ldapConfFile, 'w') as f:
                            f.write('# This is a sample configuration for the ldap_server section of nginx.conf.\n')
                            f.write(
                                '# Yours will vary depending on how your Active Directory/LDAP server is configured.\n'
                            )
                            f.write(
                                '# See https://github.com/kvspb/nginx-auth-ldap#available-config-parameters for options.\n\n'
                            )
                            f.write('ldap_server ad_server {\n')
                            f.write(f'  url "{ldapProto}{ldapHost}:{ldapPort}/{ldapUri}";\n\n')
                            f.write('  binddn "bind_dn";\n')
                            f.write('  binddn_passwd "bind_dn_password";\n\n')
                            f.write(f'  group_attribute {ldapGroupAttr};\n')
                            f.write(f'  group_attribute_is_dn {ldapGroupAttrIsDN};\n')
                            f.write('  require group "CN=malcolm,OU=groups,DC=example,DC=com";\n')
                            f.write('  require valid_user;\n')
                            f.write('  satisfy all;\n')
                            f.write('}\n\n')
                            f.write('auth_ldap_cache_enabled on;\n')
                            f.write('auth_ldap_cache_expiration_time 10000;\n')
                            f.write('auth_ldap_cache_size 1000;\n')
                        os.chmod(ldapConfFile, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

                    # populate htadmin config file
                    with open(os.path.join(MalcolmPath, os.path.join('htadmin', 'config.ini')), 'w') as f:
                        f.write('; HTAdmin config file.\n\n')
                        f.write('[application]\n')
                        f.write('; Change this to customize your title:\n')
                        f.write('app_title = Malcolm User Management\n\n')
                        f.write('; htpasswd file\n')
                        f.write('secure_path  = ./auth/htpasswd\n')
                        f.write('; metadata file\n')
                        f.write('metadata_path  = ./config/metadata\n\n')
                        f.write('; administrator user/password (htpasswd -b -c -B ...)\n')
                        f.write(f'admin_user = {username}\n\n')
                        f.write('; username field quality checks\n')
                        f.write(';\n')
                        f.write(f'min_username_len = {UsernameMinLen}\n')
                        f.write(f'max_username_len = {UsernameMaxLen}\n\n')
                        f.write('; Password field quality checks\n')
                        f.write(';\n')
                        f.write(f'min_password_len = {PasswordMinLen}\n')
                        f.write(f'max_password_len = {PasswordMaxLen}\n\n')

                    # touch the metadata file
                    open(os.path.join(MalcolmPath, os.path.join('htadmin', 'metadata')), 'a').close()

                    DisplayMessage(
                        'Additional local accounts can be created at https://localhost/auth/ when Malcolm is running',
                        defaultBehavior=defaultBehavior,
                    )

                # generate HTTPS self-signed certificates
                elif authItem[0] == 'webcerts':
                    with pushd(os.path.join(MalcolmPath, os.path.join('nginx', 'certs'))):
                        # remove previous files
                        for oldfile in glob.glob("*.pem"):
                            os.remove(oldfile)

                        # generate dhparam -------------------------------
                        err, out = run_process(
                            [opensslBin, 'dhparam', '-out', 'dhparam.pem', '2048'],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate dhparam.pem file: {out}')

                        # generate key/cert -------------------------------
                        err, out = run_process(
                            [
                                opensslBin,
                                'req',
                                '-subj',
                                '/CN=localhost',
                                '-x509',
                                '-newkey',
                                'rsa:4096',
                                '-nodes',
                                '-keyout',
                                'key.pem',
                                '-out',
                                'cert.pem',
                                '-days',
                                '3650',
                            ],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate key.pem/cert.pem file(s): {out}')

                elif authItem[0] == 'fwcerts':
                    with pushd(logstashPath):
                        # make clean to clean previous files
                        for pat in ['*.srl', '*.csr', '*.key', '*.crt', '*.pem']:
                            for oldfile in glob.glob(pat):
                                os.remove(oldfile)

                        # -----------------------------------------------
                        # generate new ca/server/client certificates/keys
                        # ca -------------------------------
                        err, out = run_process(
                            [opensslBin, 'genrsa', '-out', 'ca.key', '2048'],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate ca.key: {out}')

                        err, out = run_process(
                            [
                                opensslBin,
                                'req',
                                '-x509',
                                '-new',
                                '-nodes',
                                '-key',
                                'ca.key',
                                '-sha256',
                                '-days',
                                '9999',
                                '-subj',
                                '/C=US/ST=ID/O=sensor/OU=ca',
                                '-out',
                                'ca.crt',
                            ],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate ca.crt: {out}')

                        # server -------------------------------
                        err, out = run_process(
                            [opensslBin, 'genrsa', '-out', 'server.key', '2048'],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate server.key: {out}')

                        err, out = run_process(
                            [
                                opensslBin,
                                'req',
                                '-sha512',
                                '-new',
                                '-key',
                                'server.key',
                                '-out',
                                'server.csr',
                                '-config',
                                'server.conf',
                            ],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate server.csr: {out}')

                        err, out = run_process(
                            [
                                opensslBin,
                                'x509',
                                '-days',
                                '3650',
                                '-req',
                                '-sha512',
                                '-in',
                                'server.csr',
                                '-CAcreateserial',
                                '-CA',
                                'ca.crt',
                                '-CAkey',
                                'ca.key',
                                '-out',
                                'server.crt',
                                '-extensions',
                                'v3_req',
                                '-extfile',
                                'server.conf',
                            ],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate server.crt: {out}')

                        shutil.move("server.key", "server.key.pem")
                        err, out = run_process(
                            [opensslBin, 'pkcs8', '-in', 'server.key.pem', '-topk8', '-nocrypt', '-out', 'server.key'],
                            stderr=True,
                            debug=args.debug,
                        )
                        if err != 0:
                            raise Exception(f'Unable to generate server.key: {out}')

                        # client -------------------------------
                        # mkdir filebeat/certs if it doesn't exist
                        try:
                            os.makedirs(filebeatPath)
                        except OSError as exc:
                            if (exc.errno == errno.EEXIST) and os.path.isdir(filebeatPath):
                                pass
                            else:
                                raise

                        # remove previous files in filebeat/certs
                        for oldfile in glob.glob(os.path.join(filebeatPath, "*")):
                            os.remove(oldfile)

                        clientKey, clientCrt, clientCaCrt = clientForwarderCertGen(
                            caCrt=os.path.join(logstashPath, 'ca.crt'),
                            caKey=os.path.join(logstashPath, 'ca.key'),
                            clientConf=os.path.join(logstashPath, 'client.conf'),
                            outputDir=filebeatPath,
                        )
                        if (
                            (not clientKey)
                            or (not clientCrt)
                            or (not clientCaCrt)
                            or (not os.path.isfile(clientKey))
                            or (not os.path.isfile(clientCrt))
                            or (not os.path.isfile(clientCaCrt))
                        ):
                            raise Exception(f'Unable to generate client key/crt')
                        # -----------------------------------------------

                # create and populate connection parameters file for remote OpenSearch instance(s)
                elif authItem[0] == 'remoteos':
                    for instance in ['primary', 'secondary']:
                        openSearchCredFileName = os.path.join(MalcolmPath, f'.opensearch.{instance}.curlrc')
                        if YesOrNo(
                            f'Store username/password for {instance} remote OpenSearch/Elasticsearch instance?',
                            default=False,
                            defaultBehavior=defaultBehavior,
                        ):
                            prevCurlContents = ParseCurlFile(openSearchCredFileName)

                            # prompt host, username and password
                            esUsername = None
                            esPassword = None
                            esPasswordConfirm = None

                            loopBreaker = CountUntilException(
                                MaxAskForValueCount, 'Invalid OpenSearch/Elasticsearch username'
                            )
                            while loopBreaker.increment():
                                esUsername = AskForString(
                                    "OpenSearch/Elasticsearch username",
                                    default=prevCurlContents['user'],
                                    defaultBehavior=defaultBehavior,
                                )
                                if (len(esUsername) > 0) and (':' not in esUsername):
                                    break
                                eprint("Username is blank (or contains a colon, which is not allowed)")

                            loopBreaker = CountUntilException(
                                MaxAskForValueCount, 'Invalid OpenSearch/Elasticsearch password'
                            )
                            while loopBreaker.increment():
                                esPassword = AskForPassword(
                                    f"{esUsername} password: ",
                                    default='',
                                    defaultBehavior=defaultBehavior,
                                )
                                if (
                                    (len(esPassword) == 0)
                                    and (prevCurlContents['password'] is not None)
                                    and YesOrNo(
                                        f'Use previously entered password for "{esUsername}"?',
                                        default=True,
                                        defaultBehavior=defaultBehavior,
                                    )
                                ):
                                    esPassword = prevCurlContents['password']
                                    esPasswordConfirm = esPassword
                                else:
                                    esPasswordConfirm = AskForPassword(
                                        f"{esUsername} password (again): ",
                                        default='',
                                        defaultBehavior=defaultBehavior,
                                    )
                                if (esPassword == esPasswordConfirm) and (len(esPassword) > 0):
                                    break
                                eprint("Passwords do not match")

                            esSslVerify = YesOrNo(
                                'Require SSL certificate validation for OpenSearch/Elasticsearch communication?',
                                default=False,
                                defaultBehavior=defaultBehavior,
                            )

                            with open(openSearchCredFileName, 'w') as f:
                                f.write(f'user: "{EscapeForCurl(esUsername)}:{EscapeForCurl(esPassword)}"\n')
                                if not esSslVerify:
                                    f.write('insecure\n')

                        else:
                            try:
                                os.remove(openSearchCredFileName)
                            except Exception:
                                pass
                        open(openSearchCredFileName, 'a').close()
                        os.chmod(openSearchCredFileName, stat.S_IRUSR | stat.S_IWUSR)

                # OpenSearch authenticate sender account credentials
                # https://opensearch.org/docs/latest/monitoring-plugins/alerting/monitors/#authenticate-sender-account
                elif authItem[0] == 'email':
                    # prompt username and password
                    emailPassword = None
                    emailPasswordConfirm = None
                    emailSender = AskForString("OpenSearch alerting email sender name", defaultBehavior=defaultBehavior)
                    loopBreaker = CountUntilException(MaxAskForValueCount, 'Invalid Email account username')
                    while loopBreaker.increment():
                        emailUsername = AskForString("Email account username", defaultBehavior=defaultBehavior)
                        if len(emailUsername) > 0:
                            break

                    loopBreaker = CountUntilException(MaxAskForValueCount, 'Invalid Email account password')
                    while loopBreaker.increment():
                        emailPassword = AskForPassword(
                            f"{emailUsername} password: ",
                            default='',
                            defaultBehavior=defaultBehavior,
                        )
                        emailPasswordConfirm = AskForPassword(
                            f"{emailUsername} password (again): ",
                            default='',
                            defaultBehavior=defaultBehavior,
                        )
                        if emailPassword and (emailPassword == emailPasswordConfirm):
                            break
                        eprint("Passwords do not match")

                    # create OpenSearch keystore file, don't complain if it already exists, and set the keystore items
                    usernameKey = f'plugins.alerting.destination.email.{emailSender}.username'
                    passwordKey = f'plugins.alerting.destination.email.{emailSender}.password'

                    keystore_op('opensearch', True, 'create', stdin='N')
                    keystore_op('opensearch', True, 'remove', usernameKey)
                    keystore_op('opensearch', True, 'add', usernameKey, '--stdin', stdin=emailUsername)
                    keystore_op('opensearch', True, 'remove', passwordKey)
                    keystore_op('opensearch', True, 'add', passwordKey, '--stdin', stdin=emailPassword)
                    success, results = keystore_op('opensearch', True, 'list')
                    results = [
                        x
                        for x in results
                        if x and (not x.upper().startswith('WARNING')) and (not x.upper().startswith('KEYSTORE'))
                    ]
                    if success and (usernameKey in results) and (passwordKey in results):
                        eprint(f"Email alert sender account variables stored: {', '.join(results)}")
                    else:
                        eprint("Failed to store email alert sender account variables:\n")
                        eprint("\n".join(results))

                elif authItem[0] == 'netbox':
                    with pushd(args.configDir):

                        # Check for the presence of existing passwords prior to setting new NetBox passwords.
                        #   see cisagov/Malcolm#565 (NetBox fails to start due to invalid internal password
                        #   if NetBox passwords have been changed).

                        preExistingPasswordFound = False
                        preExistingPasswords = {
                            'netbox-postgres.env': (
                                'POSTGRES_PASSWORD',
                                'DB_PASSWORD',
                            ),
                            'redis.env': ('REDIS_PASSWORD',),
                            'netbox-secret.env': (
                                'SECRET_KEY',
                                'SUPERUSER_PASSWORD',
                                'SUPERUSER_API_TOKEN',
                            ),
                        }
                        for envFile, keys in preExistingPasswords.items():
                            envValues = defaultdict(None)
                            if os.path.isfile(envFile):
                                envValues.update(dotenvImported.dotenv_values(envFile))
                            for key in keys:
                                if keyVal := envValues[key]:
                                    if all(c in "xX" for c in keyVal) or (
                                        (key == 'SUPERUSER_PASSWORD') and (keyVal == 'admin')
                                    ):
                                        # all good, no password has been set yet
                                        pass
                                    else:
                                        # preexisting password was found, need to warn the user
                                        preExistingPasswordFound = True

                        if (not preExistingPasswordFound) or YesOrNo(
                            'Internal passwords for NetBox already exist. Overwriting them will break access to a populated NetBox database. Are you sure?',
                            default=args.cmdAuthSetupNonInteractive,
                            defaultBehavior=defaultBehavior,
                        ):

                            netboxPwAlphabet = string.ascii_letters + string.digits + '_'
                            netboxKeyAlphabet = string.ascii_letters + string.digits + '%@<=>?~^_-'
                            netboxPostGresPassword = ''.join(secrets.choice(netboxPwAlphabet) for i in range(24))
                            redisPassword = ''.join(secrets.choice(netboxPwAlphabet) for i in range(24))
                            netboxSuPassword = ''.join(secrets.choice(netboxPwAlphabet) for i in range(24))
                            netboxSuToken = ''.join(secrets.choice(netboxPwAlphabet) for i in range(40))
                            netboxSecretKey = ''.join(secrets.choice(netboxKeyAlphabet) for i in range(50))

                            with open('netbox-postgres.env', 'w') as f:
                                f.write('DB_HOST=netbox-postgres\n')
                                f.write('POSTGRES_DB=netbox\n')
                                f.write('DB_NAME=netbox\n')
                                f.write('POSTGRES_USER=netbox\n')
                                f.write('DB_USER=netbox\n')
                                f.write(f'POSTGRES_PASSWORD={netboxPostGresPassword}\n')
                                f.write(f'DB_PASSWORD={netboxPostGresPassword}\n')
                                f.write('K8S_SECRET=True\n')
                            os.chmod('netbox-postgres.env', stat.S_IRUSR | stat.S_IWUSR)

                            with open('redis.env', 'w') as f:
                                f.write(f'REDIS_HOST=redis\n')
                                f.write(f'REDIS_CACHE_HOST=redis-cache\n')
                                f.write(f'REDIS_PASSWORD={redisPassword}\n')
                                f.write('K8S_SECRET=True\n')
                            os.chmod('redis.env', stat.S_IRUSR | stat.S_IWUSR)

                            if (not os.path.isfile('netbox-secret.env')) and (
                                os.path.isfile('netbox-secret.env.example')
                            ):
                                shutil.copy2('netbox-secret.env.example', 'netbox-secret.env')

                            with fileinput.FileInput('netbox-secret.env', inplace=True, backup=None) as envFile:
                                for line in envFile:
                                    line = line.rstrip("\n")

                                    if line.startswith('SECRET_KEY'):
                                        line = re.sub(
                                            r'(SECRET_KEY\s*=\s*)(.*?)$',
                                            fr"\g<1>{netboxSecretKey}",
                                            line,
                                        )
                                    elif line.startswith('SUPERUSER_PASSWORD'):
                                        line = re.sub(
                                            r'(SUPERUSER_PASSWORD\s*=\s*)(.*?)$',
                                            fr"\g<1>{netboxSuPassword}",
                                            line,
                                        )
                                    elif line.startswith('SUPERUSER_API_TOKEN'):
                                        line = re.sub(
                                            r'(SUPERUSER_API_TOKEN\s*=\s*)(.*?)$',
                                            fr"\g<1>{netboxSuToken}",
                                            line,
                                        )
                                    elif line.startswith('K8S_SECRET'):
                                        line = re.sub(
                                            r'(SUPERUSER_API_TOKEN\s*=\s*)(.*?)$',
                                            fr"\g<1>True",
                                            line,
                                        )

                                    print(line)

                            os.chmod('netbox-secret.env', stat.S_IRUSR | stat.S_IWUSR)

                        else:
                            DisplayMessage(
                                'Internal passwords for NetBox were left unmodified.',
                                defaultBehavior=defaultBehavior,
                            )

                elif authItem[0] == 'arkime':
                    # prompt password
                    arkimePassword = None
                    arkimePasswordConfirm = None

                    loopBreaker = CountUntilException(MaxAskForValueCount, 'Invalid password hash secret')
                    while loopBreaker.increment():
                        arkimePassword = AskForPassword(
                            f"Arkime password hash secret: ",
                            default='',
                            defaultBehavior=defaultBehavior,
                        )
                        arkimePasswordConfirm = AskForPassword(
                            f"Arkime password hash secret (again): ",
                            default='',
                            defaultBehavior=defaultBehavior,
                        )
                        if arkimePassword and (arkimePassword == arkimePasswordConfirm):
                            break
                        eprint("Passwords do not match")

                    if (not arkimePassword) and args.cmdAuthSetupNonInteractive and args.authArkimePassword:
                        arkimePassword = args.authArkimePassword

                    with pushd(args.configDir):
                        if (not os.path.isfile('arkime-secret.env')) and (os.path.isfile('arkime-secret.env.example')):
                            shutil.copy2('arkime-secret.env.example', 'arkime-secret.env')

                        with fileinput.FileInput('arkime-secret.env', inplace=True, backup=None) as envFile:
                            for line in envFile:
                                line = line.rstrip("\n")

                                if arkimePassword and line.startswith('ARKIME_PASSWORD_SECRET'):
                                    line = re.sub(
                                        r'(ARKIME_PASSWORD_SECRET\s*=\s*)(.*?)$',
                                        fr"\g<1>{arkimePassword}",
                                        line,
                                    )

                                print(line)

                        os.chmod('arkime-secret.env', stat.S_IRUSR | stat.S_IWUSR)

                elif authItem[0] == 'txfwcerts':
                    DisplayMessage(
                        'Run configure-capture on the remote log forwarder, select "Configure Forwarding," then "Receive client SSL files..."',
                        defaultBehavior=defaultBehavior,
                    )
                    # generate new client key/crt and send it
                    with tempfile.TemporaryDirectory(dir=MalcolmTmpPath) as tmpCertDir:
                        with pushd(tmpCertDir):
                            clientKey, clientCrt, clientCaCrt = clientForwarderCertGen(
                                caCrt=os.path.join(logstashPath, 'ca.crt'),
                                caKey=os.path.join(logstashPath, 'ca.key'),
                                clientConf=os.path.join(logstashPath, 'client.conf'),
                                outputDir=tmpCertDir,
                            )
                            if (
                                (not clientKey)
                                or (not clientCrt)
                                or (not clientCaCrt)
                                or (not os.path.isfile(clientKey))
                                or (not os.path.isfile(clientCrt))
                                or (not os.path.isfile(clientCaCrt))
                            ):
                                raise Exception(f'Unable to generate client key/crt')

                            with Popen(
                                [txRxScript, '-t', clientCaCrt, clientCrt, clientKey],
                                stdout=PIPE,
                                stderr=STDOUT,
                                bufsize=0 if MainDialog else -1,
                            ) as p:
                                if MainDialog:
                                    DisplayProgramBox(
                                        fileDescriptor=p.stdout.fileno(),
                                        text='ssl-client-transmit',
                                        clearScreen=True,
                                    )
                                else:
                                    while True:
                                        output = p.stdout.readline()
                                        if (len(output) == 0) and (p.poll() is not None):
                                            break
                                        if output:
                                            print(output.decode('utf-8').rstrip())
                                        else:
                                            time.sleep(0.5)

                                p.poll()
    finally:
        if MainDialog and (not args.cmdAuthSetupNonInteractive):
            ClearScreen()


###################################################################################################
# main
def main():
    global args
    global dockerBin
    global dockerComposeBin
    global dockerComposeYaml
    global kubeImported
    global opensslBin
    global orchMode
    global shuttingDown
    global yamlImported
    global dotenvImported

    # extract arguments from the command line
    # print (sys.argv[1:]);
    parser = argparse.ArgumentParser(
        description='Malcolm control script',
        add_help=False,
        usage=f'{ScriptName} <arguments>',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        dest='debug',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Verbose output",
    )
    parser.add_argument(
        '-f',
        '--file',
        required=False,
        dest='composeFile',
        metavar='<string>',
        type=str,
        default=os.getenv('MALCOLM_COMPOSE_FILE', os.path.join(MalcolmPath, 'docker-compose.yml')),
        help='docker-compose or kubeconfig YML file',
    )
    parser.add_argument(
        '-e',
        '--environment-dir',
        required=False,
        dest='configDir',
        metavar='<string>',
        type=str,
        default=os.getenv('MALCOLM_CONFIG_DIR', None),
        help="Directory containing Malcolm's .env files",
    )
    parser.add_argument(
        '-p',
        '--profile',
        required=False,
        dest='composeProfile',
        metavar='<string>',
        type=str,
        default=None,
        help='docker-compose profile to enable',
    )
    parser.add_argument(
        '-r',
        '--runtime',
        required=False,
        dest='runtimeBin',
        metavar='<string>',
        type=str,
        default=os.getenv('MALCOLM_CONTAINER_RUNTIME', ''),
        help='Container runtime binary (e.g., docker, podman)',
    )
    parser.add_argument(
        '--no-tmpdir-override',
        required=False,
        dest='noTmpDirOverride',
        type=str2bool,
        nargs='?',
        const=True,
        default=str2bool(os.getenv('MALCOLM_NO_TMPDIR_OVERRIDE', default='False')),
        help="Don't override TMPDIR for compose commands",
    )

    operationsGroup = parser.add_argument_group('Runtime Control')
    operationsGroup.add_argument(
        '--start',
        dest='cmdStart',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Start Malcolm",
    )
    operationsGroup.add_argument(
        '--restart',
        dest='cmdRestart',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Stop and restart Malcolm",
    )
    operationsGroup.add_argument(
        '--stop',
        dest='cmdStop',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Stop Malcolm",
    )
    operationsGroup.add_argument(
        '--wipe',
        dest='cmdWipe',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Stop Malcolm and delete all data",
    )

    kubernetesGroup = parser.add_argument_group('Kubernetes')
    kubernetesGroup.add_argument(
        '-n',
        '--namespace',
        required=False,
        dest='namespace',
        metavar='<string>',
        type=str,
        default=os.getenv('MALCOLM_NAMESPACE', 'malcolm'),
        help="Kubernetes namespace",
    )
    kubernetesGroup.add_argument(
        '--reclaim-persistent-volume',
        dest='deleteRetPerVol',
        action='store_true',
        help='Delete PersistentVolumes with Retain reclaim policy (default; only for "stop" operation with Kubernetes)',
    )
    kubernetesGroup.add_argument(
        '--no-reclaim-persistent-volume',
        dest='deleteRetPerVol',
        action='store_false',
        help='Do not delete PersistentVolumes with Retain reclaim policy (only for "stop" operation with Kubernetes)',
    )
    kubernetesGroup.set_defaults(deleteRetPerVol=True)

    authSetupGroup = parser.add_argument_group('Authentication Setup')
    authSetupGroup.add_argument(
        '--auth',
        dest='cmdAuthSetup',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Configure Malcolm authentication",
    )
    authSetupGroup.add_argument(
        '--auth-noninteractive',
        dest='cmdAuthSetupNonInteractive',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Configure Malcolm authentication (noninteractive using arguments provided)",
    )
    authSetupGroup.add_argument(
        '--auth-admin-username',
        dest='authUserName',
        required=False,
        metavar='<string>',
        type=str,
        default='',
        help='Administrator username (for --auth-noninteractive)',
    )
    authSetupGroup.add_argument(
        '--auth-admin-password-openssl',
        dest='authPasswordOpenssl',
        required=False,
        metavar='<string>',
        type=str,
        default='',
        help='Administrator password hash from "openssl -passwd -1" (for --auth-noninteractive)',
    )
    authSetupGroup.add_argument(
        '--auth-admin-password-htpasswd',
        dest='authPasswordHtpasswd',
        required=False,
        metavar='<string>',
        type=str,
        default='',
        help='Administrator password hash from "htpasswd -n -B username | cut -d: -f2" (for --auth-noninteractive)',
    )
    authSetupGroup.add_argument(
        '--auth-arkime-password',
        dest='authArkimePassword',
        required=False,
        metavar='<string>',
        type=str,
        default='Malcolm',
        help='Password hash secret for Arkime viewer cluster (for --auth-noninteractive)',
    )
    authSetupGroup.add_argument(
        '--auth-generate-webcerts',
        dest='authGenWebCerts',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="(Re)generate self-signed certificates for HTTPS access (for --auth-noninteractive)",
    )
    authSetupGroup.add_argument(
        '--auth-generate-fwcerts',
        dest='authGenFwCerts',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="(Re)generate self-signed certificates for a remote log forwarder",
    )
    authSetupGroup.add_argument(
        '--auth-generate-netbox-passwords',
        dest='authGenNetBoxPasswords',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="(Re)generate internal passwords for NetBox",
    )

    logsAndStatusGroup = parser.add_argument_group('Logs and Status')
    logsAndStatusGroup.add_argument(
        '-l',
        '--logs',
        dest='cmdLogs',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Tail Malcolm logs",
    )
    logsAndStatusGroup.add_argument(
        '--lines',
        dest='logLineCount',
        type=posInt,
        nargs='?',
        const=False,
        default=None,
        help='Number of log lines to output. Outputs all lines by default (only for logs operation)',
    )
    logsAndStatusGroup.add_argument(
        '--status',
        dest='cmdStatus',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Display status of Malcolm components",
    )
    logsAndStatusGroup.add_argument(
        '--urls',
        dest='cmdPrintURLs',
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Display Malcolm URLs",
    )
    logsAndStatusGroup.add_argument(
        '-s',
        '--service',
        required=False,
        dest='service',
        metavar='<string>',
        nargs='*',
        type=str,
        default=None,
        help='docker-compose service(s) (only applies to some operations)',
    )

    netboxGroup = parser.add_argument_group('NetBox Backup and Restore')
    netboxGroup.add_argument(
        '--netbox-backup',
        dest='netboxBackupFile',
        required=False,
        metavar='<string>',
        type=str,
        default=None,
        help='Filename to which to back up NetBox configuration database',
    )
    netboxGroup.add_argument(
        '--netbox-restore',
        dest='netboxRestoreFile',
        required=False,
        metavar='<string>',
        type=str,
        default=None,
        help='Filename from which to restore NetBox configuration database',
    )

    try:
        parser.error = parser.exit
        args = parser.parse_args()
    except SystemExit as e:
        eprint(f'Invalid arguments: {e}')
        parser.print_help()
        exit(2)

    if args.debug:
        eprint(os.path.join(ScriptPath, ScriptName))
        eprint(f"Arguments: {sys.argv[1:]}")
        eprint(f"Arguments: {args}")
        eprint("Malcolm path:", MalcolmPath)
    else:
        sys.tracebacklimit = 0

    # handle sigint and sigterm for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    yamlImported = YAMLDynamic(debug=args.debug)
    if args.debug:
        eprint(f"Imported yaml: {yamlImported}")
    if not yamlImported:
        exit(2)

    dotenvImported = DotEnvDynamic(debug=args.debug)
    if args.debug:
        eprint(f"Imported dotenv: {dotenvImported}")
    if not dotenvImported:
        exit(2)

    if not ((orchMode := DetermineYamlFileFormat(args.composeFile)) and (orchMode in OrchestrationFrameworksSupported)):
        raise Exception(f'{args.composeFile} must be a docker-compose or kubeconfig YAML file')

    with pushd(MalcolmPath):
        # don't run this as root
        if (pyPlatform != PLATFORM_WINDOWS) and (
            (os.getuid() == 0) or (os.geteuid() == 0) or (getpass.getuser() == 'root')
        ):
            raise Exception(f'{ScriptName} should not be run as root')

        # if .env directory is unspecified, use the default ./config directory
        for firstLoop in (True, False):
            if (args.configDir is None) or (not os.path.isdir(args.configDir)):
                if firstLoop:
                    if args.configDir is None:
                        args.configDir = os.path.join(MalcolmPath, 'config')
                    try:
                        os.makedirs(args.configDir)
                    except OSError as exc:
                        if (exc.errno == errno.EEXIST) and os.path.isdir(args.configDir):
                            pass
                        else:
                            raise
                else:
                    raise Exception("Could not determine configuration directory containing Malcolm's .env files")

        # create local temporary directory for docker-compose because we may have noexec on /tmp
        try:
            os.makedirs(MalcolmTmpPath)
        except OSError as exc:
            if (exc.errno == errno.EEXIST) and os.path.isdir(MalcolmTmpPath):
                pass
            else:
                raise

        # docker-compose use local temporary path
        osEnv = os.environ.copy()
        if not args.noTmpDirOverride:
            osEnv['TMPDIR'] = MalcolmTmpPath

        if orchMode is OrchestrationFramework.DOCKER_COMPOSE:
            # identify runtime engine
            runtimeBinSrc = ''
            if args.runtimeBin:
                dockerBin = args.runtimeBin
                runtimeBinSrc = 'specified'
            else:
                processEnvFile = os.path.join(args.configDir, 'process.env')
                try:
                    if os.path.isfile(processEnvFile):
                        dockerBin = dotenvImported.get_key(processEnvFile, CONTAINER_RUNTIME_KEY)
                        runtimeBinSrc = os.path.basename(processEnvFile)
                    else:
                        runtimeBinSrc = 'process.env not found'
                except Exception as e:
                    runtimeBinSrc = f'exception ({e})'
            if not dockerBin:
                dockerBin = 'docker.exe' if ((pyPlatform == PLATFORM_WINDOWS) and which('docker.exe')) else 'docker'
                runtimeBinSrc = 'default'
            if args.debug:
                eprint(f"Container runtime ({runtimeBinSrc}): {dockerBin}")

            # make sure docker and docker compose are available
            err, out = run_process([dockerBin, 'info'], debug=args.debug)
            if err != 0:
                raise Exception(f'{ScriptName} requires docker, please run install.py')
            # first check if compose is available as a docker plugin
            dockerComposeBin = (dockerBin, 'compose')
            err, out = run_process(
                [dockerComposeBin, '--profile', PROFILE_MALCOLM, '-f', args.composeFile, 'version'],
                env=osEnv,
                debug=args.debug,
            )
            if err != 0:
                if (pyPlatform == PLATFORM_WINDOWS) and which('docker-compose.exe'):
                    dockerComposeBin = 'docker-compose.exe'
                elif which('docker-compose'):
                    dockerComposeBin = 'docker-compose'
                elif os.path.isfile('/usr/libexec/docker/cli-plugins/docker-compose'):
                    dockerComposeBin = '/usr/libexec/docker/cli-plugins/docker-compose'
                elif os.path.isfile('/usr/local/opt/docker-compose/bin/docker-compose'):
                    dockerComposeBin = '/usr/local/opt/docker-compose/bin/docker-compose'
                elif os.path.isfile('/usr/local/bin/docker-compose'):
                    dockerComposeBin = '/usr/local/bin/docker-compose'
                elif os.path.isfile('/usr/bin/docker-compose'):
                    dockerComposeBin = '/usr/bin/docker-compose'
                else:
                    dockerComposeBin = 'docker-compose'
                err, out = run_process(
                    [dockerComposeBin, '--profile', PROFILE_MALCOLM, '-f', args.composeFile, 'version'],
                    env=osEnv,
                    debug=args.debug,
                )
            if err != 0:
                raise Exception(f'{ScriptName} requires docker-compose, please run install.py')

            # load compose file YAML (used to find some volume bind mount locations)
            with open(args.composeFile, 'r') as cf:
                dockerComposeYaml = yamlImported.YAML(typ='safe', pure=True).load(cf)

        elif orchMode is OrchestrationFramework.KUBERNETES:
            kubeImported = KubernetesDynamic(debug=args.debug)
            if args.debug:
                eprint(f"Imported kubernetes: {kubeImported}")
            if kubeImported:
                kubeImported.config.load_kube_config(args.composeFile)
            else:
                raise Exception(
                    f'{ScriptName} requires the official Python client library for kubernetes for {orchMode} mode'
                )

        # identify running profile
        runProfileSrc = ''
        if not args.composeProfile:
            profileEnvFile = os.path.join(args.configDir, 'process.env')
            try:
                if os.path.isfile(profileEnvFile):
                    args.composeProfile = dotenvImported.get_key(profileEnvFile, PROFILE_KEY)
                    runProfileSrc = os.path.basename(profileEnvFile)
                elif args.debug:
                    runProfileSrc = 'process.env not found'
            except Exception as e:
                runProfileSrc = f'exception ({e})'
        elif args.debug:
            runProfileSrc = 'specified'
        if not args.composeProfile:
            args.composeProfile = PROFILE_MALCOLM
            runProfileSrc = 'default'
        if args.debug:
            eprint(f"Run profile ({runProfileSrc}): {args.composeProfile}")

        # identify openssl binary
        opensslBin = 'openssl.exe' if ((pyPlatform == PLATFORM_WINDOWS) and which('openssl.exe')) else 'openssl'

        # if executed via a symlink, figure out what was intended via the symlink name
        if os.path.islink(os.path.join(ScriptPath, ScriptName)):
            if ScriptName == "logs":
                args.cmdLogs = True
            elif ScriptName == "status":
                args.cmdStatus = True
            elif ScriptName == "start":
                args.cmdStart = True
            elif ScriptName == "restart":
                args.cmdRestart = True
            elif ScriptName == "stop":
                args.cmdStop = True
            elif ScriptName == "wipe":
                args.cmdWipe = True
            elif ScriptName.startswith("auth"):
                args.cmdAuthSetup = True
            elif ScriptName == "netbox-backup":
                args.netboxBackupFile = ""
            elif ScriptName == "netbox-restore" and (
                (not args.netboxRestoreFile) or (not os.path.isfile(args.netboxRestoreFile))
            ):
                raise Exception('NetBox configuration database file must be specified with --netbox-restore')

        # the compose file references various .env files in just about every operation this script does,
        # so make sure they exist right off the bat
        checkEnvFilesAndValues()

        # stop Malcolm (and wipe data if requestsed)
        if args.cmdRestart or args.cmdStop or args.cmdWipe:
            stop(wipe=args.cmdWipe)

        # configure Malcolm authentication
        if args.cmdAuthSetup or args.cmdAuthSetupNonInteractive:
            authSetup()

        # start Malcolm
        if args.cmdStart or args.cmdRestart:
            start()

        # tail Malcolm logs
        if args.cmdStart or args.cmdRestart or args.cmdLogs:
            logs()

        # display Malcolm status
        if args.cmdStatus:
            status()

        # display Malcolm URLS
        if args.cmdPrintURLs:
            printURLs()

        # backup NetBox files
        if args.netboxBackupFile is not None:
            print(f"NetBox configuration database saved to {netboxBackup(args.netboxBackupFile)}")

        # restore NetBox files
        if args.netboxRestoreFile is not None:
            netboxRestore(args.netboxRestoreFile)


if __name__ == '__main__':
    main()
    if coloramaImported:
        print(Style.RESET_ALL)
