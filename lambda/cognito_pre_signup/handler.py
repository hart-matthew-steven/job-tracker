import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SUPPORTED_TRIGGERS = {"PreSignUp_SignUp", "PreSignUp_AdminCreateUser"}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:  # noqa: ANN401
    """
    Cognito Pre Sign-up trigger handler.

    Ensures every signup is auto-confirmed while leaving email verification to downstream systems.
    """

    trigger = event.get("triggerSource")
    user_pool_id = event.get("userPoolId")
    user_name = event.get("userName")

    logger.info(
        "PreSignUp trigger received (triggerSource=%s, userPoolId=%s, userName=%s)",
        trigger or "unknown",
        user_pool_id or "unknown",
        user_name or "unknown",
    )

    if trigger in SUPPORTED_TRIGGERS:
        response = event.setdefault("response", {})
        response["autoConfirmUser"] = True
        response["autoVerifyEmail"] = False
    else:
        logger.warning("Unsupported triggerSource %s; leaving event unchanged.", trigger)

    return event


