"""
SOLR module
   Generates the required Solr cores
"""
from pyspark.sql.functions import (
    col,
    explode,
    concat_ws,
    collect_set,
    when,
    flatten,
    explode_outer,
)
from pyspark.sql import DataFrame, SparkSession
import sys


def main(argv):
    """
    Solr Core loader
    :param list argv: the list elements should be:
                    [1]: source IMPC parquet file
                    [2]: Output Path
    """
    observations_parquet_path = argv[1]
    pipeline_core_parquet_path = argv[2]
    omero_ids_csv_path = argv[3]
    output_path = argv[4]

    spark = SparkSession.builder.getOrCreate()
    observations_df = spark.read.parquet(observations_parquet_path)
    pipeline_core_df = spark.read.parquet(pipeline_core_parquet_path)
    pipeline_core_df = pipeline_core_df.select(
        "fully_qualified_name",
        "mouse_anatomy_id",
        "mouse_anatomy_term",
        "embryo_anatomy_id",
        "embryo_anatomy_term",
        "top_level_mouse_anatomy_id",
        "top_level_mouse_anatomy_term",
        "top_level_embryo_anatomy_id",
        "top_level_embryo_anatomy_term",
    )
    omero_ids_df = spark.read.csv(omero_ids_csv_path, header=True)
    image_observations_df = observations_df.where(
        col("observation_type") == "image_record"
    )
    image_observations_df = image_observations_df.join(
        omero_ids_df,
        [
            "observation_id",
            "download_file_path",
            "phenotyping_center",
            "pipeline_stable_id",
            "procedure_stable_id",
            "parameter_stable_id",
            "datasource_name",
        ],
    )
    image_observations_df = image_observations_df.withColumn(
        "parameter_association_stable_id_exp",
        explode_outer("parameter_association_stable_id"),
    )
    image_observations_df = image_observations_df.withColumn(
        "fully_qualified_name",
        concat_ws(
            "_",
            "pipeline_stable_id",
            "procedure_stable_id",
            "parameter_association_stable_id",
        ),
    )
    image_observations_df = image_observations_df.join(
        pipeline_core_df, "fully_qualified_name", "left_outer"
    )
    image_observations_df = image_observations_df.groupBy(
        [
            col_name
            for col_name in observations_df.columns
            if col_name != "parameter_association_stable_id"
        ]
    ).agg(
        collect_set("parameter_association_stable_id_exp").alias(
            "parameter_association_stable_id"
        ),
        collect_set(
            when(
                col("mouse_anatomy_id").isNotNull(), col("mouse_anatomy_id")
            ).otherwise(col("embryo_anatomy_id"))
        ).alias("anatomy_id"),
        collect_set(
            when(
                col("mouse_anatomy_term").isNotNull(), col("mouse_anatomy_term")
            ).otherwise(col("embryo_anatomy_term"))
        ).alias("anatomy_term"),
        flatten(
            collect_set(
                when(
                    col("mouse_anatomy_id").isNotNull(),
                    col("top_level_mouse_anatomy_id"),
                ).otherwise(col("top_level_embryo_anatomy_id"))
            )
        ).alias("selected_top_level_anatomy_id"),
        flatten(
            collect_set(
                when(
                    col("mouse_anatomy_id").isNotNull(),
                    col("top_level_mouse_anatomy_term"),
                ).otherwise(col("top_level_embryo_anatomy_term"))
            )
        ).alias("selected_top_level_anatomy_term"),
    )
    image_observations_df.write.parquet(output_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
