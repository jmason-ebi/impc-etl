from impc_etl.workflow.load import *


class ImpcEtl(luigi.Task):
    dcc_xml_path = luigi.Parameter()
    imits_colonies_tsv_path = luigi.Parameter()
    imits_alleles_tsv_path = luigi.Parameter()
    mgi_allele_input_path = luigi.Parameter()
    mgi_strain_input_path = luigi.Parameter()
    komp2_jdbc_connection = luigi.Parameter()
    komp2_db_user = luigi.Parameter()
    komp2_db_password = luigi.Parameter()
    ontology_input_path = luigi.Parameter()
    output_path = luigi.Parameter()

    def requires(self):
        return [
            ObservationsMapper(
                dcc_xml_path=self.dcc_xml_path,
                imits_colonies_tsv_path=self.imits_colonies_tsv_path,
                output_path=self.output_path,
                mgi_strain_input_path=self.mgi_strain_input_path,
                mgi_allele_input_path=self.mgi_allele_input_path,
                ontology_input_path=self.ontology_input_path,
            ),
            Komp2AlleleLoader(
                jdbc_connection=self.komp2_jdbc_connection,
                db_user=self.komp2_db_user,
                db_password=self.komp2_db_password,
                imits_allele2_tsv_file=self.imits_alleles_tsv_path,
                output_path=self.output_path,
            ),
        ]


class ImpcOpenStats(luigi.Task):
    openstats_jdbc_connection = luigi.Parameter()
    openstats_db_user = luigi.Parameter()
    openstats_db_password = luigi.Parameter()
    data_release_version = luigi.Parameter()
    output_path = luigi.Parameter()

    def requires(self):
        return [
            OpenStatsExtractor(
                openstats_jdbc_connection=self.openstats_jdbc_connection,
                openstats_db_user=self.openstats_db_user,
                openstats_db_password=self.openstats_db_password,
                data_release_version=self.data_release_version,
                output_path=self.output_path,
            )
        ]
