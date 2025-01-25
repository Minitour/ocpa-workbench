from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from ocpa.objects.log.ocel import OCEL


@dataclass
class Event:
    activity: str
    timestamp: datetime
    objects: dict[str, list[str]]


class Trace(list):

    def get_trace_hash(self):
        return hash(tuple([e.activity for e in self]))


@dataclass
class Variant:
    trace: Trace
    percentage: float = 0.0
    count: int = 0


class Cases:

    def __init__(self, ocel: OCEL):
        self.cases = defaultdict(lambda: defaultdict(Trace))
        self._variants = None
        self._variant_count = None

        events = self._dataframe_to_events(ocel.log.log)
        for event in events:
            for key, values in event.objects.items():
                for value in values:
                    self.cases[key][value].append(event)

    @property
    def variants(self):
        if self._variants:
            return self._variants
        self._variant_count = defaultdict(lambda: defaultdict(list))
        for object_type, values in self.cases.items():
            for key, value in values.items():
                # key is the object id
                # value is the list of events
                self._variant_count[object_type][value.get_trace_hash()].append(value)

        variants = defaultdict(list)
        for object_type, type_variants in self._variant_count.items():
            for key, value in type_variants.items():
                variant = Variant(
                    trace=value[0],
                    percentage=len(value) / len(self.cases[object_type]),
                    count=len(value)
                )
                variants[object_type].append(variant)

        self._variants = variants
        return self._variants

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
                       col not in ['event_activity', 'event_timestamp'] and row[col]}
            event = Event(
                activity=row['event_activity'],
                timestamp=row['event_timestamp'],
                objects=objects
            )
            events.append(event)
        return events
