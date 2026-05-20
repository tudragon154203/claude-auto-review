from pathlib import Path


def resolve_rules_file_path(project_root, settings):
    rules_path = Path(settings.rules_file)
    if rules_path.is_absolute():
        return rules_path
    return Path(project_root) / rules_path
