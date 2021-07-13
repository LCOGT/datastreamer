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

```json
{
    site: (string) the sitecode that specifies which subscribers will recieve this message,
    topic: (string) the type of data (ie. weather, status, calendar), used by the recieving clients,
    data: (json) the primary content
}
```

## Receiving Data

Clients may subscribe to datastreams by connecting to the websocket at `datastream.photonranch.org/<stage>?site=<site>`.
The stage can be dev or prod, and the site abbreviation (ie. mrc) should be included as a query string parameter.
