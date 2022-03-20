import pathlib

SALTEXT_DIR = pathlib.Path(__file__).resolve().parent


def get_engines_dirs():
    """
    Return a list of directories for Salt to look for engine extensions.
    """
    return [str(SALTEXT_DIR / "engines")]


def get_log_handlers_dirs():
    """
    Return a list of directories for Salt to look for log handlers extensions.
    """
    return [str(SALTEXT_DIR / "log_handlers")]
