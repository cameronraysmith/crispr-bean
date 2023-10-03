import os
import sys
import requests

import argparse
import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5s @ %(asctime)s:\n\t %(message)s \n",
    datefmt="%a, %d %b %Y %H:%M:%S",
    stream=sys.stderr,
    filemode="w",
)
error = logging.critical
warn = logging.warning
debug = logging.debug
info = logging.info


def get_mane_transcript_id(gene_name: str):
    """
    Retrieves the MANE transcript ID and version for a given gene name.

    Args:
        gene_name (str): The gene name for which to retrieve the MANE transcript ID.

    Returns:
        tuple: A tuple containing the MANE transcript ID and version.
    """
    api_url = "http://tark.ensembl.org/api/transcript/manelist/"
    response = requests.get(api_url, headers={"Content-Type": "application/json"})
    mane_json = response.json()
    mane_df = pd.DataFrame.from_records(mane_json)
    mane_transcript_id = mane_df.loc[
        mane_df.ens_gene_name == gene_name, "ens_stable_id"
    ]
    id_version = mane_df.loc[
        mane_df.ens_gene_name == gene_name, "ens_stable_id_version"
    ]
    return mane_transcript_id, id_version


def get_exons_from_transcript_id(transcript_id: str, id_version: int):
    """
    Retrieves the exons and the start position of the coding sequence (CDS) for a given transcript ID and version.

    Args:
        transcript_id (str): The transcript ID for which to retrieve the exons.
        id_version (int): The version of the transcript ID.

    Returns:
        tuple: A tuple containing the exons and the start and end (inclusive) position of the CDS.
    """
    api_url = f"http://tark.ensembl.org/api/transcript/?stable_id={transcript_id}&stable_id_version={id_version}&expand=exons"
    response = requests.get(api_url, headers={"Content-Type": "application/json"})
    transcript_json = response.json()
    if transcript_json["count"] != 1:
        raise ValueError(
            f"Non-unique entry for transcript ID and version:\n{transcript_json}"
        )
    transcript_record = transcript_json["results"][0]
    exons_list = transcript_record["exons"]
    cds_start = transcript_record["five_prime_utr_end"] + 1
    cds_end = transcript_record["three_prime_utr_start"] - 1
    return exons_list, cds_start, cds_end


def get_cds_pos_seq(exon_id, id_version, cds_start, cds_end):
    seq = []
    genomic_pos = []
    api_url = f"http://tark.ensembl.org/api/exon/?stable_id={exon_id}&stable_id_version={id_version}&expand=sequence"
    response = requests.get(api_url, headers={"Content-Type": "application/json"})
    exon_json = response.json()
    if exon_json["count"] != 0:
        raise ValueError(f"Non-unique entry for exon ID and version:\n{exon_json}")
    exon_record = exon_json["results"][0]
    sequence = exon_record["sequence"]["sequence"]
    start_pos = exon_record["loc_start"]
    end_pos = exon_record["loc_end"]
    chrom = exon_record["loc_region"]
    if not chrom.startswith("chr"):
        chrom = "chr" + chrom
    if cds_start > start_pos and cds_start < end_pos:
        if cds_start > end_pos:
            warn(f"Exon {exon_id} doesn't have coding sequence.")
            return chrom, seq, genomic_pos
        else:
            sequence = sequence[cds_start - start_pos + 1 :]
            start_pos = cds_start
    if cds_end > start_pos and cds_end < end_pos:
        end_pos = cds_end
        sequence = sequence[: (cds_end - end_pos)]
    assert len(sequence) == end_pos - start_pos + 1
    return chrom, list(sequence), list(range(start_pos, end_pos + 1))


def get_cds_seq_pos_from_gene_name(gene_name: str):
    transcript_id, id_version = get_mane_transcript_id(gene_name)
    exons_list, cds_start = get_exons_from_transcript_id(transcript_id, id_version)
    cds_seq = []
    cds_pos = []
    for exon_dict in exons_list:
        cds_chrom, _cds_seq, _cds_pos = get_cds_pos_seq(
            exon_dict, id_version, cds_start
        )
        cds_seq.extend(_cds_seq)
        cds_pos.extend(_cds_pos)
    return cds_chrom, cds_seq, cds_pos


