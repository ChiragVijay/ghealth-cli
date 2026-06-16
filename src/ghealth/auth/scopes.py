SCOPE_ALIASES = {
    "cloud-platform": "https://www.googleapis.com/auth/cloud-platform",
    "activity_and_fitness.readonly": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "activity_and_fitness.writeonly": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.writeonly",
    "ecg.readonly": "https://www.googleapis.com/auth/googlehealth.ecg.readonly",
    "health_metrics_and_measurements.readonly": "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "health_metrics_and_measurements.writeonly": "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    "irn.readonly": "https://www.googleapis.com/auth/googlehealth.irn.readonly",
    "location.readonly": "https://www.googleapis.com/auth/googlehealth.location.readonly",
    "location.writeonly": "https://www.googleapis.com/auth/googlehealth.location.writeonly",
    "nutrition.readonly": "https://www.googleapis.com/auth/googlehealth.nutrition.readonly",
    "nutrition.writeonly": "https://www.googleapis.com/auth/googlehealth.nutrition.writeonly",
    "profile.readonly": "https://www.googleapis.com/auth/googlehealth.profile.readonly",
    "profile.writeonly": "https://www.googleapis.com/auth/googlehealth.profile.writeonly",
    "settings.readonly": "https://www.googleapis.com/auth/googlehealth.settings.readonly",
    "settings.writeonly": "https://www.googleapis.com/auth/googlehealth.settings.writeonly",
    "sleep.readonly": "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    "sleep.writeonly": "https://www.googleapis.com/auth/googlehealth.sleep.writeonly",
}

SCOPE_MAPPINGS = {
    "activity": {
        "read": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
        "write": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.writeonly",
    },
    "sleep": {
        "read": "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
        "write": "https://www.googleapis.com/auth/googlehealth.sleep.writeonly",
    },
    "nutrition": {
        "read": "https://www.googleapis.com/auth/googlehealth.nutrition.readonly",
        "write": "https://www.googleapis.com/auth/googlehealth.nutrition.writeonly",
    },
    "metrics": {
        "read": "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
        "write": "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    },
    "location": {
        "read": "https://www.googleapis.com/auth/googlehealth.location.readonly",
        "write": "https://www.googleapis.com/auth/googlehealth.location.writeonly",
    },
    "ecg": {"read": "https://www.googleapis.com/auth/googlehealth.ecg.readonly"},
    "irn": {"read": "https://www.googleapis.com/auth/googlehealth.irn.readonly"},
}

AUTH_STATUS_IDENTITY_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# Scope profiles mapped to list of full scope URLs
SCOPE_PROFILES = {
    "readonly": [
        "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
        "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
        "https://www.googleapis.com/auth/googlehealth.nutrition.readonly",
        "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
        "https://www.googleapis.com/auth/googlehealth.location.readonly",
        "https://www.googleapis.com/auth/googlehealth.ecg.readonly",
        "https://www.googleapis.com/auth/googlehealth.irn.readonly",
        "https://www.googleapis.com/auth/googlehealth.profile.readonly",
        "https://www.googleapis.com/auth/googlehealth.settings.readonly",
    ],
    "all-read": [
        "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
        "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
        "https://www.googleapis.com/auth/googlehealth.nutrition.readonly",
        "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
        "https://www.googleapis.com/auth/googlehealth.location.readonly",
        "https://www.googleapis.com/auth/googlehealth.ecg.readonly",
        "https://www.googleapis.com/auth/googlehealth.irn.readonly",
        "https://www.googleapis.com/auth/googlehealth.profile.readonly",
        "https://www.googleapis.com/auth/googlehealth.settings.readonly",
    ],
    "activity": ["https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly"],
    "sleep": ["https://www.googleapis.com/auth/googlehealth.sleep.readonly"],
    "nutrition": ["https://www.googleapis.com/auth/googlehealth.nutrition.readonly"],
    "metrics": [
        "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    ],
    "write": [
        "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.writeonly",
        "https://www.googleapis.com/auth/googlehealth.sleep.writeonly",
        "https://www.googleapis.com/auth/googlehealth.nutrition.writeonly",
        "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
        "https://www.googleapis.com/auth/googlehealth.location.writeonly",
        "https://www.googleapis.com/auth/googlehealth.profile.writeonly",
        "https://www.googleapis.com/auth/googlehealth.settings.writeonly",
    ],
}


def get_scopes_for_login(scope_profile: str | None = None, scopes_str: str | None = None) -> list[str]:
    """Parse and return scope URLs based on options."""
    expanded = []
    if scope_profile or not scopes_str:
        profile = scope_profile or "readonly"
        if profile not in SCOPE_PROFILES:
            msg = f"Unknown scope profile '{profile}'."
            raise ValueError(msg)
        expanded = SCOPE_PROFILES[profile].copy()

    if scopes_str:
        parts = [p.strip() for p in scopes_str.split(",") if p.strip()]
        for p in parts:
            if p in SCOPE_ALIASES:
                expanded.append(SCOPE_ALIASES[p])
            elif p.startswith("https://"):
                expanded.append(p)
            else:
                expanded.append(f"https://www.googleapis.com/auth/googlehealth.{p}")

    expanded = list(dict.fromkeys(expanded))

    for scope in AUTH_STATUS_IDENTITY_SCOPES:
        if scope not in expanded:
            expanded.append(scope)

    return expanded
