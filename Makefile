# Makefile for Palimpsest journal processing pipeline
# Orchestrates: inbox → txt → md → db → pdf

# ─── Verbosity ────────────────────────────────────────────────────────────────
# make          [Make] → quiet
# make V=1      [Make] → verbose
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

# ─── Pipeline Commands ────────────────────────────────────────────────────────
PYTHON        := python3
PIPELINE      := $(PYTHON) -m dev.pipeline.cli
METADB        := $(PYTHON) -m dev.database.cli
TXT2MD        := $(PIPELINE) convert
MD2PDF        := $(PIPELINE) build-pdf

# ─── Directories ──────────────────────────────────────────────────────────────
INBOX_DIR     := journal/inbox
TXT_DIR       := journal/sources/txt
MD_DIR        := journal/content/md
PDF_DIR       := journal/output/pdf
DB_PATH       := journal/metadata/palimpsest.db

# ─── Years ────────────────────────────────────────────────────────────────────
# No 2020 entries (COVID)
YEARS         := 2015 2016 2017 2018 2019 2021 2022 2023 2024 2025

# ─── Computed Targets ─────────────────────────────────────────────────────────
# All text files and their corresponding MD stamps
ALL_TXT_FILES := $(wildcard $(TXT_DIR)/*/*.txt)
ALL_MD_STAMPS := $(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,$(ALL_TXT_FILES))

# All PDFs (clean + notes)
YEAR_PDFS     := $(foreach Y,$(YEARS),$(PDF_DIR)/$(Y).pdf $(PDF_DIR)/$(Y)-notes.pdf)

# ─── Phony Targets ────────────────────────────────────────────────────────────
.PHONY: all help clean
.PHONY: inbox txt md db pdf
.PHONY: clean-txt clean-md clean-db clean-pdf
.PHONY: init-db backup backup-full backup-list backup-list-full status validate stats health analyze
.PHONY: install install-dev uninstall
.PHONY: $(YEARS) $(foreach Y,$(YEARS),$(Y)-md $(Y)-pdf)

# ─── Default: Full Pipeline ───────────────────────────────────────────────────
all: inbox txt md db pdf

# ─── Pipeline Steps ───────────────────────────────────────────────────────────

# Step 1: Process inbox (raw exports → formatted text)
inbox:
	$(Q)echo "[Make] Processing inbox..."
	$(Q)$(PIPELINE) inbox $(PY_VERBOSE)

# Step 2: Convert text to markdown
txt: inbox
md: txt $(ALL_MD_STAMPS)

# Step 3: Sync database from markdown
db: md
	$(Q)echo "[Make] Syncing database..."
	$(Q)$(PIPELINE) sync-db $(PY_VERBOSE)

# Step 4: Build PDFs
pdf: md $(YEAR_PDFS)

# ─── Individual File Conversion ───────────────────────────────────────────────
# Convert single TXT file to MD (creates stamp file)
$(MD_DIR)/%.stamp: $(TXT_DIR)/%.txt
	$(Q)echo "[Make] Converting $*"
	$(Q)mkdir -p $(dir $@)
	$(Q)$(TXT2MD) -i $< -o $(MD_DIR) $(PY_VERBOSE)
	$(Q)touch $@

# ─── Per-Year Targets ─────────────────────────────────────────────────────────
# Build everything for a specific year
$(YEARS): %: %-md %-pdf

# Build only markdown for specific year
$(foreach Y,$(YEARS),$(Y)-md): %-md: txt
	$(Q)echo "[Make] Building markdown for year $*"
	$(Q)$(MAKE) $(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,$(wildcard $(TXT_DIR)/$*/*.txt))

# Build only PDFs for specific year
$(foreach Y,$(YEARS),$(Y)-pdf): %-pdf: %-md $(PDF_DIR)/%.pdf $(PDF_DIR)/%-notes.pdf

