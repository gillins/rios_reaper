#!/usr/bin/env python3

"""
Test harness for testing rios_reaper
"""

import os
import time
import json
import argparse
import subprocess
import boto3
import botocore


DFLT_STARTWAIT = 10  # seconds
DFLT_AWSREGION = 'us-west-2'

def getCmdArgs():
    """
    """
    p = argparse.ArgumentParser()
    p.add_argument('-m', '--mode', choices=['lambda', 'deployed'],
        default='lambda', help="Which type of test we are running. (default=%(default)s)")
    p.add_argument("--wait", default=DFLT_STARTWAIT, type=int,
        help="Number of seconds to wait for api/lambda before the child " +
            "process is assumed to be ready for testing. (default=%(default)s)")
    p.add_argument('--awsregion', default=DFLT_AWSREGION,
        help="AWS Region to use. (default=%(default)s)")
    p.add_argument('--skipdeploy', default=False, action="store_true",
        help="For --mode deployed, skip the deploying stage")

    cmdargs = p.parse_args()
    return cmdargs


def main():
    """
    Main function
    """
    if 'AWS_PROFILE' not in os.environ:
        raise SystemExit('AWS_PROFILE env var not set')

    if 'VPC_ID' not in os.environ:
        raise SystemExit('Must set VPC_ID env var to id of the VPC you wish to deploy to')

    if 'SUBNET_IDS' not in os.environ:
        raise SystemExit('Must set SUBNET_IDS env var to a comma separated list of subnet ids')

    parameter_overrides = ['--parameter-overrides', 'VPCId={}'.format(os.environ['VPC_ID']),
        '--parameter-overrides', 'SubnetIds={}'.format(os.environ['SUBNET_IDS'])]

    # Get: Lambda functions containers initialization failed because of Layers require credentials to download the layers locally.
    # because of the danger of messing up the AWS_ACCESS_KEY_ID/AWS_PROFILE and having them not match
    # We set the tokens ourselves - AWS SAM requires this
    if 'AWS_ACCESS_KEY_ID' in os.environ:
        raise SystemExit('Do not set aws configure export-credentials before running this script')

    cmdargs = getCmdArgs()

    # now set the temproray tokens so the child process (SAM) can pick this up
    session = boto3.Session()
    credentials = session.get_credentials()
    os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
    os.environ['AWS_SESSION_TOKEN'] = credentials.token
    
    # ensure built first
    if not cmdargs.skipdeploy:
        cmd = ['sam', 'build']
        subprocess.check_call(cmd)

    cmd = None
    lambda_client = None
    fnName = 'RIOS_Reaper'

    if cmdargs.mode == 'lambda':
        cmd = ['sam', 'local', 'start-lambda'] + parameter_overrides
        lambda_client = boto3.client('lambda',
            region_name=cmdargs.awsregion,
            endpoint_url="http://127.0.0.1:3001",
            use_ssl=False,
            verify=False,
            config=botocore.client.Config(
                signature_version=botocore.UNSIGNED,
                read_timeout=30,
                retries={'max_attempts': 0},
                )
        )
    else:
        # deployed Lambda endpoint first
        if not cmdargs.skipdeploy:
            cmd = ['sam', 'deploy', '--capabilities', 'CAPABILITY_NAMED_IAM'] + parameter_overrides
            subprocess.check_call(cmd)
            # no need to run anything later
            cmd = None
            time.sleep(30)  # to ensure new lambdas are called

        lambda_client = boto3.client('lambda',
            region_name=cmdargs.awsregion)
        
    proc = None
    if cmd is not None:
        print(cmd)
        proc = subprocess.Popen(cmd)
        time.sleep(cmdargs.wait)
        if proc.poll() is not None:
            raise SystemExit("Child exited")

    try:    
        payload = {'event': 'sdwedwewq'}
        out = lambda_client.invoke(FunctionName=fnName, 
            Payload=json.dumps(payload))
        payload = json.loads(out["Payload"].read())
        print(payload)
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait()

if __name__ == '__main__':
    main()
