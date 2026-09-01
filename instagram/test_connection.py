import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


# ============================================================
# THRAANSH INSTAGRAM CONNECTION TEST V1
#
# PURPOSE:
#
# - Load Instagram credentials from .env
# - Verify token works
# - Verify account ID
# - Confirm professional Instagram account
# - Print username / account information
#
# DOES NOT PUBLISH ANYTHING
# ============================================================


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

ENV_FILE = (
    PROJECT_ROOT
    / ".env"
)


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv(
    ENV_FILE,
    override=True
)


INSTAGRAM_ACCESS_TOKEN = os.getenv(
    "INSTAGRAM_ACCESS_TOKEN"
)

INSTAGRAM_ACCOUNT_ID = os.getenv(
    "INSTAGRAM_ACCOUNT_ID"
)

INSTAGRAM_GRAPH_VERSION = os.getenv(
    "INSTAGRAM_GRAPH_VERSION",
    "v26.0"
)


# ============================================================
# DISPLAY HELPERS
# ============================================================

def line():
    print("=" * 72)


def fail(message, code=1):

    print()
    line()

    print(
        f"❌ {message}"
    )

    line()

    sys.exit(code)


def success(message):

    print(
        f"✅ {message}"
    )


# ============================================================
# CHECK ENVIRONMENT
# ============================================================

def check_environment():

    print()
    print(
        "STEP 1: Checking Instagram environment variables..."
    )

    if not INSTAGRAM_ACCESS_TOKEN:

        fail(
            "INSTAGRAM_ACCESS_TOKEN is missing from .env"
        )

    if not INSTAGRAM_ACCOUNT_ID:

        fail(
            "INSTAGRAM_ACCOUNT_ID is missing from .env"
        )

    print(
        "INSTAGRAM_ACCESS_TOKEN: LOADED"
    )

    print(
        "Token length:",
        len(INSTAGRAM_ACCESS_TOKEN)
    )

    print(
        "INSTAGRAM_ACCOUNT_ID:",
        INSTAGRAM_ACCOUNT_ID
    )

    success(
        "Instagram environment variables loaded"
    )


# ============================================================
# TRY INSTAGRAM GRAPH API
# ============================================================

def test_instagram_graph_api():

    print()
    line()

    print(
        "STEP 2: Testing Instagram account connection"
    )

    line()

    # --------------------------------------------------------
    # Instagram API with Instagram Login
    #
    # This uses graph.instagram.com
    # --------------------------------------------------------

    url = (
        "https://graph.instagram.com/"
        f"{INSTAGRAM_ACCOUNT_ID}"
    )

    params = {

        "fields":
            "id,user_id,username,name,"
            "account_type,profile_picture_url",

        "access_token":
            INSTAGRAM_ACCESS_TOKEN,
    }

    print()
    print(
        "Trying Instagram API..."
    )

    print(
        "Endpoint:",
        url
    )

    try:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

    except requests.RequestException as error:

        fail(
            "Instagram API request failed:\n"
            f"{error}"
        )

    print()
    print(
        "HTTP Status:",
        response.status_code
    )

    try:

        result = response.json()

    except Exception:

        print()
        print(
            "Raw response:"
        )

        print(
            response.text
        )

        fail(
            "Instagram returned a non-JSON response."
        )

    print()

    print(
        "Response:"
    )

    print(
        result
    )

    if (
        response.status_code
        == 200
        and result.get("id")
    ):

        return (
            True,
            result,
            "instagram"
        )

    return (
        False,
        result,
        "instagram"
    )


# ============================================================
# TRY FACEBOOK GRAPH API FALLBACK
# ============================================================

def test_facebook_graph_api():

    print()
    line()

    print(
        "STEP 3: Trying Meta/Facebook Graph API fallback"
    )

    line()

    url = (
        "https://graph.facebook.com/"
        f"{INSTAGRAM_GRAPH_VERSION}/"
        f"{INSTAGRAM_ACCOUNT_ID}"
    )

    params = {

        "fields":
            "id,username,name,"
            "profile_picture_url,"
            "followers_count,"
            "follows_count,"
            "media_count",

        "access_token":
            INSTAGRAM_ACCESS_TOKEN,
    }

    print()
    print(
        "Endpoint:",
        url
    )

    try:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

    except requests.RequestException as error:

        fail(
            "Facebook Graph Instagram request failed:\n"
            f"{error}"
        )

    print()
    print(
        "HTTP Status:",
        response.status_code
    )

    try:

        result = response.json()

    except Exception:

        print()
        print(
            "Raw response:"
        )

        print(
            response.text
        )

        fail(
            "Meta Graph API returned a non-JSON response."
        )

    print()

    print(
        "Response:"
    )

    print(
        result
    )

    if (
        response.status_code
        == 200
        and result.get("id")
    ):

        return (
            True,
            result,
            "facebook"
        )

    return (
        False,
        result,
        "facebook"
    )


# ============================================================
# VERIFY ACCOUNT
# ============================================================

