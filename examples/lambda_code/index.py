"""
Audit API Lambda Function
Receives audit events via API Gateway and stores them in DynamoDB
"""

import json
import os
import time
import uuid
import boto3
from datetime import datetime

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

# Environment variables
TABLE_NAME = os.environ.get('TABLE_NAME', 'audit-events')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# DynamoDB table
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    """
    Lambda handler function for processing audit events
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract request details
        http_method = event.get('httpMethod', 'UNKNOWN')
        path = event.get('path', '/')
        body = event.get('body', '{}')
        
        # Parse request body
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return create_response(400, {'error': 'Invalid JSON in request body'})
        else:
            request_data = {}
        
        # Route based on HTTP method and path
        if http_method == 'POST' and path == '/audit':
            return handle_audit_event(request_data, event)
        elif http_method == 'GET' and path == '/health':
            return handle_health_check()
        elif http_method == 'GET' and path.startswith('/audit/'):
            event_id = path.split('/')[-1]
            return handle_get_audit_event(event_id)
        else:
            return create_response(404, {'error': 'Not found'})
            
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return create_response(500, {'error': 'Internal server error', 'message': str(e)})


def handle_audit_event(data, event):
    """
    Handle incoming audit event
    
    Args:
        data: Audit event data
        event: Original API Gateway event
        
    Returns:
        API Gateway response
    """
    # Generate event ID
    event_id = str(uuid.uuid4())
    timestamp = int(time.time())
    
    # Extract metadata
    source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
    user_agent = event.get('requestContext', {}).get('identity', {}).get('userAgent', 'unknown')
    
    # Create audit record
    audit_record = {
        'eventId': event_id,
        'timestamp': timestamp,
        'eventType': data.get('eventType', 'UNKNOWN'),
        'userId': data.get('userId'),
        'action': data.get('action'),
        'resource': data.get('resource'),
        'result': data.get('result', 'SUCCESS'),
        'metadata': {
            'sourceIp': source_ip,
            'userAgent': user_agent,
            'environment': ENVIRONMENT,
            'additionalData': data.get('additionalData', {})
        },
        'ttl': timestamp + (90 * 24 * 60 * 60)  # 90 days retention
    }
    
    # Store in DynamoDB
    try:
        table.put_item(Item=audit_record)
        print(f"Audit event stored: {event_id}")
    except Exception as e:
        print(f"Error storing audit event: {str(e)}")
        return create_response(500, {'error': 'Failed to store audit event'})
    
    # Return success response
    return create_response(201, {
        'eventId': event_id,
        'message': 'Audit event recorded successfully',
        'timestamp': timestamp
    })


def handle_health_check():
    """
    Handle health check request
    
    Returns:
        API Gateway response
    """
    return create_response(200, {
        'status': 'healthy',
        'timestamp': int(time.time()),
        'environment': ENVIRONMENT,
        'version': '1.0.0'
    })


def handle_get_audit_event(event_id):
    """
    Retrieve audit event by ID
    
    Args:
        event_id: Event ID to retrieve
        
    Returns:
        API Gateway response
    """
    try:
        response = table.get_item(Key={'eventId': event_id})
        
        if 'Item' in response:
            return create_response(200, response['Item'])
        else:
            return create_response(404, {'error': 'Event not found'})
            
    except Exception as e:
        print(f"Error retrieving audit event: {str(e)}")
        return create_response(500, {'error': 'Failed to retrieve audit event'})


def create_response(status_code, body):
    """
    Create API Gateway response
    
    Args:
        status_code: HTTP status code
        body: Response body (dict)
        
    Returns:
        API Gateway response object
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body)
    }
