__all__ = ["RecordType", "ParserInterface", "Parser"]

from mantisshrimp.imports import *
from mantisshrimp.utils import *
from mantisshrimp.core import *
from mantisshrimp.parsers.mixins import *
from mantisshrimp.parsers.splits import *

RecordType = Dict[str, Any]


class ParserInterface(ABC):
    @abstractmethod
    def parse(
        self, data_splitter: DataSplitter, show_pbar: bool = True
    ) -> List[List[RecordType]]:
        pass


class Parser(ImageidParserMixin, ParserInterface, ABC):
    def prepare(self, o):
        pass

    @abstractmethod
    def __iter__(self):
        pass

    def parse_dicted(
        self, show_pbar: bool = True, idmap: IDMap = None
    ) -> Dict[int, RecordType]:
        idmap = idmap or IDMap()

        info_parse_funcs = self.collect_info_parse_funcs()
        annotation_parse_funcs = self.collect_annotation_parse_funcs()

        get_imageid = info_parse_funcs.pop("imageid")

        records = defaultdict(lambda: {name: [] for name in annotation_parse_funcs})
        for sample in pbar(self, show_pbar):
            self.prepare(sample)
            imageid = idmap[get_imageid(sample)]

            for name, func in info_parse_funcs.items():
                records[imageid][name] = func(sample)

            for name, func in annotation_parse_funcs.items():
                records[imageid][name].extend(func(sample))

        # check that all annotations have the same length
        # TODO: instead of immediatily raising the error, store the result and raise
        # at the end of the for loop for all records
        for imageid, record_annotations in records.items():
            record_annotations_len = {
                annotation_name: len(record_annotations[annotation_name])
                for annotation_name in annotation_parse_funcs
            }
            if not allequal(list(record_annotations_len.values())):
                true_imageid = idmap.i2imageid[imageid]
                raise RuntimeError(
                    f"imageid->{true_imageid} has an inconsistent number of annotations"
                    f", all annotations must have the same length."
                    f"\nNumber of annotations: {record_annotations_len}"
                )

        return dict(records)

    def parse(
        self,
        data_splitter: DataSplitter = None,
        idmap: IDMap = None,
        show_pbar: bool = True,
    ) -> List[List[RecordType]]:
        data_splitter = data_splitter or SingleSplitSplitter()
        records = self.parse_dicted(show_pbar=show_pbar, idmap=idmap)
        splits = data_splitter(records.keys())
        return [[{"imageid": id, **records[id]} for id in ids] for ids in splits]
