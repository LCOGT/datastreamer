# datastreamer

This service is used by photon ranch to stream data to browser clients in real time. 


## Usage

This service is developed using the serverless framework. 

To deploy the service, make sure you have aws credentials configured on your machine. Then run:

`> serverless deploy`

## Architecture

Clients subscribe by connecting to a websocket and specifying the type of data they want to receive (for now, subscriptions are per site). 
Incoming data is read from a queue, and sent to the relevant subscribers.
In order to handle potentially large numbers of subscribers, sending the data is a two step process. 
The list of subscribers is split into managable chuncks (~10 at a time). Each of these sub-lists is sent to an outgoing queue, 
along with the payload, and workers pull from this queue to send to the websocket connections. 

## Sending Data

Services may stream data to subscribers by sending it to the sqs queue `datastreamIncomingQueue-<stage>` where stage is either dev or prod.
The body of the queue payload should be structured as follows: 

```
{
    site: (string) the sitecode that specifies which subscribers will recieve this message,
    topic: (string) the type of data (ie. weather, status, calendar), used by the recieving clients,
    data: (json) the primary content
}
```

## Receiving Data

Clients may subscribe to datastreams by connecting to the websocket at `datastream.photonranch.org/<stage>?site=<site>`.
The stage can be dev or prod, and the site abbreviation (ie. mrc) should be included as a query string parameter.


## Example: Sending data in python

Prequisites:

- datastreamer is deployed and running in a stage called dev.
- aws credentials with the permission to write to sqs queues is setup on your local machine

If the conditions above are satisfied, the following should send a message through datasteamer to all clients connected and listtening for messages to site "tst":

```python
import boto3
import botocore.exceptions
import json

# Payload data
SITE = "tst"
TOPIC = "testing"
MESSAGE = json.dumps({ "text": "hello, site tst" })  # any string

# This is the SQS queue we send messages to.
STAGE = "dev"
DATASTREAMER_QUEUE_NAME = f"datastreamIncomingQueue-{STAGE}"

# Boto3 requires the queue url, which we can get using its name
def get_queue_url(queueName: str) -> str:
    sqs_client = boto3.client("sqs", region_name="us-east-1")
    response = sqs_client.get_queue_url(
        QueueName=queueName,
    )
    return response["QueueUrl"]

# This method sends a message to the datastreamer SQS queue 
def send_to_datastream(topic: str, site: str, data: str):
    sqs = boto3.client('sqs')
    queue_url = get_queue_url(DATASTREAMER_QUEUE_NAME)
    payload = {
        "topic": topic,
        "site": site,
        "data": data,
    }
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload),
        )
        print('Message sent succesfully')
    except botocore.exceptions.ClientError as error:
        print('Message failed to send', error)

# Send the message
send_to_datastream(TOPIC, SITE, MESSAGE)

```
