import tempfile
from pathlib import Path

import pandas as pd
from ocpa.objects.log.ocel import OCEL
from streamlit.runtime.uploaded_file_manager import UploadedFile
from ocpa.algo.discovery.ocpn import algorithm as ocpn_discovery_factory
from ocpa.visualization.oc_petri_net import factory as ocpn_vis_factory

temp_dir = tempfile.TemporaryDirectory()


def safe_get(session, attr: str):
    try:
        return session[attr]
    except:
        return None


def safe_execute(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            return None

    return wrapper


def get_local_file(file: UploadedFile | None) -> Path | None:
    """
    Get local file path from uploaded file. This uploads the file into a temp directory and returns the local path.
    """

    if file is None:
        return None

    uploaded_file_path = Path(temp_dir.name) / file.name
    with open(uploaded_file_path, 'wb') as output_temporary_file:
        output_temporary_file.write(file.read())
    return uploaded_file_path


def get_petri_net(ocel: OCEL, include_object_types: list[str] = None, activity_filter: int = 100):
    petri_net = ocpn_discovery_factory.apply(
        ocel,
        parameters={
            "debug": False,
            'include_object_types': include_object_types
        }
    )

    # create graphiz Digraph object
    petri_net_graph = ocpn_vis_factory.apply(petri_net)
    return petri_net_graph


def get_object_types(ocel: OCEL):
    return ocel.log.object_types


def convert_dataframe_to_strings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts all data types in a DataFrame to strings.
    If a value is a list, it joins the elements using commas.

    Args:
        df (pd.DataFrame): The input DataFrame.

    Returns:
        pd.DataFrame: The DataFrame with all values converted to strings.
    """

    def convert_value(value):
        if isinstance(value, list):
            return ','.join(map(str, value))
        return str(value)

    # Apply the conversion to the entire DataFrame
    return df.map(convert_value)
