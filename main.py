import streamlit as st
from ocpa.objects.log.importer.ocel2.xml import factory as ocel_import_factory
from ocpa.objects.log.ocel import OCEL
from st_circular_progress import CircularProgress

from app import utils
from app.models import Cases


@st.cache_data
def load_ocel(file):
    file_path = utils.get_local_file(file)
    ocel = ocel_import_factory.apply(str(file_path))
    return ocel


def cases_from_ocel(ocel: OCEL):
    cases = Cases(ocel)
    return cases


def compute_petri_net(ocel: OCEL):
    if ocel is None:
        return
    st.session_state.petri_net_graph = utils.get_petri_net(
        ocel,
        include_object_types=st.session_state.selected_object_types,
        activity_filter=st.session_state.activity_filter
    )


def compute_variants(ocel: OCEL):
    if ocel is None:
        return
    cases = Cases(ocel)
    variants = cases.variants

    variant_keys = (
        {key for key in variants.keys() if key in st.session_state.selected_object_types}
        if st.session_state.selected_object_types
        else variants.keys()
    )

    variants_sorted = {
        key: sorted(
            filter(
                lambda variant: (variant.percentage * 100) >= (100 - st.session_state.variant_filter),
                variant_items,
            ),
            key=lambda item: item.percentage,
            reverse=True
        )
        for key, variant_items in variants.items()
        if key in variant_keys
    }

    st.session_state.variants = variants_sorted


def component_from_variants():
    variants = st.session_state.variants
    if variants is None:
        return

    tabs = st.tabs(list(variants.keys()))
    for tab, object_type in zip(tabs, variants.keys()):
        with (tab):
            for variant in variants[object_type]:
                progress_col, trace_col = st.columns([1, 10])

                with progress_col:
                    bar = CircularProgress(
                        label="",
                        size="small",
                        value=int(variant.percentage * 100),
                        color="#007aff",
                        key=f"{object_type}_{variant.trace.get_trace_hash()}"
                    )
                    bar.st_circular_progress()
                with trace_col:
                    # html_trace = "<nav style='display: inline-block; white-space: nowrap; font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 8px; border-radius: 4px; border: 1px solid #ddd;'>" + " ➔ ".join(
                    #     [f"<span style='color: #007bff; text-decoration: none; padding: 0 4px;'>{event.activity}</span>"
                    #      for event in variant.trace]) + "</nav>"
                    # st.markdown(html_trace, unsafe_allow_html=True)
                    for _ in range(4):
                        st.text('')
                    st.markdown(" ➔ ".join([f'[{event.activity}]' for event in variant.trace]))

                st.divider()


def on_selected_object_types_changed():
    print(st.session_state.selected_object_types)


def main():
    # Streamlit app
    st.set_page_config(layout="wide")
    st.title("OCPA Workbench")

    if 'available_object_types' not in st.session_state:
        st.session_state.available_object_types = []
    if 'petri_net_graph' not in st.session_state:
        st.session_state.petri_net_graph = None
    if 'variants' not in st.session_state:
        st.session_state.variants = None

    # Top Bar
    file = st.file_uploader("Upload a new Log:", type="xml")

    ocel = None
    if file:
        ocel = load_ocel(file)
        st.session_state.available_object_types = list(ocel.log.object_types)
    # Body Layout
    col_left, col_right = st.columns([3, 2])

    # Left Side: Petri Net Visualization
    with col_left:
        st.subheader("Object-Centric Petri Net")
        st.button(
            "Discover Petri net",
            args=(ocel,),
            on_click=compute_petri_net,
            type="primary",
            disabled=ocel is None

        )

        if st.session_state.petri_net_graph:
            st.graphviz_chart(
                st.session_state.petri_net_graph,
                use_container_width=True
            )

    # Right Side: Variant Explorer
    with col_right:
        st.subheader("Log Settings")

        st.multiselect(
            "Selected Object Types:",
            options=st.session_state.available_object_types,
            default=st.session_state.available_object_types,
            key="selected_object_types"
        )

        st.slider("Activity Filter", 0, 100, value=100, key="activity_filter")
        st.slider("Variant Filter", 0, 100, value=95, key="variant_filter")

        # Variant Explorer
        st.subheader("Variant Explorer")
        st.button(
            "Discover Variants",
            args=(ocel,),
            on_click=compute_variants,
            type="primary",
            disabled=ocel is None
        )

        if st.session_state.variants:
            component_from_variants()


if __name__ == "__main__":
    main()
