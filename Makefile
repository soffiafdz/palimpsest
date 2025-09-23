# Makefile for journal conversion & PDF builds (years 2015–2025)

# ─── Toggle verbosity ─────────────────────────────────────────────────────────
# make          → quiet
# make V=1      → verbose
V ?= 0
ifeq ($(V),2)
    Q :=
    PY_VERBOSE = -v
else ifeq ($(V),1)
    Q := @
    PY_VERBOSE = -v
else
    Q := @
    PY_VERBOSE =
endif

# ─── Variables ────────────────────────────────────────────────────────────────
TXT2MD    := scripts/txt2md/txt2md.py
MD2PDF    := scripts/md2pdf/md2pdf.py
PROC_INBX := bin/proc_inbox

TXT_DIR   := journal/txt
MD_DIR    := journal/md
PDF_DIR   := journal/pdf

# There is no 2020 entries (COVID)
YEARS     := 2015 2016 2017 2018 2019 2021 2022 2023 2024 2025

# ─── Compute the list of all targets ─────────────────────────────────────────
# Find all TXT files and convert to corresponding stamp files
ALL_TXT_FILES := $(wildcard $(TXT_DIR)/*/*.txt)
ALL_MD_STAMPS := $(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,\
								 $(ALL_TXT_FILES))

# ─── Compute the list of all PDF targets (clean + notes) ─────────────────────
YEAR_PDFS := $(foreach Y,$(YEARS),$(PDF_DIR)/$(Y).pdf) \
						 $(foreach Y,$(YEARS),$(PDF_DIR)/$(Y)-notes.pdf)

# ─── Phony targets ───────────────────────────────────────────────────────────
.PHONY: all inbox md pdf clean-md clean-pdf help $(YEARS)
.PHONY: $(foreach Y,$(YEARS),$(Y)-md $(Y)-pdf)

# ─── Default: build everything ───────────────────────────────────────────────
all: inbox md pdf

# ─── Build all Markdown files ────────────────────────────────────────────────
md: inbox $(ALL_MD_STAMPS)

# ─── Build all PDFs ──────────────────────────────────────────────────────────
pdf: md $(YEAR_PDFS)

# ─── Per-year PDF targets ────────────────────────────────────────────────────
# Build everything for a specific year (Markdown + PDFs)
$(YEARS): %: %-md %-pdf

# Build only Markdown for a specific year
$(foreach Y,$(YEARS),$(Y)-md): %-md: inbox
	$(Q)echo "→  building Markdown for year $*"
	$(Q)$(MAKE) $(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,\
		$(wildcard $(TXT_DIR)/$*/*.txt))

# Build only PDFs for a specific year (depends on Markdown)
$(foreach Y,$(YEARS),$(Y)-pdf): %-pdf: %-md $(PDF_DIR)/%.pdf \
	$(PDF_DIR)/%-notes.pdf

# ─── 1) import new months from inbox ─────────────────────────────────────────
inbox:
	$(Q)echo "→  processing inbox"
	$(Q)bash $(PROC_INBX)

# ─── 2) month‐to‐daily conversion + stamp ────────────────────────────────────
# journal/md/<y>/<y>_<m>.stamp depends on journal/txt/<y>/<y>_<m>.txt
$(MD_DIR)/%.stamp: $(TXT_DIR)/%.txt
	$(Q)echo "→  converting month $*"
	$(Q)mkdir -p $(dir $@)
	$(Q)PYTHONPATH=$(PWD) \
	python3 $(TXT2MD) --input $< --outdir $(MD_DIR) $(PY_VERBOSE)
	$(Q)touch $@

# ─── 3) yearly‐PDF builds ────────────────────────────────────────────────────
define BUILD_YEAR_PDF
$(PDF_DIR)/$(1).pdf $(PDF_DIR)/$(1)-notes.pdf &:  \
	$(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,\
		$(wildcard $(TXT_DIR)/$(1)/*.txt))
	$(Q)echo "→  building PDF for year $(1)"
	$(Q)mkdir -p $(PDF_DIR)
	$(Q)PYTHONPATH=$(PWD)                         \
	python3 $(MD2PDF) $(1)                        \
		--indir $(MD_DIR)                         \
		--outdir $(PDF_DIR)                       \
		$(PY_VERBOSE)
endef

# instantiate that rule for each year
$(foreach Y,$(YEARS),$(eval $(call BUILD_YEAR_PDF,$Y)))

# ─── Cleaning ────────────────────────────────────────────────────────────────
# Remove ONLY the markdown or ONLY the PDFs (won’t touch the other)
clean-md:
	$(Q)echo "→  cleaning generated Markdown"
	$(Q)rm -rf $(MD_DIR)

clean-pdf:
	$(Q)echo "→  cleaning generated PDFs"
	$(Q)rm -rf $(PDF_DIR)

# ─── Help ────────────────────────────────────────────────────────────────────
help:
	@echo "Usage:"
	@echo "  make               # convert & build everything for all years"
	@echo "  make all           # same as 'make'"
	@echo "  make md            # convert all TXT files to Markdown"
	@echo "  make pdf           # build all PDFs (requires Markdown)"
	@echo "  make <YEAR>        # build everything for specific year"
	@echo "  make <YEAR>-md     # build only Markdown for specific year"
	@echo "  make <YEAR>-pdf    # build only PDFs for specific year"
	@echo "  make inbox         # process new exports in journal/txt/"
	@echo "  make clean-md      # delete all .stamp & .md files"
	@echo "  make clean-pdf     # delete all .pdf files"
	@echo ""
	@echo "Examples:"
	@echo "  make 2023          # build everything for 2023"
	@echo "  make 2023-md       # build only Markdown for 2023"
	@echo "  make 2023-pdf      # build only PDFs for 2023"
