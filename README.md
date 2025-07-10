# rios_reaper

This Lambda collects up EC2 instances that have not been terminated by RIOS 
for whatever reason.

## Installation

AWS SAM needs to be installed first.

We recommend that SAM is installed into a Python virtual env as shown below:
```
python3 -m venv .sam_venv
source .sam_venv/bin/activate
wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-arm64.zip
unzip aws-sam-cli-linux-arm64.zip
cd aws-sam-cli-src
pip install .
```
You will need to activate this virtual env each time you wish to work on `rios_reaper`.

## Development 

Add code to `reaper/app.py` as required.

## Environment Variables

The following env vars must be set in your environment before running `test-deploy.py`:

1. AWS_PROFILE - the name of the profile you are running under, or `default`
2. VPC_ID - the id of the VPC you want the Lambda to run under
3. SUBNET_IDS - a comma separated list of subnet ids the Lambda is to run within

## Local testing

```
./test-deploy.py
```

Will start up the lambda locally and try to run it

## Deploying

```
./test-deploy -m deployed
```
