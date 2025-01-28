import pandas as pd
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
            data = [
                {
                    'percentage': variant.percentage * 100,
                    'count': variant.count,
                    'text': " ➔ ".join([f'[{event.activity}]' for event in variant.trace])
                }
                for variant in variants[object_type]
            ]
            st.dataframe(
                pd.DataFrame(data),
                column_config={
                    'percentage': st.column_config.ProgressColumn(
                        format="%.2f%%", width='small', label='Percentage', min_value=0, max_value=100
                    ),
                    'count': st.column_config.NumberColumn(width='small', label='Count'),
                    'text': st.column_config.TextColumn(width='large', label='Trace')
                },
                hide_index=True,
                use_container_width=True
            )


def main():
    # Streamlit app
    st.set_page_config(page_title="OCPA Workbench", page_icon=":material/sync_alt:", layout="wide")
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

    if ocel:
        with st.expander(f"Show raw logs ({ocel.log.log.shape[0]} events)"):
            st.dataframe(
                utils.convert_dataframe_to_strings(ocel.log.log),
                column_config={
                    'event_timestamp': st.column_config.DatetimeColumn()
                },
                use_container_width=True,
                hide_index=True
            )

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
