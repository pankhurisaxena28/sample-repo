from flask import Request, request, Response
import logging
import json
import hashlib
import hmac
import base64

from google.cloud import secretmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_request(request):
    """
    Validates that the request contains the necessary headers and body fields.

    Args:
      request: The Flask request object.

    Returns:
      A tuple containing:
        - A boolean indicating whether the request is valid.
        - A string containing an error message if the request is invalid, or None otherwise.
    """

    # Validate header fields
    if "X-TFC-Task-Signature" not in request.headers:
        return False, "Missing header field: X-TFC-Task-Signature"

    # Validate body fields
    try:
        body = request.get_json()
    except:
        return False, "Invalid JSON body"

    required_body_fields = [
        "stage",
        "access_token",
        "organization_name",
        "plan_json_api_url",
        "task_result_callback_url",
    ]
    for field in required_body_fields:
        if field not in body:
            return False, f"Missing body field: {field}"

    return True, None


def validate_hmac_signature(request: Request, project_number):
    """
    Validates the HMAC signature in the X-TFC-Task-Signature header.

    Args:
      request: The Flask request object.

    Returns:
      A boolean indicating whether the signature is valid.
    """

    try:
        # Get the signature from the header
        signature_header = request.headers["X-TFC-Task-Signature"]

        # Retrieve the HMAC key from Secret Manager
        secret_name = (
            f"projects/{project_number}/secrets/HCP_TERRAFORM_HMAC/versions/latest"
        )
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_name})
        secret_key = response.payload.data.decode("UTF-8")
        # Calculate the expected signature
        payload = request.get_data()
        expected_signature = hmac.new(
            secret_key.encode("UTF-8"), payload, hashlib.sha512
        ).hexdigest()

        # Compare the signatures
        return hmac.compare_digest(signature_header, expected_signature)

    except Exception as e:
        logger.error(f"Error validating HMAC signature: {e}")
        return False
