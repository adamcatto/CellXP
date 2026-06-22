#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(susieR))
suppressPackageStartupMessages(library(jsonlite))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 7) stop("usage: run_susie.R summary.tsv ld.tsv output.json chrom start end assembly")
stats <- read.delim(args[1], check.names = FALSE)
ld <- as.matrix(read.delim(args[2], header = FALSE, check.names = FALSE))
required <- c("variant_id", "beta", "se")
if (!all(required %in% names(stats))) stop("summary stats require variant_id, beta, and se")
if (nrow(ld) != nrow(stats) || ncol(ld) != nrow(stats)) stop("LD dimensions do not match summary stats")
fit <- susie_rss(bhat = stats$beta, shat = stats$se, R = ld, coverage = 0.95, estimate_residual_variance = FALSE)
sets <- list()
if (!is.null(fit$sets$cs)) {
  for (i in seq_along(fit$sets$cs)) {
    indices <- fit$sets$cs[[i]]
    sets[[length(sets) + 1]] <- list(
      id = paste0("susie-cs", i),
      variants = lapply(indices, function(j) list(variant_id = stats$variant_id[j], pip = fit$pip[j])),
      region = list(chrom = args[4], start = as.integer(args[5]), end = as.integer(args[6]), assembly = args[7], strand = "."),
      coverage = 0.95
    )
  }
}
result <- list(
  credible_sets = sets,
  assumptions = c("summary statistics and LD alleles are harmonized", "SuSiE RSS model", "95% credible sets"),
  input_datasets = c(args[1], args[2])
)
write(toJSON(result, auto_unbox = TRUE, digits = 16), file = args[3])
