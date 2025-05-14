# Makefile for journal conversion & PDF builds (years 2015–2025)

# ─── Toggle verbosity ─────────────────────────────────────────────────────────
# make          → quiet
# make V=1      → verbose
V ?= 0
ifeq ($(V),1)
  Q :=
  PY_VERBOSE = -v
else
  Q := @
  PY_VERBOSE =
endif

# ─── Variables ────────────────────────────────────────────────────────────────
PYTHON    := python3
TXT2MD    := scripts/txt2md.py
BUILD_PDF := scripts/pdfbuild.py
PROC_INBX := scripts/proc_inbox.sh

TXT_DIR   := journal/txt
MD_DIR    := journal/md
PDF_DIR   := journal/pdf

# There is no 2020 entries (COVID)
YEARS     := 2015 2016 2017 2018 2019 2021 2022 2023 2024 2025

# ─── Compute the list of all PDF targets (clean + notes) ─────────────────────
YEAR_PDFS :=                                  \
	$(foreach Y,$(YEARS),$(PDF_DIR)/$(Y).pdf) \
	$(foreach Y,$(YEARS),$(PDF_DIR)/$(Y)-notes.pdf)

# ─── Phony targets ───────────────────────────────────────────────────────────
.PHONY: all inbox clean-md clean-pdf help $(YEARS)

# ─── Per-year PDF targets ────────────────────────────────────────────────────
$(YEARS): %:          \
    $(PDF_DIR)/$@.pdf \
    $(PDF_DIR)/$@-notes.pdf

# ─── Default: build everything ───────────────────────────────────────────────
all: inbox $(YEAR_PDFS)

# ─── 1) import new months from inbox ─────────────────────────────────────────
inbox:
	$(Q)echo "→ processing inbox"
	$(Q)bash $(PROC_INBX)

# ─── 2) month‐to‐daily conversion + stamp ────────────────────────────────────
# journal/md/<y>/<y>_<m>.stamp depends on journal/txt/<y>/<y>_<m>.txt
$(MD_DIR)/%.stamp: $(TXT_DIR)/%.txt
	$(Q)echo "→ converting month $*"
	$(Q)mkdir -p $(dir $@)
	$(Q)$(PYTHON) $(TXT2MD) --input $< --outdir $(MD_DIR) $(PY_VERBOSE)
	$(Q)touch $@

# ─── 3) yearly‐PDF builds ────────────────────────────────────────────────────
define BUILD_YEAR_PDF
$(PDF_DIR)/$(1).pdf $(PDF_DIR)/$(1)-notes.pdf &:  \
	$(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,\
		$(wildcard $(TXT_DIR)/$(1)/*.txt))
	$(Q)echo "→ building PDF for year $(1)"
	$(Q)mkdir -p $(PDF_DIR)
	$(Q)$(PYTHON) $(BUILD_PDF) $(1)               \
		--indir $(MD_DIR)                         \
		--outdir $(PDF_DIR)                       \
		$(PY_VERBOSE)
endef

# instantiate that rule for each year
$(foreach Y,$(YEARS),$(eval $(call BUILD_YEAR_PDF,$Y)))

# ─── Cleaning ────────────────────────────────────────────────────────────────
# Remove ONLY the markdown or ONLY the PDFs (won’t touch the other)
clean-md:
	$(Q)echo "→ cleaning generated Markdown"
	$(Q)rm -rf $(MD_DIR)

clean-pdf:
	$(Q)echo "→ cleaning generated PDFs"
	$(Q)rm -rf $(PDF_DIR)

# ─── Help ────────────────────────────────────────────────────────────────────
help:
	@echo "Usage:"
	@echo "  make             # convert & build PDFs for all YEARS"
	@echo "  make all         # same as ‘make’"
	@echo "  make <YEAR>      # build only journal/pdf/<YEAR>{,-notes}.pdf"
	@echo "  make inbox       # process new exports in journal/txt/"
	@echo "  make clean-md    # delete all generated .stamp & .md files"
	@echo "  make clean-pdf   # delete all generated .pdf files"
