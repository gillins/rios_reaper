"""
Module that implements the RIOS Reaper
"""


from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools import Logger
from aws_lambda_powertools import Tracer
from aws_lambda_powertools import Metrics
import boto3

tracer = Tracer()
logger = Logger()
metrics = Metrics(namespace="Powertools")

# Enrich logging with contextual information from Lambda
@logger.inject_lambda_context
# Adding tracer
# See: https://awslabs.github.io/aws-lambda-powertools-python/latest/core/tracer/
@tracer.capture_lambda_handler
# ensures metrics are flushed upon request completion/failure and capturing ColdStart metric
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logger.warning(f"Received event: {event}")

    return {'message': 'done'}
