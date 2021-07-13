import json
import os
import decimal
import logging
import time
import datetime
import boto3

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from helpers import get_response
from helpers import get_body
from helpers import DecimalEncoder

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

subscribers_table = dynamodb.Table(os.getenv('CONNECTIONS_TABLE'))

WSS_URL = os.getenv('WSS_URL')
INCOMING_QUEUE_URL = os.getenv('INCOMING_QUEUE_URL')
OUTGOING_QUEUE_URL = os.getenv('OUTGOING_QUEUE_URL')


def connection_manager(event, context):
    """
    Handles connecting and disconnecting for the Websocket
    """

    connection_id = event["requestContext"].get("connectionId")

    # Connection request
    if event["requestContext"]["eventType"] == "CONNECT":
        logger.info("Connect requested")
        # Check that the subscriber specified which site they are subscribed to.
        try:
            site = event["queryStringParameters"]["site"]
        except:
            return get_response(400, "No site specified")
        # Add connection_id to the database
        add_connection(connection_id, site)
        return get_response(200, "Connect successful.")

    # Disconnection request
    elif event["requestContext"]["eventType"] in ("DISCONNECT", "CLOSE"):
        logger.info("Disconnect requested")
        # Remove the connection_id from the database
        subscribers_table.delete_item(Key={"PK": connection_id}) 
        remove_connection(connection_id)
        return get_response(200, "Disconnect successful.")

    # Unknown request
    else:
        logger.error("Connection manager received unrecognized eventType '{}'")
        return get_response(500, "Unrecognized eventType.")


def update_subscriber_site(event, context):
    '''
    Change the site associated with a connectionId. This connection will only
    be sent updates for that site. 
    '''
    connection_id = event['requestContext'].get('connectionId')
    body = get_body(event)

    try:
        site = body.get('site')
    except:
        return get_response(400, 'Missing the subscribers new site')

    # Update the connections table entry
    add_connection(connection_id, site)

    return get_response(200, f"Successfully subscribed to {site}.")

#=========================================#
#======    Websocket Connections   =======#
#=========================================#

def add_connection(connection_id, site):
    """ Save the id of new connections subscribing to status at a site """
    subscriber = {
        "PK": connection_id,
        "site": site,
        "timestamp": decimal.Decimal(int(time.time())),
        "expiration": decimal.Decimal(int(time.time() + 86400)),  # connection expires in 24hrs
        "timestamp_readable": datetime.datetime.now().isoformat()
    }
    table_response = subscribers_table.put_item(Item=subscriber)
    return table_response


def remove_connection(connection_id):
    """ Remove a client from the list of subscribers, usually when the websocket closes. """
    table_response = subscribers_table.delete_item(Key={"PK": connection_id}) 
    return table_response


def get_connection_ids(site, topic):
    """ Get a list of websocket connections subscribed to the given site """
    subscribers_query = subscribers_table.scan(
        ProjectionExpression="PK, site",
        FilterExpression=Key('site').eq(site)
    )
    site_subscribers = subscribers_query.get("Items", [])
    connection_ids = [c["PK"] for c in site_subscribers]
    return connection_ids


def send_to_connection(connection_id, data):
    gatewayapi = boto3.client("apigatewaymanagementapi", endpoint_url=WSS_URL)
    dataToSend = json.dumps(data, cls=DecimalEncoder).encode('utf-8')
    post_response = gatewayapi.post_to_connection(
        ConnectionId=connection_id,
        Data=dataToSend
    )
    return post_response


#=========================================#
#=======       Queue Handlers      =======#
#=========================================#

def incoming_queue_handler(event, context):
    """    """
    for record in event['Records']:
        logger.info(f'Message body: {record["body"]}')

        # Parse the queue message content
        try:
            payload = json.loads(record["body"])
            site = json.loads(payload["site"])
            topic = json.loads(payload["topic"])
            data = json.loads(payload["data"])
        except KeyError as e:
            logger.error(f"KeyError when parsing incoming queue contents. {e}")

        # get connections
        connection_ids = get_connection_ids(site, topic)

        # Break the list of connection IDs into a list of lists of connection IDs 
        # ie. from [1,2,3,4,5] to [[1,2], [3,4], [5]] using a chunk size of 2
        # This is so lambda functions sending data to clients can run in parallel with managable loads.
        chunk_size = 10
        chunked_connection_ids = [connection_ids[i:i+chunk_size] for i in range(0,len(connection_ids),chunk_size)]

        # construct payload and send to outgoing queue
        for connection_list in chunked_connection_ids:
            # Send to dispatch queue
            message_body = {
                "connections": connection_list,
                "message": {
                    "site": site,
                    "topic": topic,
                    "data": data
                }
            }
            sqs.send_message(
                QueueUrl=OUTGOING_QUEUE_URL,
                MessageBody=json.dumps(message_body),
            )


def outgoing_queue_handler(event, context):
    """  """
    for record in event['Records']:
        logger.info(f'Message body: {record["body"]}')

        # Parse the queue to get connections and content to send
        try:
            payload = json.loads(record["body"])
            connections = json.loads(payload["connections"])
            message = json.loads(payload["message"])
        except KeyError as e:
            logger.error(f"KeyError when parsing queue contents. {e}")

        # Send to each connected client
        for connection_id in connections:
            try: 
                send_to_connection(connection_id, message)
            except Exception as e:
                print(f"Could not send to connection {connection_id}")
                print(e)
