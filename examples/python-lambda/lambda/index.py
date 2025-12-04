import json
import logging
from datetime import datetime

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Simple Lambda handler for API Gateway
    
    Receives: API Gateway event
    Returns: HTTP response with JSON
    """
    
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Get request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body_data = json.loads(body)
        else:
            body_data = body
        
        logger.info(f"Request data: {body_data}")
        
        # Process the request
        response_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'Request received and processed',
            'received_data': body_data,
            'http_method': event.get('httpMethod'),
            'path': event.get('path'),
            'status': 'success'
        }
        
        logger.info(f"Response: {response_data}")
        
        # Return success
        return {
            'statusCode': 200,
            'body': json.dumps(response_data),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