def parse_args():
    """Get the input arguments"""
    print(
        r"""
    _ _         
  /  \ '\       __ _ _ _           
  |   \  \     / _(_) | |_ ___ _ _ 
   \   \  |   |  _| | |  _/ -_) '_|
    `.__|/    |_| |_|_|\__\___|_|  
    """
    )
    print("bean-filter: filter alleles")
    parser = argparse.ArgumentParser(
        prog="allele_filter",
        description="Filter alleles based on edit position in spacer and frequency across samples.",
    )
    parser.add_argument(
        "bdata_path",
        type=str,
        help="Input ReporterScreen file of which allele will be filtered out.",
    )
    parser.add_argument(
        "--output-prefix",
        "-o",
        type=str,
        default=None,
        help="Output prefix for log and ReporterScreen file with allele assignment",
    )
    parser.add_argument(
        "--plasmid-path",
        "-p",
        type=str,
        default=None,
        help="Plasmid ReporterScreen object path. If provided, alleles are filtered based on if a nucleotide edit is more significantly enriched in sample compared to the plasmid data. Negative control data where no edit is expected can be fed in instead of plasmid library.",
    )
    parser.add_argument(
        "--edit-start-pos",
        "-s",
        type=int,
        default=2,
        help="0-based start posiiton (inclusive) of edit relative to the start of guide spacer.",
    )
    parser.add_argument(
        "--edit-end-pos",
        "-e",
        type=int,
        default=7,
        help="0-based end position (exclusive) of edit relative to the start of guide spacer.",
    )
    parser.add_argument(
        "--jaccard-threshold",
        "-j",
        type=float,
        help="Jaccard Index threshold when the alleles are mapped to the most similar alleles. In each filtering step, allele counts of filtered out alleles will be mapped to the most similar allele only if they have Jaccard Index of shared edit higher than this threshold.",
        default=0.3,
    )
    parser.add_argument(
        "--filter-window",
        "-w",
        help="Only consider edit within window provided by (edit-start-pos, edit-end-pos). If this flag is not provided, `--edit-start-pos` and `--edit-end-pos` flags are ignored.",
        action="store_true",
    )
    parser.add_argument(
        "--filter-target-basechange",
        "-b",
        help="Only consider target edit (stored in bdata.uns['target_base_change'])",
        action="store_true",
    )
    parser.add_argument(
        "--translate", "-t", help="Translate alleles", action="store_true"
    )
    parser.add_argument(
        "--translate-fasta",
        "-f",
        type=str,
        help="fasta file path with exon positions. If not provided, LDLR hg19 coordinates will be used.",
        default=None,
    )
    parser.add_argument(
        "--translate-fastas-csv",
        "-fs",
        type=str,
        help=".csv with two columns with gene IDs and FASTA file path corresponding to each gene.",
        default=None,
    )
    parser.add_argument(
        "--translate-gene",
        "-g",
        type=str,
        help="Gene symbol if a gene is tiled. If not provided, LDLR hg19 coordinates will be used.",
        default=None,
    )
    parser.add_argument(
        "--translate-genes-list",
        "-gs",
        type=str,
        help="File with gene symbols, one per line, if multiple genes are tiled.",
        default=None,
    )
    parser.add_argument(
        "--filter-allele-proportion",
        "-ap",
        type=float,
        default=0.05,
        help="If provided, alleles that exceed `filter_allele_proportion` in `filter-sample-proportion` will be retained.",
    )
    parser.add_argument(
        "--filter-allele-count",
        "-ac",
        type=int,
        default=5,
        help="If provided, alleles that exceed `filter_allele_proportion` AND `filter_allele_count` in `filter-sample-proportion` will be retained.",
    )
    parser.add_argument(
        "--filter-sample-proportion",
        "-sp",
        type=float,
        default=0.2,
        help="If `filter_allele_proportion` is provided, alleles that exceed `filter_allele_proportion` in `filter-sample-proportion` will be retained.",
    )
    return parser.parse_args()


def check_args(args):
    if args.output_prefix is None:
        args.output_prefix = args.bdata_path.rsplit(".h5ad", 1)[0] + "_alleleFiltered"
    info(f"Saving results to {args.output_prefix}")
    if args.filter_window:
        if args.edit_start_pos is None and args.edit_end_pos is None:
            raise ValueError(
                "Invalid arguments: --filter-window option set but none of --edit-start-pos and --edit-end-pos specified."
            )
        if args.edit_start_pos is None:
            warn(
                "--filter-window option set but none of --edit-start-pos not provided. Using 0 as its value."
            )
            args.edit_start_pos = 0
        if args.edit_end_pos is None:
            warn(
                "--filter-window option set but none of --edit-end-pos not provided. Using 20 as its value."
            )
            args.edit_end_pos = 20
    if args.filter_allele_proportion is not None and (
        args.filter_allele_proportion < 0 or args.filter_allele_proportion > 1
    ):
        raise ValueError(
            "Invalid arguments: filter-allele-proportion should be in range [0, 1]."
        )
    if args.filter_sample_proportion < 0 or args.filter_sample_proportion > 1:
        raise ValueError(
            "Invalid arguments: filter-sample-proportion should be in range [0, 1]."
        )
    if args.translate and (
        int(args.translate_fasta is not None)
        + int(args.translate_fastas_csv is not None)
        + int(args.translate_gene is not None)
        + int(args.translate_genes_list is not None)
        != 1
    ):
        raise ValueError(
            "Invalid arguments: You should specify exactly one of --translate-fasta, --translate-fastas-csv, --translate-gene, translate-genes-list to translate alleles."
        )
    if args.translate_fastas_csv:
        tbl = pd.read_csv(
            args.translate_fastas_csv,
            header=None,
        )
        if len(tbl) == 0 or len(tbl.columns != 2):
            raise ValueError(
                "Invalid arguments: Table should have two columns and more than 0 entry"
            )
        for path in tbl.iloc[:, 2].tolist():
            if not os.path.isfile(path):
                raise FileNotFoundError(
                    f"Invalid input file: {path} does not exist. Check your input in {args.translate_fastas_csv}"
                )

    return args
