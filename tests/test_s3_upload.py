import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workflow import save_final_report_to_s3


class TestS3Upload(unittest.TestCase):
    def setUp(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "test-access-key"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "test-secret-key"
        os.environ["AWS_REGION"] = "ap-southeast-2"
        os.environ["S3_BUCKET_NAME"] = "demo-bucket"
        os.environ["AWS_S3_ENDPOINT_URL"] = "https://s3.example.com"

    def tearDown(self):
        for key in [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION",
            "S3_BUCKET_NAME",
            "AWS_S3_ENDPOINT_URL",
        ]:
            os.environ.pop(key, None)

    @patch("workflow.boto3")
    def test_save_final_report_to_s3_uses_env_credentials(self, mock_boto3):
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        state = {
            "vehicle_id": "VH-1002",
            "final_report": "# Maintenance report\nEverything looks good."
        }

        result = save_final_report_to_s3(state)

        self.assertIn("s3://demo-bucket/", result)
        mock_boto3.client.assert_called_once_with(
            "s3",
            region_name="ap-southeast-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            endpoint_url="https://s3.example.com",
        )
        mock_client.put_object.assert_called_once()

    @patch("workflow.boto3")
    def test_save_final_report_to_s3_skips_without_bucket(self, mock_boto3):
        os.environ.pop("S3_BUCKET_NAME", None)
        os.environ.pop("AWS_S3_BUCKET", None)

        state = {"vehicle_id": "VH-1002", "final_report": "report"}

        result = save_final_report_to_s3(state)

        self.assertIsNone(result)
        mock_boto3.client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
