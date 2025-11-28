"""
Audit Event Receiver
Logs audit events to CloudWatch
"""

import json
import os
import time
from datetime import datetime


# Environment variables
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


def handler(event, context):
    """
    Lambda handler for receiving and logging audit events
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    print(f"Environment: {ENVIRONMENT}")
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract request details
        http_method = event.get('httpMethod', 'UNKNOWN')
        path = event.get('path', '/')
        source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        user_agent = event.get('requestContext', {}).get('identity', {}).get('userAgent', 'unknown')
        request_id = event.get('requestContext', {}).get('requestId', 'unknown')
        
        # Parse request body
        body = event.get('body', '{}')
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return create_response(400, {
                    'error': 'Invalid JSON',
                    'message': 'Request body must be valid JSON'
                })
        else:
            request_data = {}
        
        # Route to handlers
        if http_method == 'POST' and path == '/audit':
            return handle_audit_event(request_data, source_ip, user_agent, request_id)
        elif http_method == 'GET' and path == '/health':
            return handle_health_check()
        elif http_method == 'GET' and path == '/':
            return handle_root()
        else:
            return create_response(404, {
                'error': 'Not found',
                'message': f'Endpoint {http_method} {path} not found'
            })
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return create_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })


def handle_audit_event(data, source_ip, user_agent, request_id):
    """
    Handle audit event and log to CloudWatch
    
    Args:
        data: Audit event data
        source_ip: Source IP address
        user_agent: User agent string
        request_id: API Gateway request ID
        
    Returns:
        API Gateway response
    """
    # Validate required fields
    required_fields = ['eventType', 'userId', 'action']
    missing_fields = [field for field in required_fields if not data.get(field)]
    
    if missing_fields:
        return create_response(400, {
            'error': 'Missing required fields',
            'missing': missing_fields,
            'required': required_fields
        })
    
    # Create structured audit log entry
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    audit_log = {
        'timestamp': timestamp,
        'eventType': data.get('eventType'),
        'userId': data.get('userId'),
        'action': data.get('action'),
        'resource': data.get('resource', 'N/A'),
        'result': data.get('result', 'SUCCESS'),
        'metadata': {
            'sourceIp': source_ip,
            'userAgent': user_agent,
            'requestId': request_id,
            'environment': ENVIRONMENT,
            'additionalData': data.get('additionalData', {})
        }
    }
    
    # Log the audit event (this goes to CloudWatch)
    log_audit_event(audit_log)
    
    # Return success response
    return create_response(201, {
        'message': 'Audit event logged successfully',
        'timestamp': timestamp,
        'requestId': request_id
    })


def handle_health_check():
    """
    Handle health check request
    
    Returns:
        API Gateway response
    """
    return create_response(200, {
        'status': 'healthy',
        'service': 'audit-api',
        'environment': ENVIRONMENT,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '1.0.0'
    })


def handle_root():
    """
    Handle root endpoint request
    
    Returns:
        API Gateway response
    """
    return create_response(200, {
        'message': 'Audit API - CloudWatch Logging',
        'version': '1.0.0',
        'endpoints': {
            'POST /audit': 'Submit audit event',
            'GET /health': 'Health check',
            'GET /': 'API information'
        },
        'documentation': 'https://github.com/your-org/api-gateway-lambda-module'
    })


def log_audit_event(audit_log):
    """
    Log audit event to CloudWatch with structured format
    
    Args:
        audit_log: Structured audit log entry
    """
    # Log as JSON for easy parsing in CloudWatch Insights
    log_entry = {
        'level': 'INFO',
        'type': 'AUDIT_EVENT',
        'data': audit_log
    }
    
    print(f"AUDIT_EVENT: {json.dumps(log_entry)}")
    
    # Also log in human-readable format
    print(f"[AUDIT] {audit_log['eventType']} by {audit_log['userId']}: "
          f"{audit_log['action']} on {audit_log['resource']} -> {audit_log['result']}")


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
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'POST,GET,OPTIONS',
            'X-Request-ID': str(int(time.time() * 1000))
        },
        'body': json.dumps(body, indent=2)
    }