def verify_account(result):

    print()
    line()

    print(
        "STEP 4: Verifying Instagram account"
    )

    line()

    returned_id = str(
        result.get(
            "id",
            ""
        )
    ).strip()

    configured_id = str(
        INSTAGRAM_ACCOUNT_ID
    ).strip()

    username = (
        result.get(
            "username"
        )
        or "Not returned"
    )

    name = (
        result.get(
            "name"
        )
        or "Not returned"
    )

    account_type = (
        result.get(
            "account_type"
        )
        or "Not returned"
    )

    print()
    print(
        "Configured Instagram ID:"
    )

    print(
        configured_id
    )

    print()

    print(
        "Returned Instagram ID:"
    )

    print(
        returned_id
    )

    print()

    print(
        "Username:"
    )

    print(
        username
    )

    print()

    print(
        "Name:"
    )

    print(
        name
    )

    print()

    print(
        "Account type:"
    )

    print(
        account_type
    )

    if not returned_id:

        fail(
            "Instagram API did not return an account ID."
        )

    # --------------------------------------------------------
    # Account ID consistency check
    # --------------------------------------------------------

    if returned_id != configured_id:

        print()
        print(
            "⚠️ INSTAGRAM ACCOUNT ID MISMATCH"
        )

        print()
        print(
            "Your .env contains:"
        )

        print(
            configured_id
        )

        print()

        print(
            "Instagram returned:"
        )

        print(
            returned_id
        )

        print()
        print(
            "Do NOT change anything yet."
        )

        print(
            "Send this terminal result to me first."
        )

        return False

    success(
        "Correct Instagram account detected"
    )

    return True


# ============================================================
# PRINT OPTIONAL ACCOUNT DETAILS
# ============================================================

def print_optional_details(result):

    followers = result.get(
        "followers_count"
    )

    follows = result.get(
        "follows_count"
    )

    media_count = result.get(
        "media_count"
    )

    if (
        followers is None
        and follows is None
        and media_count is None
    ):

        return

    print()
    line()

    print(
        "INSTAGRAM ACCOUNT DETAILS"
    )

    line()

    if followers is not None:

        print()
        print(
            "Followers:",
            followers
        )

    if follows is not None:

        print()
        print(
            "Following:",
            follows
        )

    if media_count is not None:

        print()
        print(
            "Media count:",
            media_count
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    line()

    print(
        "THRAANSH INSTAGRAM CONNECTION TEST V1"
    )

    line()

    print()
    print(
        "This test will NOT publish anything."
    )

    # ========================================================
    # STEP 1
    # ========================================================

    check_environment()

    # ========================================================
    # STEP 2
    #
    # First try Instagram API with Instagram Login.
    # ========================================================

    (
        connected,
        result,
        api_type
    ) = test_instagram_graph_api()

    # ========================================================
    # STEP 3
    #
    # If Instagram API does not work, try Meta Graph.
    # ========================================================

    if not connected:

        print()
        print(
            "Instagram API connection did not succeed."
        )

        print(
            "Trying Meta Graph API fallback..."
        )

        (
            connected,
            result,
            api_type
        ) = test_facebook_graph_api()

    # ========================================================
    # FAILURE
    # ========================================================

    if not connected:

        print()
        line()

        print(
            "❌ INSTAGRAM CONNECTION FAILED"
        )

        line()

        print()

        print(
            "The access token or account ID may be:"
        )

        print(
            "- expired"
        )

        print(
            "- incorrect"
        )

        print(
            "- generated for a different Instagram API type"
        )

        print(
            "- missing required permissions"
        )

        print()
        print(
            "Do NOT paste your access token here."
        )

        print()

        print(
            "Send me only the terminal output."
        )

        sys.exit(1)

    # ========================================================
    # VERIFY ACCOUNT
    # ========================================================

    account_valid = (
        verify_account(
            result
        )
    )

    if not account_valid:

        sys.exit(2)

    # ========================================================
    # OPTIONAL DETAILS
    # ========================================================

    print_optional_details(
        result
    )

    # ========================================================
    # SUCCESS
    # ========================================================

    print()
    line()

    print(
        "✅ INSTAGRAM CONNECTION SUCCESSFUL"
    )

    line()

    print()

    print(
        "API connection type:"
    )

    if api_type == "instagram":

        print(
            "Instagram API with Instagram Login"
        )

    else:

        print(
            "Meta/Facebook Graph Instagram API"
        )

    print()

    print(
        "Instagram Account ID:"
    )

    print(
        result.get(
            "id"
        )
    )

    print()

    print(
        "Username:"
    )

    print(
        result.get(
            "username",
            "Not returned"
        )
    )

    print()

    print(
        "Connection status: READY"
    )

    print()

    print(
        "Publishing test: NOT RUN YET"
    )

    print()

    print(
        "Next stage after this succeeds:"
    )

    print(
        "Instagram video publishing"
    )

    line()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print(
            "Instagram connection test stopped by user."
        )

        sys.exit(130)