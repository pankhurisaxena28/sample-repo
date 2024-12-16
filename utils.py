import logging
from enum import Enum, auto
from google.cloud import resourcemanager_v3
import requests

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskResultStatus(Enum):
    """Enum for task result statuses."""

    RUNNING = auto()
    PASSED = auto()
    FAILED = auto()


class Severities(Enum):
    """Enum for violation severities."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def fetch_terraform_plan(plan_url, api_token):
    """
    Fetches the Terraform plan JSON from the given URL.

    Args:
      plan_url: The URL of the Terraform plan.
      api_token: The API token for authentication.

    Returns:
      The Terraform plan as a JSON object.

    Raises:
      requests.exceptions.RequestException: If there's an error fetching the plan.
    """

    try:
        headers = {"Authorization": f"Bearer {api_token}"}
        response = requests.get(plan_url, headers=headers)
        return response.json(), response.status_code

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Terraform plan: {e}")
        if hasattr(e.response, "status_code"):
            return None, e.response.status_code
        else:
            return None, 500


def get_project_number(project_id):
    """
    Fetches the project number of a GCP project using its project ID.

    Args:
      project_id: The ID of the GCP project.

    Returns:
      The project number as a string, or None if the project is not found.
    """
    try:
        client = resourcemanager_v3.ProjectsClient()
        request = resourcemanager_v3.SearchProjectsRequest(query=f"id:{project_id}")
        page_result = client.search_projects(request=request)
        for response in page_result:
            if response.project_id == project_id:
                project = response.name
                return project.replace("projects/", "")
        return None
    except Exception as e:
        logger.error(f"Error fetching project number: {e}")
        return None
