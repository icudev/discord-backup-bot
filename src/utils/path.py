import os

PROJECT_DIR = os.path.abspath(__file__).replace(
    os.path.normpath("src/utils/path.py"), ""
)


def get_path(path_after_project_dir: str) -> str:
    """Converts a short path inside the project dir to a full path

    Parameters
    ----------
    path_after_project_dir: str
        The path inside of the project dir that you want to extend

    Returns
    -------
    str
        The full path
    """

    return PROJECT_DIR + os.path.normpath(path_after_project_dir)
