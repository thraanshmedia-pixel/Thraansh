import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


# ============================================================
# THRAANSH RIGHTS / COPYRIGHT PREFLIGHT GATE V3
#
# FAIL-CLOSED:
# Unknown/unverified media -> BLOCK publishing
#
# This is a rights/license preflight system.
# It does NOT guarantee that a platform will never issue
# a copyright, Content ID, trademark, privacy or other claim.
# ============================================================


PROJECT_ROOT = Path(__file__).resolve().parent.parent

QUEUE_FILE = PROJECT_ROOT / "data" / "article_queue.json"

RIGHTS_FOLDER = PROJECT_ROOT / "rights_manifests"

MUSIC_FOLDER = PROJECT_ROOT / "music"

MUSIC_REGISTRY_FILE = (
    PROJECT_ROOT
    / "copyright"
    / "music_registry.json"
)

DEFAULT_BACKGROUND_MUSIC = (
    MUSIC_FOLDER
    / "background_music.mp3"
)

RIGHTS_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# APPROVED VISUAL SOURCES
# ============================================================

APPROVED_SOURCES = {

    "PEXELS": {
        "licenses": {
            "pexels license",
        },
        "domains": {
            "pexels.com",
            "www.pexels.com",
            "videos.pexels.com",
            "images.pexels.com",
        },
    },

    "PIXABAY": {
        "licenses": {
            "pixabay content license",
            "pixabay license",
        },
        "domains": {
            "pixabay.com",
            "www.pixabay.com",
            "cdn.pixabay.com",
        },
    },

    "WIKIMEDIA": {
        "license_keywords": {
            "public domain",
            "cc0",
            "creative commons zero",
            "cc by",
            "cc-by",
            "cc by-sa",
            "cc-by-sa",
            "attribution",
        },
        "domains": {
            "commons.wikimedia.org",
            "upload.wikimedia.org",
        },
    },

    "THRAANSH": {
        "licenses": {
            "thraansh owned",
            "thraansh original",
        },
        "domains": set(),
    },
}


ALLOWED_MEDIA_TYPES = {
    "VIDEO",
    "IMAGE",
}


# ============================================================
# EDITORIAL-SENSITIVITY WORDS
# ============================================================

SENSITIVE_KEYWORDS = {
    "murder",
    "killed",
    "killing",
    "rape",
    "raped",
    "assault",
    "arrest",
    "arrested",
    "accused",
    "allegation",
    "alleged",
    "crime",
    "criminal",
    "fraud",
    "scam",
    "terror",
    "terrorist",
    "suicide",
    "death",
    "died",
    "dead",
    "crash",
    "victim",
    "hospitalised",
    "hospitalized",
}


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def safe_filename(value):

    value = clean_text(value)

    value = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        value
    )

    value = re.sub(
        r"\s+",
        "_",
        value
    )

    value = value.strip("._")

    if not value:
        value = "THRAANSH"

    return value[:100]


def normalize_source(value):

    return clean_text(value).upper()


def normalize_license(value):

    return clean_text(value).lower()


def get_domain(url):

    try:
        return (
            urlparse(url)
            .netloc
            .lower()
            .strip()
        )
    except Exception:
        return ""


def path_is_inside(child, parent):

    try:
        child.resolve().relative_to(
            parent.resolve()
        )
        return True
    except Exception:
        return False


