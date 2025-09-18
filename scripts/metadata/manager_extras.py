def _update_entry_relationships(
    self, session: Session, entry: Entry, metadata: Dict[str, Any]
) -> None:
    """
    Update all many-to-many relationships for a given entry_list
    based on its Markdown metadata.

    Handles both simple string entries and dictionaries with extra fields.

    Args:
        session (Session): Active SQLAlchemy session
        entry (Entry): The database Entry object to update
        metadata (Dict[str, Any]): Parsed metadata from Markdown file

    Relationships updated:
        Mentioned dates, locations, people, references, events, poems, tags

    Returns:
        None

    Raises:
        Any exception raised during session operations
        Exceptions will propagate unless handled by the calling function
    """
    # MentionedDates
    for date_val in metadata.get("mentioned_dates", []):
        if isinstance(date_val, str) and date_val.strip():
            try:
                dt: date = datetime.strptime(date_val.strip(), "%Y-%m-%d").date()
                date_obj = self._get_or_create_lookup_item(
                    session, MentionedDate, dt, column_name="dates"
                )
                self._append_lookup()
            except ValueError:
                warnings.warn(f"Invalid date format: {date_str}")
                continue
        elif isinstance(date_str, date):
            parsed_date = date_str
        else:
            continue

        self._append_lookup(
            session, entry.dates, MentionedDate, parsed_date, column_name="date"
        )

    # People
    for person_name in metadata.get("people", []):
        if isinstance(person_name, str) and person_name.strip():
            self._append_lookup(session, entry.people, Person, person_name)

    # Tags
    for tag_name in metadata.get("tags", []):
        if isinstance(tag_name, str) and tag_name.strip():
            self._append_lookup(session, entry.tags, Tag, tag_name)

    # Locations
    for location_data in metadata.get("location", []):
        if isinstance(location_data, str) and location_data.strip():
            location = self._get_or_create_lookup_item(
                session, Location, location_data.strip()
            )
            entry.locations.append(location)
        elif isinstance(location_data, dict):
            name = location_data.get("name", "").strip()
            if name:
                extra_fields = {
                    "canonical_name": location_data.get("canonical_name"),
                    "parent_location": location_data.get("parent_location"),
                    "location_type": location_data.get("location_type"),
                    "coordinates": location_data.get("coordinates"),
                }
                location = self._get_or_create_lookup_item(
                    session, Location, name, **extra_fields
                )
                entry.locations.append(location)

    # Events
    for event_data in metadata.get("events", []):
        if isinstance(event_data, str) and event_data.strip():
            event = self._get_or_create_lookup_item(session, Event, event_data.strip())
            entry.events.append(event)
        elif isinstance(event_data, dict):
            name = event_data.get("name", "").strip()
            if name:
                extra_fields = {
                    "category": event_data.get("category"),
                    "notes": event_data.get("notes"),
                }
                event = self._get_or_create_lookup_item(
                    session, Event, name, **extra_fields
                )
                entry.events.append(event)

    # References
    for ref_data in metadata.get("references", []):
        if isinstance(ref_data, str) and ref_data.strip():
            reference = self._get_or_create_lookup_item(
                session, Reference, ref_data.strip()
            )
            entry.references.append(reference)
        elif isinstance(ref_data, dict):
            content = ref_data.get("content", "").strip()
            if content:
                ref_type = None
                if ref_data.get("type"):
                    ref_type = self._get_or_create_lookup_item(
                        session, ReferenceType, ref_data["type"]
                    )

                extra_fields = {
                    "type_id": ref_type.id if ref_type else None,
                    "metadata": (
                        json.dumps(ref_data.get("metadata", {}))
                        if ref_data.get("metadata")
                        else None
                    ),
                    "url": ref_data.get("url"),
                }
                reference = self._get_or_create_lookup_item(
                    session, Reference, content, **extra_fields
                )
                entry.references.append(reference)


def update_entry_from_file(self, file_path: str) -> bool:
    """
    Insert or update an Entry in the database from a Markdown file.

    - Parse YAML/md metadata from file
    - Compute the file hash to detect changes
    - If no changes, skip
    - Insert/update Entry rown and its related lookup tables
        Dates, Locations, People, References, Events, Poems, Tags
    - Commit the transaction

    Args:
        file_path (str | Path): Path to the markdown file

    Returns:
        bool:
            True if entry was created/updated
            False if skipped due to no changes or parsing failure

    Raises:
        Prints and rolls back on any SQLAlchemy/database exception
    """
    metadata = self.parse_markdown_metadata(file_path)
    if not metadata:
        return False

    # TODO: fix this broken reference
    file_hash = self._get_file_hash(file_path)

    with self.get_session() as session:
        try:
            existing_entry = session.query(Entry).filter_by(file_path=file_path).first()

            if existing_entry and existing_entry.file_hash == file_hash:
                return False

            entry_data = {
                "file_path": file_path,
                "date": metadata.get("date", ""),
                "word_count": self._extract_number(metadata.get("word_count", 0)),
                "reading_time": float(
                    self._extract_number(metadata.get("reading_time", 0.0))
                ),
                "status": metadata.get("status", "unreviewed"),
                "excerpted": metadata.get("excerpted", False),
                "epigraph": metadata.get("epigraph", ""),
                "notes": metadata.get("notes", ""),
                "file_hash": file_hash,
            }

            if existing_entry:
                for key, value in entry_data.items():
                    setattr(existing_entry, key, value)
                entry = existing_entry
            else:
                entry = Entry(**entry_data)
                session.add(entry)

            if existing_entry:
                entry.people.clear()
                entry.tags.clear()
                entry.locations.clear()
                entry.events.clear()
                entry.references.clear()

            self._update_entry_relationships(session, entry, metadata)
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            print(f"Error updating entry {file_path}: {e}")
            return False
