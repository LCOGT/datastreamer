import json, decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError


#=========================================#
#=======    Utility Functions     ========#
#=========================================#


def get_response(status_code, body):
    if not isinstance(body, str):
        body = json.dumps(body,cls=DecimalEncoder)
    return {
        "statusCode": status_code, 
        "headers": {
            # Required for CORS support to work
            "Access-Control-Allow-Origin": "*",
            # Required for cookies, authorization headers with HTTPS
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "*",
        },
        "body": body
    }

def get_body(event):
    try:
        return json.loads(event.get("body", ""))
    except:
        print("event body could not be JSON decoded.")
        return {}

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)
        

def simple():
    return "hello"