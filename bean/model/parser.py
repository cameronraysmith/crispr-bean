import argparse


def none_or_str(value):
    if value == "None":
        return None
    return value


def parse_args(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser(description="Run model on data.")
    parser.add_argument(
        "selection",
        type=str,
        choices=["sorting", "survival"],
        help="Screen selection type whether cells are sorted based on continuous phenotype ('sorting') or proliferated based on their viability ('survival').",
    )
    parser.add_argument(
        "library_design",
        type=str,
        choices=["variant", "tiling"],
        help="Library design type whether to run variant or tiling screen model.\nVariant library design assumes gRNA has specific target variant and bystander edits are ignored. Tiling library design considers all alleles generated by gRNA in reporter.",
    )
    parser.add_argument("bdata_path", type=str, help="Path of an ReporterScreen object")
    parser.add_argument(
        "--rep-pi",
        "-r",
        action="store_true",
        default=False,
        help="Fit replicate specific scaling factor. Recommended to set as True if you expect variable editing activity across biological replicates.",
    )
    parser.add_argument(
        "--uniform-edit",
        "-p",
        action="store_true",
        default=False,
        help="Assume uniform editing rate for all guides.",
    )
    parser.add_argument(
        "--scale-by-acc",
        action="store_true",
        default=False,
        help="Scale guide editing efficiency by the target loci accessibility",
    )
    parser.add_argument(
        "--acc-bw-path",
        type=str,
        default=None,
        help="Accessibility .bigWig file to be used to assign accessibility of guides.",
    )
    parser.add_argument(
        "--acc-col",
        type=str,
        default=None,
        help="Column name in bdata.guides that specify raw ATAC-seq signal.",
    )
    parser.add_argument(
        "--const-pi",
        default=False,
        action="store_true",
        help="Use constant pi provided in --guide-activity-col (instead of fitting from reporter data)",
    )
    parser.add_argument(
        "--shrink-alpha",
        default=False,
        action="store_true",
        help="Instead of using the trend-fitted alpha values, use estimated alpha values for each gRNA that are shrunk towards the fitted trend.",
    )
    parser.add_argument(
        "--condition-col",
        default="condition",
        type=str,
        help="Column key in `bdata.samples` that describes experimental condition.",
    )
    parser.add_argument(
        "--time-col",
        default="time",
        type=str,
        help="Column key in `bdata.samples` that describes time elapsed.",
    )
    parser.add_argument(
        "--control-condition",
        default="bulk",
        type=str,
        help="Value in `bdata.samples[condition_col]` that indicates control experimental condition.",
    )
    parser.add_argument(
        "--include-control-condition-for-inference",
        "-ic",
        default=False,
        action="store_true",
        help="Include control conditions for inference. Currently only supported for survival screens.",
    )
    parser.add_argument(
        "--replicate-col",
        default="replicate",
        type=str,
        help="Column key in `bdata.samples` that describes experimental replicates.",
    )
    parser.add_argument(
        "--target-col",
        default="target",
        type=str,
        help="Column key in `bdata.guides` that describes the target element of each guide.",
    )
    parser.add_argument(
        "--guide-activity-col",
        "-a",
        type=str,
        default=None,
        help="Column in ReporterScreen.guides DataFrame showing the editing rate estimated via external tools",
    )
    parser.add_argument(
        "--outdir",
        "-o",
        default=".",
        type=str,
        help="Directory to save the run result.",
    )
    parser.add_argument(
        "--result-suffix",
        default="",
        type=str,
        help="Suffix of the output files",
    )
    parser.add_argument(
        "--sorting-bin-upper-quantile-col",
        "-uq",
        help="Column name with upper quantile values of each sorting bin in [Reporter]Screen.samples (or AnnData.var)",
        default="upper_quantile",
    )
    parser.add_argument(
        "--sorting-bin-lower-quantile-col",
        "-lq",
        help="Column name with lower quantile values of each sorting bin in [Reporter]Screen.samples (or AnnData var)",
        default="lower_quantile",
    )
    parser.add_argument(
        "--alpha-if-overdispersion-fitting-fails",
        "-af",
        default=None,
        type=str,
        help="Comma-separated regression coefficient (b0, b1) of log(a0) ~ log(q) that will be used if fitting dispersion on the data fails.",
    )
    parser.add_argument("--cuda", action="store_true", default=False, help="run on GPU")
    parser.add_argument(
        "--sample-mask-col",
        type=str,
        default=None,
        help="Name of the column indicating the sample mask in [Reporter]Screen.samples (or AnnData.var). Sample is ignored if the value in this column is 0. This can be used to mask out low-quality samples.",
    )
    parser.add_argument(
        "--fit-negctrl",
        action="store_true",
        default=False,
        help="Fit the shared negative control distribution to normalize the fitted parameters",
    )
    parser.add_argument(
        "--negctrl-col",
        type=str,
        default="target_group",
        help="Column in bdata.obs specifying if a guide is negative control. If the `bdata.guides[negctrl_col].lower() == negctrl_col_value`, it is treated as negative control guide.",
    )
    parser.add_argument(
        "--negctrl-col-value",
        type=str,
        default="negctrl",
        help="Column value in bdata.guides specifying if a guide is negative control. If the `bdata.guides[negctrl_col].lower() == negctrl_col_value`, it is treated as negative control guide.",
    )
    parser.add_argument(
        "--repguide-mask",
        type=none_or_str,
        default="repguide_mask",
        help="n_replicate x n_guide mask to mask the outlier guides. screen.uns[repguide_mask] will be used.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Optionally use GPU if provided valid GPU device name (ex. cuda:0)",
    )
    parser.add_argument(
        "--ignore-bcmatch",
        action="store_true",
        default=False,
        help="If provided, even if the screen object has .X_bcmatch, ignore the count when fitting.",
    )
    parser.add_argument(
        "--allele-df-key",
        type=str,
        default=None,
        help="screen.uns[allele_df_key] will be used as the allele count.",
    )
    parser.add_argument(
        "--splice-site-path",
        type=str,
        default=None,
        help="Path to splicing site",
    )
    parser.add_argument(
        "--control-guide-tag",
        type=none_or_str,
        default=None,
        help="If this string is in guide name, treat each guide separately not to mix the position. Used for negative controls.",
    )
    parser.add_argument(
        "--dont-fit-noise",  # TODO: add check args
        action="store_true",
    )
    parser.add_argument(
        "--dont-adjust-confidence-by-negative-control",
        action="store_true",
        help="Adjust confidence by negative controls. For variant library_design, this uses negative control variants. For tiling library_design, adjusts confidence by synonymous edits.",
    )
    parser.add_argument(
        "--n-iter",  # TODO: add check args
        type=int,
        default=2000,
        help="# of SVI steps taken for inference.",
    )
    parser.add_argument(
        "--load-existing",  # TODO: add check args
        action="store_true",
        help="Load existing .pkl file if present.",
    )

    return parser