# ─── PDF Build Rules ──────────────────────────────────────────────────────────
define BUILD_YEAR_PDF
$(PDF_DIR)/$(1).pdf $(PDF_DIR)/$(1)-notes.pdf &: \
	$(patsubst $(TXT_DIR)/%.txt,$(MD_DIR)/%.stamp,$(wildcard $(TXT_DIR)/$(1)/*.txt))
	$(Q)echo "[Make] Building PDFs for year $(1)"
	$(Q)mkdir -p $(PDF_DIR)
	$(Q)$(MD2PDF) $(1) -i $(MD_DIR) -o $(PDF_DIR) $(PY_VERBOSE)
endef

# Instantiate PDF build rule for each year
$(foreach Y,$(YEARS),$(eval $(call BUILD_YEAR_PDF,$(Y))))

# ─── Database Operations ──────────────────────────────────────────────────────
init-db:
	$(Q)echo "[Make] Initializing database..."
	$(Q)$(METADB) init

backup:
	$(Q)echo "[Make] Creating database backup..."
	$(Q)$(METADB) backup --type manual

backup-full:
	$(Q)echo "[Make] Creating full data backup..."
	$(Q)$(PIPELINE) backup-full

backup-list:
	$(Q)$(METADB) backups

backup-list-full:
	$(Q)$(PIPELINE) backup-list-full

status:
	$(Q)$(PIPELINE) status

validate:
	$(Q)$(PIPELINE) validate

stats:
	$(Q)$(METADB) stats --verbose

health:
	$(Q)$(METADB) health

analyze:
	$(Q)$(METADB) analyze

# ─── Installation ─────────────────────────────────────────────────────────────
install:
	$(Q)echo "[Make] Installing CLI commands to ~/.local/bin..."
	$(Q)mkdir -p $(HOME)/.local/bin
	$(Q)ln -sf $(PWD)/dev/bin/journal $(HOME)/.local/bin/journal
	$(Q)ln -sf $(PWD)/dev/bin/metadb $(HOME)/.local/bin/metadb
	$(Q)echo "✅ Installed: journal, metadb"
	$(Q)echo "💡 Ensure ~/.local/bin is in your PATH"

install-dev: install
	$(Q)echo "[Make] Installing development environment..."
	$(Q)echo "💡 Activate conda environment: conda activate palimpsest"

uninstall:
	$(Q)echo "[Make] Removing CLI commands..."
	$(Q)rm -f $(HOME)/.local/bin/journal
	$(Q)rm -f $(HOME)/.local/bin/metadb
	$(Q)echo "✅ Uninstalled: journal, metadb"

# ─── Cleaning ─────────────────────────────────────────────────────────────────
clean-txt:
	$(Q)echo "[Make] Cleaning formatted text files..."
	$(Q)rm -rf $(TXT_DIR)

clean-md:
	$(Q)echo "[Make] Cleaning markdown files and stamps..."
	$(Q)rm -rf $(MD_DIR)

clean-pdf:
	$(Q)echo "[Make] Cleaning PDF files..."
	$(Q)rm -rf $(PDF_DIR)

clean-db:
	$(Q)echo "[Make] Cleaning database (keeping backups)..."
	$(Q)rm -f $(DB_PATH)

clean: clean-md clean-pdf
	$(Q)echo "[Make] Clean complete (kept: txt, db)"

# ─── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo "Palimpsest Journal Processing Pipeline"
	@echo ""
	@echo "Pipeline Steps:"
	@echo "  make inbox         # Process raw exports (src2txt)"
	@echo "  make txt           # Alias for inbox (backward compat)"
	@echo "  make md            # Convert text to markdown (txt2md)"
	@echo "  make db            # Sync database from markdown (yaml2sql)"
	@echo "  make pdf           # Build PDFs for all years (md2pdf)"
	@echo "  make all           # Run complete pipeline"
	@echo ""
	@echo "Year-Specific Builds:"
	@echo "  make <YEAR>        # Build everything for specific year"
	@echo "  make <YEAR>-md     # Build only markdown for year"
	@echo "  make <YEAR>-pdf    # Build only PDFs for year"
	@echo ""
	@echo "Examples:"
	@echo "  make 2024          # Build everything for 2024"
	@echo "  make 2024-md       # Build only markdown for 2024"
	@echo "  make 2024-pdf      # Build only PDFs for 2024"
	@echo ""
	@echo "Database Operations:"
	@echo "  make init-db       # Initialize database and Alembic"
	@echo "  make backup        # Create database backup"
	@echo "  make backup-full   # Create full compressed data backup"
	@echo "  make backup-list   # List database backups"
	@echo "  make backup-list-full  # List full data backups"
	@echo "  make status        # Show pipeline status"
	@echo "  make validate      # Validate pipeline integrity"
	@echo "  make stats         # Show database statistics"
	@echo "  make health        # Run health check"
	@echo "  make analyze       # Generate analytics report"
	@echo ""
	@echo "Installation:"
	@echo "  make install       # Install CLI commands (journal, metadb)"
	@echo "  make install-dev   # Install with dev environment setup"
	@echo "  make uninstall     # Remove CLI commands"
	@echo ""
	@echo "Cleaning:"
	@echo "  make clean         # Remove markdown and PDFs"
	@echo "  make clean-txt     # Remove formatted text files"
	@echo "  make clean-md      # Remove markdown files"
	@echo "  make clean-pdf     # Remove PDF files"
	@echo "  make clean-db      # Remove database (keeps backups)"
	@echo ""
	@echo "Verbosity:"
	@echo "  make V=1 <target>  # Verbose output"
	@echo "  make V=2 <target>  # Very verbose (show commands)"
	@echo ""
	@echo "Available years: $(YEARS)"
