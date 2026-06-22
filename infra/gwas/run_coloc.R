#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(coloc))
suppressPackageStartupMessages(library(jsonlite))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 5) stop("usage: run_coloc.R gwas.tsv qtl.tsv output.json trait tissues")
gwas <- read.delim(args[1], check.names = FALSE)
qtl <- read.delim(args[2], check.names = FALSE)
required <- c("variant_id", "beta", "se", "maf", "n")
if (!all(required %in% names(gwas)) || !all(required %in% names(qtl))) {
  stop("coloc inputs require variant_id, beta, se, maf, and n")
}
merged <- merge(gwas, qtl, by = "variant_id", suffixes = c(".gwas", ".qtl"))
if (nrow(merged) < 50) stop("coloc requires at least 50 harmonized variants")
d1 <- list(beta = merged$beta.gwas, varbeta = merged$se.gwas^2, snp = merged$variant_id,
           MAF = merged$maf.gwas, N = max(merged$n.gwas), type = "quant")
d2 <- list(beta = merged$beta.qtl, varbeta = merged$se.qtl^2, snp = merged$variant_id,
           MAF = merged$maf.qtl, N = max(merged$n.qtl), type = "quant")
fit <- coloc.abf(dataset1 = d1, dataset2 = d2)
tissues <- strsplit(args[5], ",", fixed = TRUE)[[1]]
rows <- lapply(tissues, function(tissue) list(
  trait = args[4], tissue = tissue, h4 = unname(fit$summary[["PP.H4.abf"]]),
  gwas_dataset = args[1], qtl_dataset = args[2]
))
result <- list(
  results = rows,
  assumptions = c("one causal variant per trait", "harmonized alleles", "default coloc priors"),
  input_datasets = c(args[1], args[2])
)
write(toJSON(result, auto_unbox = TRUE, digits = 16), file = args[3])
