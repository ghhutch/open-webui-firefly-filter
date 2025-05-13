"""
title: Adobe Firefly Integration
author: Graham Hutchinson
author_url: https://github.com/ghhutch
version: 0.1
"""

import os
import time
import base64
import uuid
import requests
from io import BytesIO
from pathlib import Path
from PIL import Image
import logging
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("firefly_integration")

# Directory for storing generated images
IMAGES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "generated_images"
)
os.makedirs(IMAGES_DIR, exist_ok=True)


class Filter:

    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        client_id: str = Field(default="", description="Adobe Firefly client ID")
        client_secret: str = Field(
            default="", description="Adobe Firefly client secret"
        )
        default_size: str = Field(
            default="1024x1024", description="Default size for generated images"
        )
        default_content_class: str = Field(
            default="photo",
            description="Default content class (photo, art)",
        )
        default_model: str = Field(
            default="image4_standard",
            description="Default model (image3, image3_custom, image4_standard, image4_ultra)",
        )

    class UserValves(BaseModel):
        client_id: str = Field(
            default="", description="User-specific Adobe Firefly client ID"
        )
        client_secret: str = Field(
            default="", description="User-specific Adobe Firefly client secret"
        )

    def __init__(self):
        # Token management
        self.type = "filter"
        self.id = "firefly_filter"
        self.name = "Firefly Filter"
        self.token_cache = {"access_token": None, "expires_at": 0}
        self.image_html = ""
        self.image_url = ""
        self.prompt = ""
        self.apply_filter = False
        self.valves = self.Valves()

        # Log configuration status at initialization
        if self.valves.client_id and self.valves.client_secret:
            logger.info(
                f"Adobe Firefly integration initialized with client_id: {self.valves.client_id[:5]}..."
            )

            # Try to get an initial token to verify credentials
            try:
                if self._get_valid_token():
                    logger.info("Successfully verified Adobe Firefly API credentials")
                else:
                    logger.warning(
                        "Could not verify Adobe Firefly API credentials - token request failed"
                    )
            except Exception as e:
                logger.warning(f"Could not verify Adobe Firefly API credentials: {e}")
        else:
            logger.warning(
                "Adobe Firefly integration initialized but missing API credentials"
            )
            logger.warning(
                "Set FIREFLY_CLIENT_ID and FIREFLY_CLIENT_SECRET environment variables or configure in valves"
            )

    def inlet(self, body: dict, __user__: Optional[Any] = None) -> dict:
        """Process incoming requests before they reach the API"""
        logger.info(f"inlet:{__name__}")

        # Check if this is a request for image generation
        messages = body.get("messages", [])
        if messages and len(messages) > 0:
            last_message = messages[-1]
            content = last_message.get("content", "")

            # Check if the message contains a command to generate an image
            if isinstance(content, str) and content.lower().startswith("/firefly"):

                # Set apply filter for subsequent actions in the filter
                logger.info(f"Prompt contains /firefly - apply filter")
                self.apply_filter = True

                # Extract prompt from the command
                prompt = content[len("/firefly") :].strip()
                self.prompt = prompt

                # Check if a prompt was provided
                if not prompt:
                    # If no prompt is provided, we'll respond with usage instructions
                    body["messages"][-1][
                        "content"
                    ] = "Please provide a prompt for image generation. Usage: /firefly your prompt here"
                    return body

                # TODO: Determine photo or art content class

                # TODO: Determine number of outputs

                # TODO: Determine size of outputs

                # Get user-specific credentials if available
                user_valves = getattr(__user__, "valves", None)

                # Debug credential info
                logger.debug(
                    f"Using client_id: {self.valves.client_id[:5]}... (length: {len(self.valves.client_id)})"
                )
                logger.debug(
                    f"Using client_secret: {self.valves.client_secret[:3]}... (length: {len(self.valves.client_secret)})"
                )

                if not self.valves.client_id or len(self.valves.client_id) < 10:
                    error_msg = "Adobe Firefly client_id is missing or invalid. Please set FIREFLY_CLIENT_ID environment variable or configure in valves."
                    logger.error(error_msg)
                    body["messages"][-1]["content"] = error_msg
                    self.apply_filter = False
                    return body

                if not self.valves.client_secret or len(self.valves.client_secret) < 10:
                    error_msg = "Adobe Firefly client_secret is missing or invalid. Please set FIREFLY_CLIENT_SECRET environment variable or configure in valves."
                    logger.error(error_msg)
                    body["messages"][-1]["content"] = error_msg
                    self.apply_filter = False
                    return body

                # Generate the image
                try:
                    result = self._generate_image(
                        prompt,
                        client_id=self.valves.client_id,
                        client_secret=self.valves.client_secret,
                        size=self.valves.default_size,
                        content_class=self.valves.default_content_class,
                    )

                    # Replace the user message with the result
                    body["messages"][-1]["content"] = ""

                except Exception as e:
                    logger.error(f"Error generating image: {e}")
                    body["messages"][-1][
                        "content"
                    ] = f"Error generating image: {str(e)}\n\nPlease check that your Adobe Firefly API credentials are valid and have sufficient permissions."

        return body

    def stream(self, event: dict) -> dict:
        if self.apply_filter:
            for choice in event.get("choices", []):
                delta = choice.get("delta", {})
                if "content" in delta:
                    # don't output stream to ui.
                    delta["content"] = ""
        return event

    def outlet(self, body: dict, __user__: Optional[Any] = None) -> dict:
        """Process outgoing responses after they come from the API"""
        if self.apply_filter:
            logger.debug(f"outlet:{__name__}")
            logger.info(f"image_url: {self.image_url}")

            body["messages"][-1]["content"] = f"![image]({self.image_url})\n"

        self.apply_filter = False
        return body

    def _get_access_token(self, client_id=None, client_secret=None):
        """
        Get an access token from Adobe IMS using client credentials

        Args:
            client_id (str, optional): Adobe Firefly client ID
            client_secret (str, optional): Adobe Firefly client secret

        Returns:
            dict: Token data if successful, None otherwise
        """
        if not client_id:
            logger.error(
                "Missing client_id. Please set FIREFLY_CLIENT_ID environment variable or configure in valves."
            )
            return None

        if not client_secret:
            logger.error(
                "Missing client_secret. Please set FIREFLY_CLIENT_SECRET environment variable or configure in valves."
            )
            return None

        logger.info(f"Requesting access token for client_id: {client_id[:5]}...")

        url = "https://ims-na1.adobelogin.com/ims/token/v3"

        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "openid,AdobeID,session,additional_info,read_organizations,firefly_api,ff_apis",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            token_data = response.json()
            logger.info("Successfully obtained access token")
            return token_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error obtaining access token: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return None

    def _get_valid_token(self, client_id=None, client_secret=None):
        """Get a valid access token, refreshing if needed"""
        # If using default credentials, check cache first
        if (client_id is None or client_id == self.valves.client_id) and (
            client_secret is None or client_secret == self.valves.client_secret
        ):

            current_time = time.time()

            # Check if token needs refresh (expired or will expire in 5 minutes)
            if (
                self.token_cache["access_token"] is not None
                and self.token_cache["expires_at"] > current_time + 300
            ):
                return self.token_cache["access_token"]

        # Get new token
        client_id = client_id or self.valves.client_id
        client_secret = client_secret or self.valves.client_secret

        token_response = self._get_access_token(client_id, client_secret)

        if token_response and "access_token" in token_response:
            # Cache the token if using default credentials
            if (
                client_id == self.valves.client_id
                and client_secret == self.valves.client_secret
            ):
                self.token_cache["access_token"] = token_response["access_token"]
                self.token_cache["expires_at"] = time.time() + token_response.get(
                    "expires_in", 86400
                )

            return token_response["access_token"]
        else:
            return None


    def _generate_image(
        self,
        prompt,
        client_id=None,
        client_secret=None,
        size="1024x1024",
        content_class="photo",
    ):
        """
        Generate an image using Adobe Firefly API and return formatted content

        Args:
            prompt (str): Text prompt describing the image to generate
            client_id (str, optional): Adobe Firefly client ID
            client_secret (str, optional): Adobe Firefly client secret
            size (str): Size of the image to generate (e.g., "1024x1024")
            content_class (str): Type of content to generate (photo, art)

        Returns:
            str: HTML content with embedded image if successful
        """
        # Get access token
        access_token = self._get_valid_token(client_id, client_secret)
        if not access_token:
            raise Exception(
                "Failed to obtain access token from Adobe API. Please verify your client_id and client_secret are valid and have the correct permissions."
            )

        # Use provided credentials or default ones
        client_id = client_id or self.valves.client_id

        # Adobe Firefly API endpoint
        url = "https://firefly-api.adobe.io/v3/images/generate"

        # Parse dimensions
        try:
            width, height = map(int, size.split("x"))
        except ValueError:
            raise ValueError(f"Invalid size format: {size}. Use format '1024x1024'")

        # Request headers
        headers = {
            "x-api-key": client_id,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-model-version": self.valves.default_model,
        }

        # Request payload
        payload = {
            "prompt": prompt,
            "size": {"width": width, "height": height},
            "contentClass": content_class,
        }

        try:
            # Make the API request
            logger.info(f"Sending request to Firefly API with prompt: '{prompt}'")
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            # Parse the response
            data = response.json()

            # Extract the image URL from the response
            if (
                "outputs" in data
                and len(data["outputs"]) > 0
                and "image" in data["outputs"][0]
            ):
                image_url = data["outputs"][0]["image"]["url"]
                self.image_url = image_url
                logger.info(f"Image URL received: {image_url}")

                # return html_content
                return image_url
            else:
                logger.error("No image URL found in response")
                logger.error(f"Response: {data}")

                # Check if there's an error message in the response
                error_msg = "No image URL found in Firefly API response"
                if "error" in data:
                    error_msg += f": {data['error'].get('message', '')}"
                elif "errors" in data and data["errors"]:
                    error_msg += f": {data['errors'][0].get('message', '')}"

                raise Exception(error_msg)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Adobe Firefly API: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")

                # Try to extract error message from response
                try:
                    error_content = e.response.json()
                    if "error" in error_content:
                        error_msg = error_content["error"].get("message", str(e))
                    else:
                        error_msg = str(e)
                except:
                    error_msg = str(e)

                raise Exception(f"Adobe Firefly API error: {error_msg}")
            raise
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            raise

