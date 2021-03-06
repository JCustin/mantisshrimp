__all__ = [
    "create_coco_api",
    "convert_records_to_coco_style",
    "convert_preds_to_coco_style",
    "coco_api_from_records",
    "coco_api_from_preds",
    "create_coco_eval",
]

from mantisshrimp.imports import *
from mantisshrimp.utils import *
from mantisshrimp.core import *
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval


def create_coco_api(coco_records) -> COCO:
    """ Create COCO dataset api

    Args:
        coco_records: Records in coco style (use convert_records_to_coco_style to convert
        records to coco style.
    """
    coco_ds = COCO()
    coco_ds.dataset = coco_records
    coco_ds.createIndex()

    return coco_ds


def coco_api_from_preds(preds) -> COCO:
    coco_preds = convert_preds_to_coco_style(preds)
    return create_coco_api(coco_preds)


def coco_api_from_records(records) -> COCO:
    """ Create pycocotools COCO dataset from records
    """
    coco_records = convert_records_to_coco_style(records)
    return create_coco_api(coco_records=coco_records)


def create_coco_eval(records, preds, metric_type: str) -> COCOeval:
    assert len(records) == len(preds)

    for record, pred in zip(records, preds):
        pred["imageid"] = record["imageid"]

    target_ds = coco_api_from_records(records)
    pred_ds = coco_api_from_preds(preds)
    return COCOeval(target_ds, pred_ds, metric_type)


def convert_record_to_coco_image(record) -> dict:
    image = {}
    image["id"] = record["imageid"]
    image["file_name"] = Path(record["filepath"]).name
    image["width"] = record["width"]
    image["height"] = record["height"]
    return image


def convert_record_to_coco_annotations(record):
    annotations_dict = defaultdict(list)
    # build annotations field
    for label in record["labels"]:
        annotations_dict["image_id"].append(record["imageid"])
        annotations_dict["category_id"].append(label)

    if "bboxes" in record:
        for bbox in record["bboxes"]:
            annotations_dict["bbox"].append(bbox.xywh)

    if "areas" in record:
        for area in record["areas"]:
            annotations_dict["area"].append(area)
    else:
        for bbox in record["bboxes"]:
            annotations_dict["area"].append(bbox.area)

    if "masks" in record:
        for mask in record["masks"]:
            if isinstance(mask, Polygon):
                annotations_dict["segmentation"].append(mask.points)
            elif isinstance(mask, RLE):
                coco_rle = {
                    "counts": mask.to_coco(),
                    "size": [record["height"], record["width"]],
                }
                annotations_dict["segmentation"].append(coco_rle)
            elif isinstance(mask, MaskFile):
                rles = mask.to_coco_rle(record["height"], record["width"])
                annotations_dict["segmentation"].extend(rles)
            else:
                msg = f"Mask type {type(mask)} unsupported, we only support RLE and Polygon"
                raise ValueError(msg)

    # TODO: is auto assigning a value for iscrowds dangerous (may hurt the metric value?)
    if "iscrowds" not in record:
        record["iscrowds"] = [0] * len(record["labels"])
    for iscrowd in record["iscrowds"]:
        annotations_dict["iscrowd"].append(iscrowd)

    if "scores" in record:
        annotations_dict["score"].extend(record["scores"])

    return annotations_dict


def convert_preds_to_coco_style(preds):
    return convert_records_to_coco_style(records=preds, images=False, categories=False)


def convert_records_to_coco_style(
    records, images: bool = True, annotations: bool = True, categories: bool = True
):
    """ Converts records from library format to coco format.
    Inspired from: https://github.com/pytorch/vision/blob/master/references/detection/coco_utils.py#L146
    """
    images_ = []
    annotations_dict = defaultdict(list)

    for record in pbar(records):
        if images:
            image_ = convert_record_to_coco_image(record)
            images_.append(image_)

        if annotations:
            annotations_ = convert_record_to_coco_annotations(record)
            for k, v in annotations_.items():
                annotations_dict[k].extend(v)

    if annotations:
        annotations_dict = dict(annotations_dict)
        if not allequal([len(o) for o in annotations_dict.values()]):
            raise RuntimeError("Mismatch lenght of elements")

        # convert dict of lists to list of dicts
        annotations_ = []
        for i in range(len(annotations_dict["image_id"])):
            annotation = {k: v[i] for k, v in annotations_dict.items()}
            # annotations should be initialized starting at 1 (torchvision issue #1530)
            annotation["id"] = i + 1
            annotations_.append(annotation)

    if categories:
        categories_set = set(annotations_dict["category_id"])
        categories_ = [{"id": i} for i in categories_set]

    res = {}
    if images_:
        res["images"] = images_
    if annotations:
        res["annotations"] = annotations_
    if categories:
        res["categories"] = categories_

    return res
