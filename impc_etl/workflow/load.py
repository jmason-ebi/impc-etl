from impc_etl.workflow.normalization import *
from impc_etl.workflow.config import ImpcConfig


class StatsPipeLineLoader(SparkSubmitTask):
    name = "IMPC_Stats_PipelineLoader"
    app = "impc_etl/jobs/load/stats_pipeline_loader.py"
    xml_path = luigi.Parameter()
    imits_report_tsv_path = luigi.Parameter()
    imits_allele2_tsv_path = luigi.Parameter()
    strain_report_tsv_path = luigi.Parameter()
    output_path = luigi.Parameter()

    def requires(self):
        return [
            ExperimentNormalizer(
                xml_path=self.xml_path,
                tsv_path=self.imits_report_tsv_path,
                entity_type="experiment",
                output_path=self.output_path,
            ),
            MouseNormalizer(
                tsv_path=self.imits_report_tsv_path,
                xml_path=self.xml_path,
                output_path=self.output_path,
            ),
            AlleleExtractor(
                tsv_path=self.imits_allele2_tsv_path, output_path=self.output_path
            ),
            ColonyCleaner(
                tsv_path=self.imits_report_tsv_path, output_path=self.output_path
            ),
            ImpressExtractor(output_path=self.output_path),
            MGIExtractor(
                strain_input_path=self.strain_report_tsv_path,
                output_path=self.output_path,
            ),
        ]

    def output(self):
        self.output_path = (
            self.output_path + "/"
            if not self.output_path.endswith("/")
            else self.output_path
        )
        return ImpcConfig().get_target(f"{self.output_path}impc_stats_input_parquet")

    def app_options(self):
        return [
            self.input()[0].path,
            self.input()[1].path,
            self.input()[2].path,
            self.input()[3].path,
            self.input()[4].path,
            self.input()[5].path,
            self.output().path,
        ]