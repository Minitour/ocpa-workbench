import tempfile
from pathlib import Path

from ocpa.objects.log.ocel import OCEL
from streamlit.runtime.uploaded_file_manager import UploadedFile
from ocpa.algo.discovery.ocpn import algorithm as ocpn_discovery_factory
from ocpa.visualization.oc_petri_net import factory as ocpn_vis_factory

temp_dir = tempfile.TemporaryDirectory()


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
    print(include_object_types)
    petri_net = ocpn_discovery_factory.apply(
        ocel,
        parameters={
            "debug": False,
            'include_object_types': include_object_types,
            'activity_threshold': float(1 - activity_filter / 100),
        }
    )

    # create graphiz Digraph object
    petri_net_graph = ocpn_vis_factory.apply(petri_net, parameters={"bgcolor": 'white'})
    return petri_net_graph


def get_object_types(ocel: OCEL):
    return ocel.log.object_types
