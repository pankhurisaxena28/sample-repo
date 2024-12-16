import google.auth
import logging
import requests
import json
import base64
import time
from callback import create_task_result_callback_request, send_terraform_callback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_access_token():
    """
    Retrieves an access token for the Cloud Run service account.

    Returns:
      A string containing the access token.
    """
    try:
        credentials, project_id = google.auth.default()
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token, project_id

    except Exception as e:
        logger.error(f"Error getting access token: {e}")
        return None, None


def get_organization_id(project_id, auth_token):
    """
    Extracts the organization ID from a given project ID using an auth token
    and the REST API.

    Args:
      project_id: The ID of the Google Cloud project.
      auth_token: The authentication token.

    Returns:
      The organization ID as a string, or None if not found.
    """
    try:
        # Construct the API URL
        url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}:getAncestry"

        # Set up the request headers
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

        # Send the request
        response = requests.post(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()

        # Extract organization ID from the ancestry response
        for ancestor in data.get("ancestor", []):
            if ancestor["resourceId"]["type"] == "organization":
                return ancestor["resourceId"]["id"]

        return None

    except Exception as e:
        logger.error(f"Error getting organization ID: {e}")
        return None


def _create_gcloud_request_headers(gcloud_access_token, project_id):
    """Creates the request headers for the IaC Validation API."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gcloud_access_token}",
        "X-GFE-SSL": "yes",
        "x-goog-user-project": project_id,
    }


def _create_iac_validation_request_body(plan_json, org_id):
    """Creates the request body for the IaC Validation API."""
    parent = f"organizations/{org_id}/locations/global"
    tf_plan = base64.b64encode(json.dumps(plan_json).encode("utf-8")).decode("utf-8")
    return {"parent": parent, "iac": {"tf_plan": tf_plan}}


def _call_iac_validation_api(url, headers, body):
    """
    Calls the Security Command Center IaC Validation API.
    Retries the API call up to three times with exponential backoff
    if the response status code is in the retryable list.

    Args:
      url: The API endpoint URL.
      headers: The request headers.
      body: The request body.

    Returns:
      A tuple containing:
        - The name of the created IaC Validation report if successful, otherwise None.
        - The HTTP status code (200 on success, error code otherwise).
        - An error message if applicable, otherwise None.
    """
    retryable_status_codes = [408, 429, 500, 502, 503, 504]
    retry_delays = [5, 10, 20]  # Delays in seconds for each retry

    for i in range(4):  # Retry up to 3 times
        try:
            response = requests.post(url, headers=headers, data=json.dumps(body))
            return response.json()["name"], 200, None  # Success

        except requests.exceptions.RequestException as e:
            if (
                hasattr(e.response, "status_code")
                and e.response.status_code in retryable_status_codes
            ):
                if i == 3:
                    break
                logger.warning(
                    f"Retryable error ({e.response.status_code}) calling IaC Validation API. Retrying in {retry_delays[i]} seconds..."
                )
                time.sleep(retry_delays[i])  # Wait before retrying
            else:
                error_message = f"Error calling IaC Validation API: {e}"
                logger.error(error_message)
                if hasattr(e.response, "status_code"):
                    return None, e.response.status_code, error_message
                else:
                    return None, 500, error_message

    # If all retries fail, return the last error
    error_message = "All retries failed for IaC Validation API call."
    logger.error(error_message)
    return None, 500, error_message


def validate_iac(plan_json, org_id, gcloud_access_token, project_id):
    """
    Analyzes the Terraform plan using Security Command Center's IaC Validation API.

    Args:
      plan_json: The Terraform plan as a JSON object.
      org_id: The organization ID.
      gcloud_access_token: The Google Cloud access token.
      project_id: The Google Cloud project ID.

    Returns:
      The name of the created IaC Validation report.

    Raises:
      requests.exceptions.RequestException: If there's an error calling the API.
    """
    headers = _create_gcloud_request_headers(gcloud_access_token, project_id)
    parent = f"organizations/{org_id}/locations/global"
    url = f"https://securityposture.googleapis.com/v1/{parent}/reports:createIaCValidationReport"

    body = _create_iac_validation_request_body(plan_json, org_id)

    return _call_iac_validation_api(url, headers, body)


def fetch_iac_validation_report(
    operation_id,
    gcloud_access_token,
    project_id,
    task_result_callback_url,
    terraform_access_token,
):
    """
    Fetches the IaC Validation report from Security Command Center.

    Args:
      operation_id: The ID of the long-running operation.
      gcloud_access_token: The Google Cloud access token.
      project_id: The Google Cloud project ID.
      task_result_callback_url: The URL for sending task result callbacks.
      access_token: The access token for the callback URL.

    Returns:
      The IaC Validation report.

    Raises:
      requests.exceptions.RequestException: If there's an error fetching the report.
    """
    try:
        headers = _create_gcloud_request_headers(gcloud_access_token, project_id)
        url = f"https://securityposture.googleapis.com/v1/{operation_id}"

        while True:
            callback_request = create_task_result_callback_request()
            if callback_request is None:
                return None, 500, f"Error creating callback request"
            callback_status_code = send_terraform_callback(
                task_result_callback_url, terraform_access_token, callback_request
            )
            if callback_status_code != 200:
                return None, callback_status_code, f"Error sending callback request"
            operation_details = requests.get(url, headers=headers).json()
            if operation_details["done"]:  # Simplified boolean check
                break

            time.sleep(10)

        report = operation_details["response"]
        return report, 200, None

    except requests.exceptions.RequestException as e:
        error_message = f"Error fetching IaC Validation report: {e}"
        logger.error(error_message)
        if hasattr(e.response, "status_code"):
            return None, e.response.status_code, error_message
        else:
            return None, 500, error_message
