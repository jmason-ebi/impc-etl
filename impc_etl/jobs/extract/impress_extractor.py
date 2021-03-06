"""
IMPRESS extractor
    extract_impress: Extract Impress data and load it to a dataframe
"""
from typing import List, Dict
import json
import time
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StructType, ArrayType
from pyspark.sql.functions import udf, explode_outer, col
import requests
from impc_etl.shared.utils import convert_to_row
from impc_etl import logger
import sys


def main(argv):
    """
    IMPRESS Extractor job runner
    :param list argv: the list elements should be:
                    [1]: Impress API URL
                    [2]: Output Path
                    [3]: Impress root type to start scraping from
    """
    impress_api_url = argv[1]
    output_path = argv[2]
    impress_root_type = argv[3]

    spark = SparkSession.builder.getOrCreate()
    impress_df = extract_impress(spark, impress_api_url, impress_root_type)

    ontology_terms = get_ontology_terms(impress_api_url, spark)
    impress_df = impress_df.join(
        ontology_terms,
        impress_df["parammpterm.ontologyTermId"] == ontology_terms.termId,
        "left_outer",
    )
    impress_df.write.mode("overwrite").parquet(output_path)


def extract_impress(
    spark_session: SparkSession, impress_api_url: str, start_type: str
) -> DataFrame:
    """

    :param spark_session:
    :param impress_api_url:
    :param start_type:
    :return:
    """
    impress_api_url = (
        impress_api_url[:-1] if impress_api_url.endswith("/") else impress_api_url
    )
    root_index = requests.get("{}/{}/list".format(impress_api_url, start_type)).json()
    root_ids = [key for key in root_index.keys()]
    return get_entities_dataframe(spark_session, impress_api_url, start_type, root_ids)


def get_entities_dataframe(
    spark_session: SparkSession,
    impress_api_url,
    impress_type: str,
    impress_ids: List[str],
) -> DataFrame:
    """

    :param spark_session:
    :param impress_api_url:
    :param impress_type:
    :param impress_ids:
    :return:
    """
    entities = [
        get_impress_entity_by_id(impress_api_url, impress_type, impress_id)
        for impress_id in impress_ids
    ]
    entity_df = spark_session.createDataFrame(
        convert_to_row(entity) for entity in entities
    )
    current_type = ""
    current_schema = entity_df.schema
    entity_df = process_collection(
        spark_session, impress_api_url, current_schema, current_type, entity_df
    )
    unit_df = get_impress_units(impress_api_url, spark_session)
    entity_df = entity_df.join(
        unit_df, entity_df["parameter.unit"] == unit_df["unitID"], "left_outer"
    )
    return entity_df


def process_collection(
    spark_session, impress_api_url, current_schema, current_type, entity_df
):
    """

    :param spark_session:
    :param impress_api_url:
    :param current_schema:
    :param current_type:
    :param entity_df:
    :return:
    """
    impress_subtype = ""
    collection_types = []
    for column_name in current_schema.names:
        if "Collection" in column_name:
            impress_subtype = column_name.replace("Collection", "")
            if current_type != "":
                column_name = current_type + "." + column_name
            sub_entity_schema = get_impress_entity_schema(
                spark_session, impress_api_url, impress_subtype
            )
            get_entities_udf = udf(
                lambda x: get_impress_entity_by_ids(
                    impress_api_url, impress_subtype, x
                ),
                ArrayType(StructType(sub_entity_schema)),
            )
            entity_df = entity_df.withColumn(
                impress_subtype, get_entities_udf(entity_df[column_name])
            )
            collection_types.append(
                dict(type=impress_subtype, schema=sub_entity_schema)
            )
            entity_df = entity_df.withColumn(
                impress_subtype, explode_outer(entity_df[impress_subtype])
            )

    for collection_type in collection_types:
        logger.info("Calling to process:" + collection_type["type"])
        entity_df = process_collection(
            spark_session,
            impress_api_url,
            collection_type["schema"],
            collection_type["type"],
            entity_df,
        )
    return entity_df


def get_impress_entity_by_ids(
    impress_api_url: str, impress_type: str, impress_ids: List[int], retries=0
):
    """

    :param impress_api_url:
    :param impress_type:
    :param impress_ids:
    :param retries:
    :return:
    """
    api_call_url = "{}/{}/multiple".format(impress_api_url, impress_type)
    logger.info("parsing :" + api_call_url)
    if impress_ids is None or len(impress_ids) == 0:
        return []
    try:
        response = requests.post(api_call_url, json=impress_ids)
        try:
            entity = response.json()
        except json.decoder.JSONDecodeError:
            logger.info("{}/{}/multiple".format(impress_api_url, impress_type))
            logger.info("         " + response.text)
            if response.text == "":
                raise requests.exceptions.RequestException(response=response)
            entity = []
    except requests.exceptions.RequestException as e:
        if retries < 4:
            time.sleep(1)
            entity = get_impress_entity_by_ids(
                impress_api_url, impress_type, impress_ids, retries + 1
            )
        else:
            logger.info(
                "Max retries for "
                + "{}/{}/multiple".format(impress_api_url, impress_type)
            )
            entity = []
    return entity


def get_impress_entity_by_id(
    impress_api_url: str, impress_type: str, impress_id: str, retries=0
):
    """

    :param impress_api_url:
    :param impress_type:
    :param impress_id:
    :param retries:
    :return:
    """
    api_call_url = "{}/{}/{}".format(impress_api_url, impress_type, impress_id)
    logger.info("parsing :" + api_call_url)
    if impress_id is None:
        return None
    try:
        response = requests.get(api_call_url, timeout=(5, 14))
        try:
            entity = response.json()
        except json.decoder.JSONDecodeError:
            logger.info("{}/{}/{}".format(impress_api_url, impress_type, impress_id))
            logger.info("         " + response.text)
            if response.text == "":
                raise requests.exceptions.RequestException(response=response)
            entity = None
    except requests.exceptions.RequestException as e:
        if retries < 4:
            time.sleep(1)
            entity = get_impress_entity_by_id(
                impress_api_url, impress_type, impress_id, retries + 1
            )
        else:
            logger.info(
                "Max retries for "
                + "{}/{}/{}".format(impress_api_url, impress_type, impress_id)
            )
            entity = None
    return entity


def get_impress_entity_schema(
    spark_session: SparkSession, impress_api_url: str, impress_type: str
):
    """

    :param spark_session:
    :param impress_api_url:
    :param impress_type:
    :return:
    """
    schema_example = (
        1 if impress_type not in ["increment", "option", "parammpterm"] else 0
    )
    first_entity = requests.get(
        "{}/{}/{}".format(impress_api_url, impress_type, schema_example)
    ).text
    entity_rdd = spark_session.sparkContext.parallelize([first_entity])
    return spark_session.read.json(entity_rdd).schema


def get_impress_units(impress_api_url, spark_session):
    json_obj: Dict = json.loads(
        requests.get("{}/{}".format(impress_api_url, "unit/list")).text
    )
    unit_index = [{"unitID": key, "unitName": value} for key, value in json_obj.items()]
    entity_rdd = spark_session.sparkContext.parallelize(unit_index)
    return spark_session.read.json(entity_rdd)


def get_ontology_terms(impress_api_url, spark_session):
    json_obj: Dict = json.loads(
        requests.get("{}/{}".format(impress_api_url, "ontologyterm/list")).text
    )
    unit_index = [{"termId": key, "termAcc": value} for key, value in json_obj.items()]
    entity_rdd = spark_session.sparkContext.parallelize(unit_index)
    return spark_session.read.json(entity_rdd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
