import json
import requests
import logging
from utils import TaskResultStatus, Severities

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_task_result_callback_request(
    security_posture_report=None, status=TaskResultStatus.RUNNING
):
    """
    Creates a task result callback request with the specified status.

    Args:
      security_posture_report: A dictionary containing the security posture report data (required for PASSED/FAILED status).
      status: The status of the task (RUNNING, PASSED, or FAILED).

    Returns:
      A bytes object representing the JSON-encoded callback request payload.
    """
    try:

        if status == TaskResultStatus.RUNNING:
            task_result_attributes = {
                "status": "running",
                "message": "operation running",
            }
            callback_req = {
                "data": {
                    "type": "task-results",
                    "attributes": task_result_attributes,
                }
            }
        else:
            report_id = security_posture_report["name"]
            violations = security_posture_report.get("iacValidationReport").get(
                "violations"
            )

            if violations is None:
                status = TaskResultStatus.PASSED
                violations = []
            else:
                status = TaskResultStatus.FAILED

            critical_count = high_count = medium_count = low_count = 0
            outcomes = []

            for violation in violations:
                asset_id = violation.get("assetId")  # Check for None
                policy_id = violation.get("policyId")  # Check for None
                constraint_type = violation.get("violatedPolicy").get("constraintType")
                severity = violation.get("severity")

                if severity == Severities.LOW.value:
                    low_count += 1
                elif severity == Severities.MEDIUM.value:
                    medium_count += 1
                elif severity == Severities.HIGH.value:
                    high_count += 1
                elif severity == Severities.CRITICAL.value:
                    critical_count += 1

                # Check for None before creating outcome
                if asset_id and policy_id and constraint_type and severity:
                    outcomes.append(
                        {
                            "type": "task-result-outcomes",
                            "attributes": {
                                "outcome-id": "sample-outcome-id",
                                "description": f"Policy {policy_id} violated by asset {asset_id}",
                                "body": f"### Severity \n{severity} \n### Asset ID \n{asset_id} \n### Policy \n{policy_id} \n### Constraint type \n{constraint_type}",
                            },
                        }
                    )

            task_result_attributes = {
                "status": status.name.lower(),
                "message": f"{low_count} LOW, {medium_count} MEDIUM, {high_count} HIGH, {critical_count} CRITICAL asset violations found",
                "url": f"https://securityposture.googleapis.com/v1/{report_id}",
            }
            callback_req = {
                "data": {
                    "type": "task-results",
                    "attributes": task_result_attributes,
                    "relationships": {"outcomes": {"data": outcomes}},
                }
            }

        return bytes(json.dumps(callback_req), encoding="utf-8")
    except Exception as e:
        logger.error(f"Could not create callback request: {e}")
        return None


def send_terraform_callback(callback_url, access_token, callback_request):
    """
    Sends a callback to Terraform Cloud.

    Args:
      callback_url: The URL for the Terraform Cloud callback.
      access_token: The access token for authentication.
      callback_req_body: The request body for the callback.

    Raises:
      requests.exceptions.RequestException: If there's an error sending the callback.
    """
    try:
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {access_token}",
        }

        response = requests.patch(callback_url, headers=headers, data=callback_request)
        return response.status_code

    except requests.exceptions.RequestException as e:
        if hasattr(e.response, "status_code"):
            return e.response.status_code
        else:
            return 500