# ============================================================
# QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        raise RuntimeError(
            f"Queue not found: {QUEUE_FILE}"
        )

    with open(
        QUEUE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if not isinstance(data, list):

        raise RuntimeError(
            "article_queue.json must contain a list."
        )

    return data


def save_queue(queue):

    with open(
        QUEUE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            queue,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# MUSIC REGISTRY
# ============================================================

def load_music_registry():

    if not MUSIC_REGISTRY_FILE.exists():

        return {
            "approved_music": []
        }

    try:

        with open(
            MUSIC_REGISTRY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, dict):

            return {
                "approved_music": []
            }

        return data

    except Exception:

        return {
            "approved_music": []
        }


def get_music_registry_entry(filename):

    registry = load_music_registry()

    entries = registry.get(
        "approved_music",
        []
    )

    if not isinstance(entries, list):
        return None

    filename_lower = filename.lower()

    for entry in entries:

        if not isinstance(entry, dict):
            continue

        registered_filename = clean_text(
            entry.get("filename")
        ).lower()

        if registered_filename == filename_lower:

            return entry

    return None


# ============================================================
# ARTICLE SELECTION
# ============================================================

def get_article(queue):

    # First prefer currently selected article.

    for article in reversed(queue):

        if not article.get(
            "production_selected"
        ):
            continue

        status = clean_text(
            article.get("status")
        ).upper()

        if status in {
            "VIDEO_READY",
            "RIGHTS_BLOCKED",
        }:
            return article

    # Fallback.

    for article in reversed(queue):

        status = clean_text(
            article.get("status")
        ).upper()

        if status in {
            "VIDEO_READY",
            "RIGHTS_BLOCKED",
        }:
            return article

    return None


# ============================================================
# SOURCE CHECK
# ============================================================

def validate_source(scene):

    source = normalize_source(
        scene.get("media_source")
    )

    if not source:

        return (
            False,
            "Missing media_source."
        )

    if source not in APPROVED_SOURCES:

        return (
            False,
            f"Unapproved source: {source}"
        )

    return (
        True,
        "Approved source."
    )


# ============================================================
# LICENSE CHECK
# ============================================================

def validate_license(scene):

    source = normalize_source(
        scene.get("media_source")
    )

    license_name = normalize_license(
        scene.get("license")
    )

    if not license_name:

        return (
            False,
            "Missing license."
        )

    policy = APPROVED_SOURCES.get(
        source,
        {}
    )

    exact_licenses = policy.get(
        "licenses",
        set()
    )

    if exact_licenses:

        if license_name not in exact_licenses:

            return (
                False,
                f"Unexpected {source} license: "
                f"{scene.get('license')}"
            )

        return (
            True,
            "License accepted."
        )

    keywords = policy.get(
        "license_keywords",
        set()
    )

    if keywords:

        if not any(
            keyword in license_name
            for keyword in keywords
        ):

            return (
                False,
                "License is not on "
                "the approved list."
            )

        return (
            True,
            "License accepted."
        )

    return (
        False,
        "No license policy exists."
    )


# ============================================================
# URL CHECK
# ============================================================

def validate_url(scene):

    source = normalize_source(
        scene.get("media_source")
    )

    url = clean_text(
        scene.get("media_url")
    )

    if source == "THRAANSH":

        return (
            True,
            "THRAANSH-owned media."
        )

    if not url:

        return (
            False,
            "Missing media_url."
        )

    domain = get_domain(url)

    if not domain:

        return (
            False,
            "Invalid media URL."
        )

    policy = APPROVED_SOURCES.get(
        source,
        {}
    )

    approved_domains = policy.get(
        "domains",
        set()
    )

    domain_ok = any(
        domain == allowed
        or domain.endswith(
            "." + allowed
        )
        for allowed in approved_domains
    )

    if not domain_ok:

        return (
            False,
            f"URL domain '{domain}' "
            f"does not match source '{source}'."
        )

    return (
        True,
        "Source URL verified."
    )


# ============================================================
# LOCAL FILE CHECK
# ============================================================

def validate_local_file(scene):

    file_value = clean_text(
        scene.get("footage_file")
    )

    if not file_value:

        return (
            False,
            "Missing footage_file."
        )

    path = Path(file_value)

    if not path.exists():

        return (
            False,
            f"Media file does not exist: {path}"
        )

    if not path.is_file():

        return (
            False,
            "footage_file is not a file."
        )

    if path.stat().st_size < 3000:

        return (
            False,
            "Media file is suspiciously small."
        )

    return (
        True,
        "Local media exists."
    )


# ============================================================
# DOWNLOAD VALIDATION
# ============================================================

def validate_download_flag(scene):

    if scene.get(
        "download_validated"
    ) is not True:

        return (
            False,
            "Media was not marked "
            "download_validated=True."
        )

    return (
        True,
        "Download validation confirmed."
    )


# ============================================================
# MEDIA TYPE
# ============================================================

def validate_media_type(scene):

    media_type = clean_text(
        scene.get("media_type")
    ).upper()

    if media_type not in ALLOWED_MEDIA_TYPES:

        return (
            False,
            f"Unsupported media type: "
            f"{media_type or 'MISSING'}"
        )

    return (
        True,
        f"{media_type} accepted."
    )



# ============================================================
# V3 VISUAL IDENTITY SAFETY - FAIL CLOSED
# ============================================================

def validate_visual_identity(scene):
    """
    V4 media generator must explicitly prove that every scene is safe for
    identity use. This prevents legacy/unverified named-person stock footage
    from passing the publishing gate.
    """
    safe = scene.get("visual_identity_safe")
    mode = clean_text(scene.get("visual_usage_mode")).upper()
    subject = clean_text(scene.get("identity_subject"))
    method = clean_text(scene.get("identity_verification_method")).upper()
    source = normalize_source(scene.get("media_source"))

    if safe is not True:
        return (
            False,
            "visual_identity_safe is not explicitly True."
        )

    if mode == "CONTEXTUAL_MEDIA":
        if method != "NOT_IDENTITY_MEDIA":
            return (
                False,
                "Contextual media must use NOT_IDENTITY_MEDIA verification."
            )
        if subject:
            return (
                False,
                "Contextual media must not claim an identity_subject."
            )
        return (
            True,
            "Contextual media explicitly marked identity-safe."
        )

    if mode == "EXACT_PERSON_VERIFIED_METADATA":
        if source != "WIKIMEDIA":
            return (
                False,
                "Exact-person metadata verification is only accepted from Wikimedia."
            )
        if not subject:
            return (
                False,
                "Exact-person media is missing identity_subject."
            )
        if method != "WIKIMEDIA_NAME_METADATA_MATCH":
            return (
                False,
                "Exact-person media lacks accepted Wikimedia metadata verification."
            )
        return (
            True,
            "Exact-person Wikimedia metadata verification accepted."
        )

    return (
        False,
        f"Unsupported or missing visual_usage_mode: {mode or 'MISSING'}"
    )


# ============================================================
# DUPLICATE MEDIA
# ============================================================

def check_duplicate_url(
    scene,
    used_urls
):

    url = clean_text(
        scene.get("media_url")
    )

    if not url:

        return (
            False,
            "Missing URL."
        )

    if url in used_urls:

        return (
            False,
            "Duplicate media URL detected."
        )

    used_urls.add(url)

    return (
        True,
        "Unique media URL."
    )


# ============================================================
# SENSITIVE STORY
# ============================================================

def sensitive_story(article):

    text = (
        clean_text(
            article.get("title")
        )
        + " "
        + clean_text(
            article.get("teaser")
        )
        + " "
        + clean_text(
            article.get("article_text")
        )
    ).lower()

    found = sorted(
        keyword
        for keyword in SENSITIVE_KEYWORDS
        if keyword in text
    )

    return found


# ============================================================
# BACKGROUND MUSIC RESOLUTION
# ============================================================

def resolve_background_music(article):

    raw_value = article.get(
        "background_music"
    )

    enabled = article.get(
        "background_music_enabled"
    )

    # Explicitly disabled.

    if enabled is False:
        return None

    # IMPORTANT FIX:
    # Existing renderer saved:
    #
    # background_music = True
    #
    # rather than a filename.
    #
    # In that case use our default file.

    if raw_value is True:

        return DEFAULT_BACKGROUND_MUSIC

    if raw_value is False:

        return None

    if isinstance(raw_value, str):

        value = clean_text(raw_value)

        if value:

            path = Path(value)

            if path.is_absolute():
                return path

            return (
                MUSIC_FOLDER
                / path.name
            )

    if enabled is True:

        return DEFAULT_BACKGROUND_MUSIC

    return None


# ============================================================
# MUSIC VALIDATION
# ============================================================

def validate_music(article):

    enabled = article.get(
        "background_music_enabled"
    )

    if enabled is False:

        return {
            "enabled": False,
            "passed": True,
            "reason": (
                "Background music disabled."
            ),
        }

    music_path = resolve_background_music(
        article
    )

    if music_path is None:

        return {
            "enabled": False,
            "passed": True,
            "reason": (
                "No background music configured."
            ),
        }

    try:

        resolved = music_path.resolve()

    except Exception:

        return {
            "enabled": True,
            "passed": False,
            "reason": (
                "Invalid music path."
            ),
        }

    if not resolved.exists():

        return {
            "enabled": True,
            "passed": False,
            "reason": (
                f"Music file missing: {resolved}"
            ),
        }

    if not path_is_inside(
        resolved,
        MUSIC_FOLDER
    ):

        return {
            "enabled": True,
            "passed": False,
            "reason": (
                "Music is outside "
                "approved music folder."
            ),
        }

    registry_entry = (
        get_music_registry_entry(
            resolved.name
        )
    )

    if registry_entry is None:

        return {
            "enabled": True,
            "passed": False,
            "reason": (
                "Music file is not listed "
                "in music_registry.json."
            ),
            "file": str(resolved),
        }

    if registry_entry.get(
        "approved"
    ) is not True:

        return {
            "enabled": True,
            "passed": False,
            "reason": (
                "Music registry entry "
                "is not approved."
            ),
            "file": str(resolved),
        }

    return {
        "enabled": True,
        "passed": True,
        "reason": (
            "Music file exists and is "
            "approved in music_registry.json."
        ),
        "file": str(resolved),
        "registry": registry_entry,
    }


# ============================================================
# FINAL VIDEO
# ============================================================

def validate_final_video(article):

    value = clean_text(
        article.get("final_video_file")
    )

    if not value:

        return (
            False,
            "Missing final_video_file."
        )

    path = Path(value)

    if not path.exists():

        return (
            False,
            "Final video does not exist."
        )

    if not path.is_file():

        return (
            False,
            "Final video path is invalid."
        )

    if path.stat().st_size < 100000:

        return (
            False,
            "Final video is suspiciously small."
        )

    return (
        True,
        "Final rendered video exists."
    )


# ============================================================
# CHECK ONE SCENE
# ============================================================

def check_scene(
    scene,
    index,
    used_urls
):

    checks = []

    passed = True

    validators = [
        (
            "source",
            validate_source
        ),
        (
            "license",
            validate_license
        ),
        (
            "source_url",
            validate_url
        ),
        (
            "local_file",
            validate_local_file
        ),
        (
            "download_validation",
            validate_download_flag
        ),
        (
            "media_type",
            validate_media_type
        ),
        (
            "visual_identity_safety",
            validate_visual_identity
        ),
    ]

    for name, validator in validators:

        result, reason = validator(
            scene
        )

        checks.append(
            {
                "check": name,
                "passed": result,
                "reason": reason,
            }
        )

        if not result:
            passed = False

    duplicate_result, duplicate_reason = (
        check_duplicate_url(
            scene,
            used_urls
        )
    )

    checks.append(
        {
            "check": "duplicate_url",
            "passed": duplicate_result,
            "reason": duplicate_reason,
        }
    )

    if not duplicate_result:
        passed = False

    return {
        "scene_number": (
            scene.get("scene_number")
            or index
        ),
        "passed": passed,
        "media_type": clean_text(
            scene.get("media_type")
        ),
        "source": clean_text(
            scene.get("media_source")
        ),
        "license": clean_text(
            scene.get("license")
        ),
        "source_url": clean_text(
            scene.get("media_url")
        ),
        "local_file": clean_text(
            scene.get("footage_file")
        ),
        "search_query": clean_text(
            scene.get("search_query_used")
        ),
        "artist": clean_text(
            scene.get("artist")
        ),
        "visual_identity_safe": scene.get("visual_identity_safe"),
        "visual_usage_mode": clean_text(scene.get("visual_usage_mode")),
        "identity_subject": clean_text(scene.get("identity_subject")),
        "identity_verification_method": clean_text(
            scene.get("identity_verification_method")
        ),
        "checks": checks,
    }


# ============================================================
# RIGHTS MANIFEST
# ============================================================

def save_manifest(
    article,
    manifest
):

    title = safe_filename(
        article.get("title")
    )

    path = (
        RIGHTS_FOLDER
        / f"{title}_RIGHTS.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            manifest,
            file,
            indent=2,
            ensure_ascii=False
        )

    return path


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 78)

    print(
        "THRAANSH RIGHTS / COPYRIGHT PREFLIGHT V3"
    )

    print("=" * 78)

    print()
    print("Policy: FAIL CLOSED ✓")
    print("Unknown source: BLOCK ✓")
    print("Missing license: BLOCK ✓")
    print("Missing URL: BLOCK ✓")
    print("Unvalidated media: BLOCK ✓")
    print("Duplicate media: BLOCK ✓")
    print("Unregistered music: BLOCK ✓")
    print("Unsafe/unverified visual identity: BLOCK ✓")

    try:

        queue = load_queue()

    except Exception as error:

        print()
        print("QUEUE ERROR:")
        print(error)

        sys.exit(1)

    article = get_article(queue)

    if article is None:

        print()
        print(
            "No VIDEO_READY or RIGHTS_BLOCKED "
            "article is available."
        )

        sys.exit(0)

    title = clean_text(
        article.get("title")
    )

    print()
    print("ARTICLE:")
    print(title)

    scenes = article.get(
        "scene_plan",
        []
    )

    if not isinstance(scenes, list):
        scenes = []

    print()
    print(
        "Scenes:",
        len(scenes)
    )

    overall_pass = True

    blockers = []

    warnings = []

    used_urls = set()

    scene_results = []

    # ========================================================
    # FINAL VIDEO CHECK
    # ========================================================

    (
        final_video_pass,
        final_video_reason
    ) = validate_final_video(
        article
    )

    if not final_video_pass:

        overall_pass = False

        blockers.append(
            final_video_reason
        )

    # ========================================================
    # SCENE CHECKS
    # ========================================================

    if not scenes:

        overall_pass = False

        blockers.append(
            "No scene plan exists."
        )

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        print()
        print("-" * 60)

        print(
            f"SCENE {index}"
        )

        result = check_scene(
            scene,
            index,
            used_urls
        )

        scene_results.append(
            result
        )

        print(
            "Source:",
            result["source"]
            or "MISSING"
        )

        print(
            "License:",
            result["license"]
            or "MISSING"
        )

        for check in result["checks"]:

            status_text = (
                "PASS"
                if check["passed"]
                else "FAIL"
            )

            print(
                f"{check['check']}: "
                f"{status_text}"
            )

            if not check["passed"]:

                print(
                    "  Reason:",
                    check["reason"]
                )

        if not result["passed"]:

            overall_pass = False

            blockers.append(
                f"Scene {index} "
                f"failed rights validation."
            )

    # ========================================================
    # MUSIC CHECK
    # ========================================================

    music_result = validate_music(
        article
    )

    print()
    print("-" * 60)

    print("BACKGROUND MUSIC")

    print(
        "PASS"
        if music_result["passed"]
        else "FAIL"
    )

    print(
        music_result["reason"]
    )

    if music_result.get("file"):

        print(
            "File:",
            music_result["file"]
        )

    if not music_result["passed"]:

        overall_pass = False

        blockers.append(
            music_result["reason"]
        )

    # ========================================================
    # EDITORIAL WARNING
    # ========================================================

    sensitive_words = sensitive_story(
        article
    )

    if sensitive_words:

        warning = (
            "Sensitive-story terms detected: "
            + ", ".join(sensitive_words)
            + ". Generic stock people must not "
            + "be presented as the actual accused, "
            + "suspect, victim or subject."
        )

        warnings.append(
            warning
        )

    # ========================================================
    # FINAL STATUS
    # ========================================================

    checked_at = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    status = (
        "RIGHTS_PASS"
        if overall_pass
        else "RIGHTS_BLOCKED"
    )

    manifest = {
        "article_id": article.get("id"),
        "title": title,
        "publisher": article.get("publisher"),
        "article_url": article.get("url"),
        "final_video_file": article.get(
            "final_video_file"
        ),
        "checked_at": checked_at,
        "policy": "THRAANSH_FAIL_CLOSED_V3_IDENTITY_SAFE",
        "rights_status": status,
        "final_video_check": {
            "passed": final_video_pass,
            "reason": final_video_reason,
        },
        "scene_count": len(scenes),
        "scenes": scene_results,
        "background_music": music_result,
        "warnings": warnings,
        "blockers": blockers,
        "important_notice": (
            "This preflight verifies configured "
            "source and license records. It does "
            "not guarantee that a platform will "
            "never issue a copyright, Content ID, "
            "trademark, privacy, publicity or "
            "other rights claim."
        ),
    }

    manifest_path = save_manifest(
        article,
        manifest
    )

    # ========================================================
    # UPDATE ARTICLE QUEUE
    # ========================================================

    article["rights_status"] = status

    article["rights_checked_at"] = (
        checked_at
    )

    article["rights_manifest_file"] = (
        str(manifest_path)
    )

    article["rights_blockers"] = (
        blockers
    )

    article["rights_warnings"] = (
        warnings
    )

    article["updated_at"] = (
        checked_at
    )

    if overall_pass:

        article["status"] = (
            "RIGHTS_PASS"
        )

        article["last_error"] = None

    else:

        article["status"] = (
            "RIGHTS_BLOCKED"
        )

        article["last_error"] = (
            "Rights preflight failed."
        )

    save_queue(queue)

    # ========================================================
    # DISPLAY RESULT
    # ========================================================

    print()
    print("=" * 78)

    if overall_pass:

        print(
            "RIGHTS CHECK PASSED ✓"
        )

        print("=" * 78)

        print()
        print(
            "VIDEO_READY / RIGHTS_BLOCKED "
            "-> RIGHTS_PASS"
        )

        print()
        print(
            "Publishing gate: OPEN ✓"
        )

    else:

        print(
            "RIGHTS CHECK BLOCKED ✗"
        )

        print("=" * 78)

        print()
        print(
            "Status -> RIGHTS_BLOCKED"
        )

        print()
        print(
            "Publishing gate: CLOSED ✗"
        )

        print()
        print("BLOCKERS:")

        for blocker in blockers:

            print(
                "-",
                blocker
            )

    if warnings:

        print()
        print(
            "EDITORIAL WARNINGS:"
        )

        for warning in warnings:

            print(
                "-",
                warning
            )

    print()
    print(
        "Rights manifest:"
    )

    print(
        manifest_path
    )

    print()

    if not overall_pass:

        sys.exit(2)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
