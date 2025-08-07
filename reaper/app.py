"""
Module that implements the RIOS Reaper
"""

import os
import datetime
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools import Logger
from aws_lambda_powertools import Tracer
from aws_lambda_powertools import Metrics
import boto3

tracer = Tracer()
logger = Logger()
metrics = Metrics(namespace="Powertools")

def findIdleInstances(tagKey, periodLen=3600, numPeriods=12, idleThreshold=1):
    """
    Find idle instances with the given tag. CPU Utilization is averaged over
    periods of the specified length (seconds), for the given number of periods.
    An instance is defined as idle if all periods have CPU utilization less
    than the given threshold (percentage).

    Return a list of instanceID strings for all idle instances.
    """
    ec2client = boto3.client('ec2')
    cloudwatchClient = boto3.client('cloudwatch')

    instanceIdList = findInstancesByTag(ec2client, tagKey)

    idleInstanceList = []
    for instanceId in instanceIdList:
        cpuUtilList = getCPUUtilization(cloudwatchClient, instanceId,
            periodLen, numPeriods)
        # We need to have the full set of periods
        if len(cpuUtilList) == numPeriods:
            isIdle = (max(cpuUtilList) < idleThreshold)
            if isIdle:
                idleInstanceList.append(instanceId)

    return idleInstanceList


def findInstancesByTag(ec2client, tagKey):
    """
    Find all instances which have the given tag (regardless of its value)
    """
    # A filter for the tag key, regardless of its value
    tagFilter = {'Name': 'tag-key', 'Values': [tagKey]}
    # Find matching instances
    response = ec2client.describe_instances(Filters=[tagFilter])
    # Extract the instanceId strings
    reservationsList = response['Reservations']

    instanceIdList = []
    for res in reservationsList:
        instList = res['Instances']
        instanceIdList.extend([inst['InstanceId'] for inst in instList])

    return instanceIdList


def getCPUUtilization(cloudwatchClient, instanceId, periodLen, numPeriods):
    """
    Get the CPU Utilization for the given instanceID. Percentage is averaged
    over the given number of periods of length periodLen (seconds).

    Return a list of average values (one for each period)
    """
    # Start and end times
    endTime = datetime.datetime.now()
    totalSeconds = periodLen * numPeriods
    timeDelta = datetime.timedelta(seconds=totalSeconds)
    startTime = endTime - timeDelta

    response = cloudwatchClient.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instanceId}],
        StartTime=startTime,
        EndTime=endTime,
        Period=periodLen,
        Statistics=["Average"]
    )

    hourlyAvgCpuPcnt = [d['Average'] for d in response['Datapoints']]
    return hourlyAvgCpuPcnt


def findStoppedClustersByTag(ecs_client, tag_key):
    """
    Return a list of clusters with with given tag key
    and zero running tasks
    """
    matching_clusters = []
    cluster_arns = []
    paginator = ecs_client.get_paginator('list_clusters')
    for page in paginator.paginate():
        cluster_arns.extend(page['clusterArns'])

    if not cluster_arns:
        return []

    # 2. Describe clusters to get tags (in batches of up to 100)
    for i in range(0, len(cluster_arns), 100):
        batch_arns = cluster_arns[i:i + 100]
        response = ecs_client.describe_clusters(
            clusters=batch_arns,
            include=['TAGS']
        )
        
        # 3. Filter based on tags
        for cluster in response['clusters']:
            if cluster.get('runningTasksCount') == 0 and 'tags' in cluster:
                for tag in cluster['tags']:
                    if tag.get('key') == tag_key:
                        matching_clusters.append(cluster['clusterName'])
                        break  # Found the tag, move to the next cluster

    return matching_clusters


def findStoppedClusters(tag_key):
    ecs_client = boto3.client('ecs')

    matching_clusters = findStoppedClustersByTag(ecs_client, tag_key)

    return matching_clusters    


# Enrich logging with contextual information from Lambda
@logger.inject_lambda_context
# Adding tracer
# See: https://awslabs.github.io/aws-lambda-powertools-python/latest/core/tracer/
@tracer.capture_lambda_handler
# ensures metrics are flushed upon request completion/failure and capturing ColdStart metric
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logger.warning(f"Received event: {event}")
    idleInstanceList = findIdleInstances('RIOS-computeworkerinstance')
    stoppedClusters = findStoppedClusters('RIOS-cluster')

    logger.warning("Idle instances: %s", ','.join(idleInstanceList))
    logger.warning("Stopped Clusters: %s", ','.join(stoppedClusters))

    topic_arn = os.getenv('SNS_TOPIC_ARN')
    if topic_arn != 'SNSTopic':
        # weirdly the SNS_TOPIC_ARN env var gets set to SNSTopic
        # instead of an ARN in lambda local mode as the SNS Topic
        # has not been created yet.
        sns = boto3.client('sns')
        if len(idleInstanceList) == 0:
            msg = 'No Idle Instances detected'
        else:
            msg = 'The following idle instances were found: ' + ','.join(idleInstanceList)

        if len(stoppedClusters) == 0:
            msg += '\nNo Stopped Clusters found'
        else:
            msg += '\nThe following stopped clusters were found: ' + ','.join(stoppedClusters)
        sns.publish(TopicArn=topic_arn, Message=msg)

    return {'idle': idleInstanceList, 'stopped': stoppedClusters}
