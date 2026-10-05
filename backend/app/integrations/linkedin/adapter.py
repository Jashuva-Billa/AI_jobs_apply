from typing import Protocol, Optional, Dict, Any
import logging
import urllib.parse

logger = logging.getLogger(__name__)

class LinkedInProvider(Protocol):
    async def get_profile(self, profile_id: str) -> Dict[str, Any]:
        ...

    async def get_authorized_data(self) -> Dict[str, Any]:
        ...

    async def prepare_message(self, recipient_name: str, recipient_url: Optional[str], message: str) -> Dict[str, Any]:
        ...

class CompliantLinkedInAdapter:
    """
    Compliant LinkedIn adapter.
    Adheres strictly to platform terms and prevents unauthorized scraping or automated browser messaging.
    Prepares verified outreach copy with direct manual deep-links for the user.
    """
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret

    async def get_profile(self, profile_id: str) -> Dict[str, Any]:
        return {"profile_id": profile_id, "status": "AUTHORIZED_PROFILE_STUB"}

    async def get_authorized_data(self) -> Dict[str, Any]:
        return {"status": "AUTHORIZED_CONNECTED"}

    async def prepare_message(self, recipient_name: str, recipient_url: Optional[str], message: str) -> Dict[str, Any]:
        encoded_message = urllib.parse.quote(message)
        
        # Build direct LinkedIn URL or search URL
        if recipient_url and "linkedin.com" in recipient_url:
            target_url = recipient_url
        else:
            target_url = f"https://www.linkedin.com/search/results/all/?keywords={urllib.parse.quote(recipient_name)}"

        return {
            "action_status": "MANUAL_REQUIRED",
            "recipient_name": recipient_name,
            "target_url": target_url,
            "prepared_message": message,
            "instructions": "Open the recruiter's verified LinkedIn profile, click Connect/Message, and paste the pre-approved personalized outreach.",
            "char_count": len(message)
        }

linkedin_adapter = CompliantLinkedInAdapter()
