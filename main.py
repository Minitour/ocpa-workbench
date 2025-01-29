import pandas as pd
import streamlit as st
from ocpa.objects.log.importer.csv.util import clean_normalized_frequency
from ocpa.objects.log.importer.ocel2.xml import factory as ocel_import_factory
from ocpa.objects.log.ocel import OCEL
from streamlit_modal import Modal
from streamlit_tags import st_tags

from app import utils
from app.models import Cases, Variant
from app.utils import safe_execute


@st.cache_data
def load_ocel(file):
    reset_states()
    file_path = utils.get_local_file(file)
    ocel = ocel_import_factory.apply(str(file_path))
    ocel.log.log.sort_values('event_timestamp', inplace=True)
    cases = Cases(ocel)
    df_copy = pd.DataFrame(ocel.log.log)
    return ocel, cases, df_copy


def get_traces_handler(object_type: str, variant: Variant):
    st.session_state.selected_variant = variant
    st.session_state.object_type = object_type


def close_modal_handler(rerun_condition=True):
    st.session_state.selected_variant = None
    st.session_state.object_type = None
    st.session_state[f'traces-modal-opened'] = False
    if rerun_condition:
        st.rerun()


def get_petri_net_handler(ocel: OCEL):
    if ocel is None:
        return
    st.session_state.petri_net_graph = utils.get_petri_net(
        ocel,
        include_object_types=st.session_state.selected_object_types,
        activity_filter=st.session_state.activity_filter
    )


def get_variants_handler(ocel: OCEL, cases: Cases):
    if ocel is None:
        return
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


# component
def variants_component():
    variants = st.session_state.variants
    if variants is None:
        return

    tabs = st.tabs(list(variants.keys()))
    for tab, object_type in zip(tabs, variants.keys()):
        with (tab):
            for variant in variants[object_type]:
                key = f"{object_type}_{variant.trace.get_trace_hash()}"
                col1, col2, col3 = st.columns([1, 4, 1])
                with col1:
                    st.progress(variant.percentage, text=f"{variant.count} traces")
                with col2:
                    # st.write(" ➔ ".join([f'[{event.activity}]' for event in variant.trace]))
                    st.graphviz_chart(variant.trace.directly_follows_graph(), use_container_width=True)
                with col3:
                    st.button(
                        "See Traces",
                        args=(object_type, variant,),
                        on_click=get_traces_handler, type="primary",
                        key=f"btn_{key}"
                    )
                st.divider()


@safe_execute
def reset_states():
    states = [
        'selected_object_types',
        'selected_object_instances',
        'selected_variant',
        'object_type',
        'available_object_types',
        'petri_net_graph',
        'variants'
    ]

    for state in states:
        if utils.safe_get(st.session_state, state):
            st.session_state[state] = None


# filter
@safe_execute
def apply_filters(dataframe_pointer):
    """
    Apply filters on dataframe from session state.
    """
    if selected_object_types := utils.safe_get(st.session_state, 'selected_object_types'):
        dataframe_pointer.drop(
            dataframe_pointer[~dataframe_pointer[selected_object_types].any(axis=1)].index, inplace=True
        )
    if selected_object_instances := utils.safe_get(st.session_state, 'selected_object_instances'):
        def contains_selected_value(row):
            return any(
                any(val in selected_object_instances for val in (cell if isinstance(cell, list) else [cell]))
                for cell in row
            )

        dataframe_pointer.drop(
            dataframe_pointer[~dataframe_pointer.apply(contains_selected_value, axis=1)].index,
            inplace=True
        )
    if activity_filter := utils.safe_get(st.session_state, 'activity_filter'):
        to_keep = clean_normalized_frequency(
            dataframe_pointer.reset_index(drop=True),
            float(1 - activity_filter / 100)
        ).set_index("event_id")

        dataframe_pointer.drop(
            index=dataframe_pointer[~dataframe_pointer.index.isin(to_keep.index)].index,
            inplace=True
        )


def main():
    # Streamlit app
    st.set_page_config(page_title="OCPA Workbench", page_icon=":material/sync_alt:", layout="wide")
    st.title("OCPA Workbench")

    # Set states
    if 'selected_variant' not in st.session_state:
        st.session_state.selected_variant = None
    if 'object_type' not in st.session_state:
        st.session_state.object_type = None
    if 'available_object_types' not in st.session_state:
        st.session_state.available_object_types = []
    if 'petri_net_graph' not in st.session_state:
        st.session_state.petri_net_graph = None
    if 'variants' not in st.session_state:
        st.session_state.variants = None

    file = st.file_uploader("Upload a new Log:", type="xml")

    if not file:
        return

    # Prepare Data
    ocel, cases, original_dataframe = load_ocel(file)
    dataframe_pointer = ocel.log.log
    st.session_state.available_object_types = list(ocel.log.object_types)

    # Apply Filters
    apply_filters(dataframe_pointer)
    cases.reload()

    # Log Settings
    st.subheader("Log Settings")
    col1, col2, col3 = st.columns([5, 1, 2])
    with col1:
        # Show dataframe
        st.text(f"Showing {ocel.log.log.shape[0] if ocel else 0} events")
        st.dataframe(
            utils.convert_dataframe_to_strings(dataframe_pointer) if ocel else pd.DataFrame(),
            column_config={
                'event_timestamp': st.column_config.DatetimeColumn()
            },
            use_container_width=True,
            hide_index=True
        )
    with col2:
        st.text('Object statistics')
        st.dataframe(
            pd.DataFrame(
                [
                    {'type': k, 'value': v}
                    for k, v in cases.unique_object_count().items()
                ]
            ),
            column_config={
                'type': st.column_config.TextColumn(label='Object Type'),
                'value': st.column_config.NumberColumn('Count', format='%d')
            },
            hide_index=True,
            use_container_width=True
        )

    with col3:
        st.multiselect(
            "Filter by object type",
            options=st.session_state.available_object_types or [],
            default=st.session_state.available_object_types or [],
            key="selected_object_types"
        )

        st_tags(
            label='Filter by object identifier', text='Press enter to add more',
            value=[],
            suggestions=list(cases.objects if cases else []),
            key='selected_object_instances'
        )
        st.slider(
            "Activity Importance Filter",
            min_value=1,
            max_value=100,
            value=100,
            key="activity_filter",
            help="Filter out activities based on frequency"
        )
        st.slider(
            "Variant Filter",
            min_value=1,
            max_value=100,
            value=95,
            key="variant_filter",
            help="Filter out variants"
        )

    # Body Layout
    col_left, col_right = st.columns([3, 2])

    # Left Side: Petri Net Visualization
    with col_left:
        st.subheader("Object-Centric Petri Net")
        st.button(
            "Discover Petri net",
            args=(ocel,),
            on_click=get_petri_net_handler,
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

        # Variant Explorer
        st.subheader("Variant Explorer")
        st.button(
            "Discover Variants",
            args=(ocel, cases,),
            on_click=get_variants_handler,
            type="primary",
            disabled=ocel is None
        )

        if st.session_state.variants:
            variants_component()

    modal = Modal("Traces", key="traces-modal", max_width=1000)
    if st.session_state.selected_variant and st.session_state.object_type:
        modal.close = close_modal_handler
        traces = cases.get_traces_by_variant(st.session_state.object_type, st.session_state.selected_variant)[:100]
        with modal.container():
            st.write('Showing first 100 traces')
            for trace in traces:
                data = [{'activity': event.activity, 'timestamp': event.timestamp, **event.objects} for event in trace]
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.divider()
        if not modal.is_open:
            modal.open()


if __name__ == "__main__":
    main()
