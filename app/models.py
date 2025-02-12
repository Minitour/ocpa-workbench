from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from ocpa.objects.log.ocel import OCEL


@dataclass
class Event:
    """
    Represents an event in a process.
    
    The `Event` class is a data structure that encapsulates the details of a process
    event, including its activity name, timestamp, and the associated objects.
    It is used as a fundamental unit to describe the behavior of processes in an OCEL
    (Object-Centric Event Log).
    """
    activity: str
    timestamp: datetime
    objects: dict[str, list[str]]


class Trace(list):
    """
    Represents a sequence of events (a trace) in a process.

    The `Trace` class extends the built-in `list` class and is used to store
    a series of events, typically representing a single execution or instance
    of a process flow. It includes methods for generating unique hashes for
    the trace, creating a directly follows graph representation in Graphviz
    syntax, and comparing traces.
    """

    def get_trace_hash(self):
        return hash(tuple([e.activity for e in self]))

    def get_case_hash(self):
        return hash(tuple((e.activity, frozenset((k, tuple(v)) for k, v in e.objects.items())) for e in self))

    def directly_follows_graph(self, include_objects=False) -> str:
        events = self
        if len(events) == 1:
            return f'digraph G {{\n    rankdir=LR;\n    "{events[0].activity}" [label="{events[0].activity}", shape=rect];\n}}'

            # Create a set of unique edges for the directly follows relationships
        edges = set()
        for i in range(len(events) - 1):
            source_id = f"{events[i].activity}_{i}"
            target_id = f"{events[i + 1].activity}_{i + 1}"
            label = ""
            if include_objects:
                object_descriptions = [f"{key}: {value}" for key, value in events[i + 1].objects.items()]
                label = " [label=\"" + ", ".join(object_descriptions) + "\"]"
            edges.add(f'    "{source_id}" -> "{target_id}"{label};')

        # Generate nodes with unique IDs but display original activity names
        nodes = set(f'    "{f"{event.activity}_{i}"}" [label="{event.activity}", shape=rect];' for i, event in
                    enumerate(events))

        # Generate the Graphviz syntax with left-to-right layout
        graph = "digraph G {\n    rankdir=LR;\n" + "\n".join(nodes) + "\n" + "\n".join(edges) + "\n}"
        return graph

    def __hash__(self):
        return self.get_case_hash()

    def __eq__(self, other):
        if not isinstance(other, Trace):
            return False
        return self.get_case_hash() == other.get_case_hash()


@dataclass
class Variant:
    """
    Represents a variant with associated trace, percentage, and count.

    This class is used to encapsulate the details of a specific variant,
    including its trace information, a percentage value (typically representing
    a relative metric), and a count (representing occurrences or instances).
    """
    trace: Trace
    percentage: float = 0.0
    count: int = 0


def _default_dict_of(dtype):
    def func():
        return defaultdict(dtype)

    return func


def _default_dict_of_trace():
    return defaultdict(Trace)


def _default_dict_of_list():
    return defaultdict(list)


class Cases:
    """
    Represents cases in an Object-Centric Event Log (OCEL).

    The `Cases` class is responsible for managing and analyzing cases extracted
    from an OCEL. It processes events to group them by associated objects, generates
    variants based on traces, and provides insights like unique object counts,
    object collections by variants, and traces by variants.
    """

    def __init__(self, ocel: OCEL):
        self._ocel = ocel
        self.cases_by_object = None
        self._variants = None  # dict of list of variant
        self._variant_count = None  # dict of dict of Trace
        self._objects = None

    def reload(self):
        self.cases_by_object = defaultdict(_default_dict_of(Trace))
        self._objects = set()
        events = self._dataframe_to_events(self._ocel.log.log)
        for event in events:
            for object_type, object_name in event.objects.items():
                for value in object_name:
                    self.cases_by_object[object_type][value].append(event)
                    self._objects.add(value)

        self._variant_count = defaultdict(_default_dict_of(set))
        for object_type, object_name in self.cases_by_object.items():
            for key, value in object_name.items():
                # key is the object id
                # value is the list of events (Trace)
                self._variant_count[object_type][value.get_trace_hash()].add(value)

        variants = defaultdict(list)
        for object_type, type_variants in self._variant_count.items():
            total = sum([len(variant) for variant in type_variants.values()])
            for key, value in type_variants.items():
                variant = Variant(
                    trace=list(value)[0],
                    percentage=len(value) / total,
                    count=len(value)
                )
                variants[object_type].append(variant)
        self._variants = variants

    @property
    def variants(self):
        return self._variants

    @property
    def objects(self):
        return self._objects

    @property
    def unique_values(self):
        def extract_values(item):
            """Recursively extracts unique values from nested structures."""
            if isinstance(item, (list, set, tuple)):
                extracted = set()
                for subitem in item:
                    extracted.update(extract_values(subitem))
                return extracted
            return {item}

        unique_values = set()
        for value in self._ocel.log.log.values.flatten():
            unique_values.update(extract_values(value) if isinstance(value, (list, set, tuple)) else {value})
        return unique_values

    def unique_object_count(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.cases_by_object.items()}

    def get_traces_by_variant(self, object_type: str, variant: Variant) -> list[Trace]:
        return list(self._variant_count[object_type][variant.trace.get_trace_hash()])

    def get_objects_by_variant(self, variant: Variant):
        objects = defaultdict(set)
        for object_type, type_variant in self._variant_count.items():
            for trace in type_variant.get(variant.trace.get_trace_hash(), []):
                for event in trace:
                    objects[object_type].update(event.objects[object_type])
        return objects

    @staticmethod
    def _dataframe_to_events(df: pd.DataFrame) -> list[Event]:
        events = []
        for _, row in df.sort_values('event_timestamp', inplace=False).iterrows():
            objects = {col: row[col] for col in df.columns if
                       not col.startswith('event_') and row[col]}
            event = Event(
                activity=row['event_activity'],
                timestamp=row['event_timestamp'],
                objects=objects
            )
            events.append(event)
        return events
