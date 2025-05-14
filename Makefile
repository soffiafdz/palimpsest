# Makefile for journal conversion & PDF builds (years 2015–2025)

# ─── Variables ────────────────────────────────────────────────────────────────
PYTHON    := python3
TXT2MD    := scripts/txt_to_md.py
BUILD_PDF := scripts/build_pdf.py
PROC_NEW  := scripts/proc_new_files.sh

TXT_DIR   := journal/txt
MD_DIR    := journal/md
PDF_DIR   := journal/pdf

YEARS     := 2015 2016 2017 2018 2019 2021 2022 2023 2024 2025

# ─── Compute lists of files ──────────────────────────────────────────────────
#TXT_FILES   := $(wildcard $(TXT_DIR)/*/*.txt)
#STAMP_FILES := $(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,$(TXT_FILES))
PDFS        := $(addprefix $(PDF_DIR)/,$(addsuffix .pdf,$(YEARS)))

# ─── Phony targets ───────────────────────────────────────────────────────────
.PHONY: all inbox clean-md clean-pdf help $(YEARS)

$(YEARS): %: $(PDF_DIR)%.pdf

# ─── Default: build every year’s PDF ─────────────────────────────────────────
all: $(PDFS)

# ─── 1) IMPORT new months from inbox ─────────────────────────────────────────
inbox:
	@echo "→ processing inbox"
	@bash $(PROC_NEW)

# ─── 2) month‐to‐daily conversion + stamp ────────────────────────────────────
# e.g. journal/md/2015/2015_01.stamp depends on journal/txt/2015/2015_01.txt
$(MD_DIR)/%.stamp: $(TXT_DIR)/%.txt
	@echo "→ converting month $*"
	@mkdir -p $(dir $@)
	$(PYTHON) $(TXT2MD) -i $< -o $(MD_DIR)
	@touch $@

# ─── 3) yearly‐PDF builds ────────────────────────────────────────────────────
# Define a static rule for each year via a small Make macro:
define BUILD_YEAR_PDF
$(PDF_DIR)/$(1).pdf: \
  $(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,$(wildcard $(TXT_DIR)/$(1)/*.txt))
	@echo "→ building PDF for year $(1)"
	@mkdir -p $(PDF_DIR)
	$(PYTHON) $(BUILD_PDF) -i $(MD_DIR)/$(1) -o $$@
endef

# Expand the above for each year in $(YEARS)
$(foreach Y,$(YEARS),$(eval $(call BUILD_YEAR_PDF,$(Y))))

# ─── Cleaning ────────────────────────────────────────────────────────────────
# Remove ONLY the markdown or ONLY the PDFs (won’t touch the other)
clean-md:
	rm -rf $(MD_DIR)

clean-pdf:
	rm -rf $(PDF_DIR)

# ─── Help ────────────────────────────────────────────────────────────────────
help:
	@echo "Usage:"
	@echo "  make           # convert & build PDFs for all years"
	@echo "  make all       # same as ‘make’"
	@echo "  make 2015      # build only journal/pdf/2015.pdf (and needed months)"
	@echo
	@echo "  make clean-md  # delete all generated .stamp & .md files"
	@echo "  make clean-pdf # delete all generated .pdf files"
