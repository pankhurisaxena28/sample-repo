import logging
import os
from flask import Request, Response, Flask

from validations import validate_request, validate_hmac_signature
from iacv import (
    get_access_token,
    get_organization_id,
    validate_iac,
    fetch_iac_validation_report,
)
from utils import fetch_terraform_plan, get_project_number
from callback import create_task_result_callback_request, send_terraform_callback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/", methods=["POST"])
def analyze_terraform_plan(request: Request):
    try:
        # Validate request
        is_valid, error_message = validate_request(request)
        if not is_valid:
            return Response(error_message, status=400)

        payload = request.get_json()

        if payload["stage"] == "test":
            return Response("", status=200)

        gcloud_access_token, project_id = get_access_token()
        print(f"{gcloud_access_token}")
        if gcloud_access_token is None:
            logger.error("Failed to obtain access token")
            return Response("Failed to obtain access token", status=500)

        if project_id is None:
            logger.error("Failed to fetch project ID")
            return Response("Failed to fetch project ID", status=500)

        project_number = get_project_number(project_id)
        if project_number is None:
            logger.error("Failed to fetch project number")
            return Response("Failed to fetch project number", status=500)

        organization_id = get_organization_id(project_id, gcloud_access_token)

        if organization_id is None:
            logger.error("Failed to fetch organization ID")
            return Response("Internal server error", status=500)

        # Authenticate request
        if not validate_hmac_signature(request, project_number):
            logger.error("Invalid HMAC signature")
            return Response("Invalid HMAC signature", status=401)

        plan_file, status_code = fetch_terraform_plan(
            payload["plan_json_api_url"], payload["access_token"]
        )

        if status_code != 200:
            logger.error("Failed to fetch plan file")
            return Response("Failed to fetch plan file", status_code)

        iacv_operation_id, status_code, error_message = validate_iac(
            plan_file, organization_id, gcloud_access_token, project_id
        )

        if status_code != 200:
            logger.error(error_message)
            return Response(error_message, status_code)
        if error_message is not None:
            logger.error(error_message)
            return Response(error_message, 500)

        iacv_report, status_code, error_message = fetch_iac_validation_report(
            iacv_operation_id,
            gcloud_access_token,
            project_id,
            payload["task_result_callback_url"],
            payload["access_token"],
        )

        if status_code != 200:
            logger.error(error_message)
            return Response(error_message, status_code)
        if error_message is not None:
            logger.error(error_message)
            return Response(error_message, 500)

        callback_request = create_task_result_callback_request(iacv_report, status=None)
        callback_status_code = send_terraform_callback(
            payload["task_result_callback_url"],
            payload["access_token"],
            callback_request,
        )

        return callback_status_code


    except Exception as e:
        logger.info(f"Exception occured: {e}")
        return Response(f"Task errored out with exception: {e}", status=500)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
