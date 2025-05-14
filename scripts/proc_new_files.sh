#!/usr/bin/env bash
### Parse `journal/inbox/` directory for new 750w exports
### Find Years to update, and then by year:
### - Rename source files to consistent naming
### - Apply initial pre-formating and send to `/journal/txt`
### - Update zipfile in `/journal/archive`
### - Remove source file

set -euo pipefail
IFS=$'\n\t'

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ROOT=~/Documents/palimpsest
ARCHIVE=${ROOT}/journal/archive
INBOX=${ROOT}/journal/inbox
TXTS=${ROOT}/journal/txt
FORMAT_SCRIPT=${ROOT}/scripts/init_fmt.awk

# centralized printf formats
INFO_FMT="→ %s\n"
COUNT_FMT="→ %d %s\n"

# ─── PREPARE ─────────────────────────────────────────────────────────────────
mkdir -p "$ARCHIVE" "$TXTS"
shopt -s nullglob

printf "$INFO_FMT" "looking for new files in '$INBOX'"
mapfile -t src_files < <(printf '%s\n' "$INBOX"/*.txt)

if (( ${#src_files[@]} == 0 )); then
  printf "$INFO_FMT" "'$INBOX' is empty. Nothing to update."
  exit 0
fi

printf "$COUNT_FMT" "${#src_files[@]}" "new files found in '$INBOX'"

# ─── FUNCTIONS ───────────────────────────────────────────────────────────────
declare -A year_files_map

rename_file() {
  local file="$1"
  local base="${file##*/}"
  if [[ $base =~ ([0-9]{4})_([0-9]{2}) ]]; then
    local year="${BASH_REMATCH[1]}"
    local month="${BASH_REMATCH[2]}"
    local new_name="journal_${year}_${month}.txt"
    printf "$INFO_FMT" "renaming '$base' → '$new_name'"
    mv -- "$file" "$INBOX/$new_name"
    # accumulate per-year list (newline-separated)
    year_files_map["$year"]+="$new_name"$'\n'
  else
    printf "$INFO_FMT" "skipping unrecognized file '$base'"
  fi
}

process_year() {
  local year="$1"
  local files_list="$2"
  local year_dir="$TXTS/$year"

  # ensure output dir exists
  mkdir -p "$year_dir"

  # read the newline-separated list into an array
  mapfile -t files <<< "$files_list"

  printf "$INFO_FMT" "processing ${#files[@]} month(s) for year $year"
  for fname in "${files[@]}"; do
    local infile="$INBOX/$fname"
    local month="${fname##*_}"
    month="${month%.txt}"
    printf "$INFO_FMT" "formatting month '$month' → '$year-$month.txt'"
    "$FORMAT_SCRIPT" "$infile" > "$year_dir/$year-$month.txt"
  done

  local archive="$ARCHIVE/$year.zip"
  [[ -f $archive]] && local action="updating" || local action="creating"
  printf "$INFO_FMT" "'$action' archive '$(basename "$archive")'"
  (cd "$INBOX" && zip -qu "$archive" "${files[@]}" && rm -- "${files[@]}")
}

# ─── MAIN ──────────────────────────────────────────────────────────────────────
for file in "${src_files[@]}"; do
  rename_file "$file"
done

if (( ${#year_files_map[@]} )); then
  # list of years to update
  years=("${!year_files_map[@]}")
  printf "$INFO_FMT" "updating year(s): ${years[*]}"
  for yr in "${years[@]}"; do
    process_year "$yr" "${year_files_map[$yr]}"
  done
fi
