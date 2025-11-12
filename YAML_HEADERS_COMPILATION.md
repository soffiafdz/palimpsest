# YAML Headers Compilation

**Analysis of journal/content/md markdown files**

This document compiles all examples of YAML headers that extend beyond the minimal set of fields:
- `date`
- `word_count`
- `reading_time`

## Summary

- **Total markdown files found**: 380
- **Files with parseable YAML headers**: 373
- **Files with additional fields**: 33

## All Unique Fields Found

Based on analysis of all 373 files with YAML headers:

| Field | Frequency | Description |
|-------|-----------|-------------|
| `date` | 373 files | Date of journal entry |
| `word_count` | 373 files | Word count of entry |
| `reading_time` | 373 files | Estimated reading time in minutes |
| `city` | 29 files | City where entry was written |
| `dates` | 28 files | Timeline of referenced dates/events |
| `people` | 28 files | People mentioned in entry |
| `epigraph` | 27 files | Opening quote or passage |
| `tags` | 26 files | Thematic tags for categorization |
| `notes` | 25 files | Editorial notes about the entry |
| `events` | 21 files | Named events or story arcs |
| `epigraph_attribution` | 19 files | Source of epigraph |
| `locations` | 15 files | Specific locations mentioned |
| `poems` | 5 files | Original poems included |
| `references` | 5 files | External references (songs, films, poems) |

---

## Complete Examples of Extended YAML Headers

### Example 1: Full Featured Entry
**File**: `journal/content/md/2024/2024-11-28.md`

```yaml
---
city: Montréal
date: 2024-11-28
dates:
  - date: '.'
    context: 'Meeting with @Louis; @Meli sent an email; talks with @Majo and @Paty; tell @Alda about idea for date with @Clara.'
  - date: 2024-11-29
    context: "@Aliza's Candidacy and plans about bar after."
epigraph: |
  Los he visto parar el tiempo al curvarse en un gesto.
  He probado de ellos el futuro en un beso sabor a promesa.
  Pero de tus labios, lo que más me fascina,
  es cuando dibujan sobre la noche mi nombre en un susurro.
events:
  - Dating-Clara
notes: |
  Reference to the night of the Museo Memoria & Tolerancia with Paty.
  Reference to Misael's party in Xochimilco.
  Look up the date of both.
  I talked with Alda about the card game I later played with Clara.
  Used ChatGPT to translate the poem to French.
people:
  - Louis
  - '@Meli (Melissa)'
  - '@Majo'
  - '@Paty'
  - Aliza
  - Alda
  - Clara
poems:
  - title: 'tus labios'
    content: |
      Los he visto parar el tiempo al curvarse en un gesto.
      He probado de ellos el futuro en un beso sabor a promesa.
      Pero de tus labios, lo que más me fascina,
      es cuando dibujan sobre la noche mi nombre en un susurro.
reading_time: 3.0
tags:
  - Emails
  - Old-pictures
  - Memories
  - Friendship
word_count: 776
---
```

---

### Example 2: Entry with Attributed Epigraph
**File**: `journal/content/md/2024/2024-11-12.md`

```yaml
---
city: Montréal
date: 2024-11-12
dates:
  - date: '~'
  - date: 2024-11-11
    context: '#Thomson-House with @Majo'
  - date: '.'
    context: '@Paty reached out on IG. Mock Candidady of @Aliza. Found mice.'
    locations:
      - Boulangerie Jarry
      - Metro
      - Station Sherbrooke
    people:
      - Didier
      - Vicky
      - Alda
  - date: 2024-11-13
    context: 'Talk about video-call with @Majo and @Aliza, before my session with @Fabiola'
epigraph: Je t'écris pour t'informer que je viens de voir une souris courir dans mon appartemant.
epigraph_attribution: Sofía
events:
  - Candidacy-Aliza
locations: null
notes: Mock candidacy of Aliza. First appearance of mice in the appartment.
people:
  - Didier
  - '@Majo'
  - '@Paty'
  - '@Vicky'
  - Aliza
  - Alda
  - Fabiola
reading_time: 3.1
tags:
  - Mice
  - Candidacy
word_count: 810
---
```

---

### Example 3: Entry with Poem
**File**: `journal/content/md/2024/2024-12-08.md`

```yaml
---
city: Montréal
date: 2024-12-08
dates:
  - '2024-12-07 (@Clara rainchecks with an IG voice message.)'
  - '2024-12-08 (Last date of the year with @Clara in my house.)'
epigraph: |
  I reach for the night we invented love, but the stars blur, their edges
  unspoken.

  A memory fading between dream and shadow, a moment unraveling in silence, its
  heartbeat dimmed, its warmth scattered like ashes.

  Tell me—did you feel it too, this quiet undoing?

  Or is it only me, grieving a ghost I can no longer hold?
events:
  - Dating-Clara
locations:
  - Station Jarry
notes: I realized I can't remember when I lost my virginity. Voice message from Clara.
people: Clara
poems:
  - title: 'I lost the night we invented love'
    content: |
      I reach for the night we invented love, but the stars blur, their edges
      unspoken.

      A memory fading between dream and shadow, a moment unraveling in silence, its
      heartbeat dimmed, its warmth scattered like ashes.

      Tell me—did you feel it too, this quiet undoing?

      Or is it only me, grieving a ghost I can no longer hold?
reading_time: 3.0
tags:
  - Date
  - Voice
word_count: 767
---
```

---

### Example 4: Entry with External References
**File**: `journal/content/md/2025/2025-03-11.md`

```yaml
---
date: 2025-03-11
dates:
  - date: '?? Majo & Emily'
    context: 'Told @Fabiola about my meeting, and disliking @Emily, and how @Majo asked me how worried she should have been about my state.'
  - date: '?? Date with Anne-Sophie'
    context: 'Remember having a date with @Anne-Sophie at #Café-Velours'
  - date: 2025-03-10
    context: 'I tell the lab I feel sick and will skip the meeting; trouble sleeping at night.'
    people:
      - Louis
      - Daniel
  - date: '.'
    people:
      - Fabiola
      - Sonny
      - Yuval
      - Alda
    locations:
      - BAnQ
      - La Taverne Atlantic
      - Oui mais non
epigraph: |
  Y, ¿de qué sirve hablar? No te quiero ver.
  ¿De qué sirve verte si no te puedo tener aquí?
  Y verte así.
events: Fading-Clara
notes: |
  Let her go, says Sonny.
  What do you want from her?, asked Fabiola
people:
  - Louis
  - Daniel (Daniel Andrews)
reading_time: 5.8
references:
  content: |
    Y, ¿de qué sirve hablar? No te quiero ver.
    ¿De qué sirve verte si no te puedo tener aquí?
    Y verte así.
  source:
    type: song
    title: 'nadie va a pensar en ti mejor que yo'
    author: Ed Maverick
tags:
  - Therapy
  - Depression
word_count: 1519
---
```

---

### Example 5: Entry with Literary Reference
**File**: `journal/content/md/2025/2025-02-28.md`

```yaml
---
city: Montréal
date: 2025-02-28
dates:
  - '2025-02-25 (Indian dinner with @Sarah at Laval. @Myriam proposed to meet mid-March. Redownloaded IG using @Paty as an excuse.)'
  - '2025-02-26 (I received the first vial of E2. I watch Y tu mamá también with @Majo. We read the Tarot.)'
  - '2025-02-27 (Did not leave the apartment, I ordered two regular A&W burgers despite the initiative to be vegetarian. Then I did not sleep.)'
  - '. (Sexting with Gaelle. I texted @Clara at 4h54 - hey. i miss you.)'
epigraph: |
  Tenoch se disculpó. Su novia lo esperaba para ir al cine. Julio insistió en
  pagar la cuenta.

  Nunca volverán a verse.

  "Nos hablamos, ¿no?"

  "Sí..."
events:
  - Fading-Clara
  - HRT-smuggling
  - Two-white-spaces
notes: |
  I redownloaded IG using Paty's salence from Telegram as an excuse.
  I watch Clara's story and wonder if it's about a past, potentially death connection.
  Dance deleting and saving Clara's number again and again. Then, I redownloaded Tinder.
  Afterwards, I sent a text: Hey. i miss you.
people:
  - '@Catfisher (Emily)'
  - Lavi
  - Sarah
  - Myriam
  - Hilary
  - '@Paty'
  - '@Majo'
  - Gaelle
reading_time: 4.8
references:
  - content: |
      Tenoch se disculpó. Su novia lo esperaba para ir al cine. Julio insistió en
      pagar la cuenta.

      Nunca volverán a verse.

      "Nos hablamos, ¿no?"

      "Sí..."
    source:
      title: 'Y tu mamá también'
      author: Alfonso Cuarón
      type: film
tags:
  - Fabiola
  - IG-story
  - Tarot
word_count: 1248
---
```

---

### Example 6: Entry with Multiple Cities
**File**: `journal/content/md/2025/2025-01-11.md`

```yaml
---
city:
  - Montréal
  - Philadelphia
date: 2025-01-11
dates:
  - date: 2025-01-09
    context: '@Clara texts me about the playlist and asks me to meet the next day.'
    locations:
      - Philadelphia Airport
      - Montréal Airport
  - date: 2025-01-10
    context: 'That January night.'
    people:
      - Clara
      - Louis
    locations: Station Jarry
  - date: '.'
    context: '@Clara wakes me up and leaves in the morning. We forget about the negatives.'
epigraph: |
  "haha you got me there; although be warned that i might take this as permission to let my corniest side out"

  "Please yes"

  "you've become my favourite notification"

  "now stop making me smile like this"
epigraph_attribution: Sofía & Clara
events:
  - Dating-Clara
  - HRT-crisis
locations:
  Philadelphia:
    - Philadelphia Airport
  Montréal:
    - Montréal Airport
    - Station Jarry
notes: |
  I made appointments with Biron Lab, for D. Franck, and am informed of Perera's maternity leave.
  THAT night.
people:
  - Clara
  - '@Dr-Perera (Hashana Perera)'
  - '@Dr-Franck (Franck)'
  - Louis
reading_time: 3.7
tags:
  - Date
  - HRT
  - Meds
  - Drs
word_count: 960
---
```

---

### Example 7: Entry with Visual Reference
**File**: `journal/content/md/2025/2025-01-17.md`

```yaml
---
city: Montréal
date: 2025-01-17
dates:
  - "2025-01-10 (When talking about the dagger's tattoo on @Clara leg, 'we're watching it right now!' she exclaims.)"
  - '2025-01-16 (@Louis proposes scheduling a meeting with @Sylvia and/or @Madeline, our meeting with @Mallar is confirmed; told @Clara about the HRT fiasco.)'
  - '. (@Majo is flying back from Costa Rica. @Clara replies and tells me about her moving.)'
  - '2025-01-19 (Rescheduled my meeting with @Majo. Will pick up my last HRT prescription at the #Pharmacy)'
epigraph: hey cee, what would you prefer to do?
epigraph_attribution: Sofía
events:
  - Dating-Clara
  - HRT-crisis
notes: Propose Clara to meet.
people:
  - Clara
  - '@Majo'
  - Sonny
  - Louis
  - Sylvia
  - Madeline
  - Mallar
  - Houssein
reading_time: 3.0
references:
  - description: "Clara's tattoo on her leg"
    mode: visual
    source:
      title: Princess Mononoke
      type: film
      author: Miyasaki
tags:
  - Princess-Mononoke
  - HRT
  - Depression
  - Testosterone
  - Dysphoria
word_count: 772
---
```

---

### Example 8: Minimal Additional Metadata
**File**: `journal/content/md/2025/2025-02-04.md`

```yaml
---
date: 2025-02-04
dates: ~
notes: 'ChatGPT generated writing: Psychologist report'
reading_time: 4.4
word_count: 1154
---
```

---

### Example 9: Entry with Dialogue Epigraph
**File**: `journal/content/md/2024/2024-11-09.md`

```yaml
---
city: Montréal
date: 2024-2024-11-09
dates:
  - date: 2024-05-25
    context: 'Reference to why I wanted to cancel with @Vero - Party at the Church.'
  - date: 2024-11-08
    context: 'Went to #Falafel-Yoni with @Majo. Talked about @Clara and how it felt different. Went bar-hopping without entering any. Mentioned sex-dreams with @Alda and @Aliza'
    locations:
      - Station Laurier
      - Station Rosemont
      - Dieu du ciel!
      - Siboire
      - Henrietta
      - Datcha
      - Darling
      - Bifteck
      - Station Saint-Laurent
  - date: '.'
    context: 'Second date with @Clara at #La-Maison-de-Mademoiselle-Dumpling. Told her about @Vero and the party at the Church and Lasertag the next day.'
  - date: 2024-11-10
    context: 'Talk about going Lasertag with @Vero the next day.'
epigraph: |
  "We'll see each other again, right? ...I hope?"
  "Yeah. No, yes. Definitively."
epigraph_attribution: Clara & Sofía
events:
  - Dating-Clara
  - Friendship-Majo
people:
  - '@Majo'
  - Alda
  - Aliza
  - Clara
  - '@Vero (Veronica)'
reading_time: 3.7
tags:
  - Sex-dream
  - Date
word_count: 970
---
```

---

### Example 10: Entry with Poetry Reference
**File**: `journal/content/md/2025/2025-03-05.md`

```yaml
---
city: Montréal
date: 2025-03-05
dates:
  - date: 2025-03-04
    context: 'I meet with @Majo and @Emily at Thomson. Dinner with @Majo at #Greenspot. Another sleepless night.'
    people:
      - Majo
      - Emily
    locations:
      - BAnQ
      - Thomson House
      - Greenspot
      - Station Peel
  - date: '.'
    context: "I don't sleep. I go from missing @Clara at 1h, to wishing her good-riddance at 5h. I work a full day at #The-Neuro."
epigraph: |
  No llegaré a saber
  por qué ni cómo nunca
  ni si era de verdad
  lo que dijiste que era
notes: |
  I meet/talk more with Emily and realize I don't like her.
  Majo and I remain afte Emily leaves. She suggests I am in a mixed episode.
  They kick us out from Thomson after it closes..
  We have dinner at Greenspot (have we been there before?)
  I read all the IG conversation with Clara. I go from missing her to not caring.
  I go to work after a sleepless night.
people:
  - '@Majo'
  - Emily
reading_time: 4.1
references:
  - content: |
      No llegaré a saber
      por qué ni cómo nunca
      ni si era de verdad
      lo que dijiste que era
    source:
      title: 'Ya no será'
      author: Idea Vilariño
      type: poem
tags:
  - Mania
  - Testosterone
word_count: 1063
---
```

---

## Field Descriptions and Conventions

### Core Fields (Present in all files)
- **date**: ISO format date (YYYY-MM-DD)
- **word_count**: Integer count of words
- **reading_time**: Float representing minutes

### Extended Fields

#### **city**
Location where the entry was written. Can be:
- Single string: `city: Montréal`
- Array of strings: `city: [Montréal, Philadelphia]`

#### **dates**
Timeline of events referenced in the entry. Formats include:
- Dictionary with `date` and `context` keys
- Can include nested `people` and `locations`
- Special date values:
  - `'.'` = current date (date of entry)
  - `'~'` = uncertain/approximate date
  - `'??'` = unknown date with description
- Can be simple string list for brief timeline

#### **epigraph**
Opening quote or passage, often poetic. Uses multiline YAML format (`|`)

#### **epigraph_attribution**
Source of the epigraph. Can be:
- Single name: `Sofía`
- Multiple: `Sofía & Clara`

#### **events**
Named story arcs or ongoing events. Examples:
- `Dating-Clara`
- `HRT-crisis`
- `Candidacy-Aliza`
- `Fading-Clara`
- `Two-white-spaces`

#### **locations**
Physical places mentioned. Can be:
- Simple list: `[Station Jarry, BAnQ]`
- Nested by city:
  ```yaml
  locations:
    Philadelphia: [Philadelphia Airport]
    Montréal: [Station Jarry]
  ```

#### **notes**
Editorial notes about the entry, meta-commentary, or context for future reference

#### **people**
People mentioned in the entry. Conventions:
- `@Name` = significant/tagged person
- `Name (Full Name)` = clarification of identity
- Can be simple list or included in `dates` entries

#### **poems**
Original poetry included in entry. Structure:
```yaml
poems:
  - title: 'poem title'
    content: |
      poem text here
      multiple lines
```

#### **references**
External works referenced (songs, films, poems, books). Structure:
```yaml
references:
  - content: |
      quoted text
    source:
      title: 'Work Title'
      author: Creator Name
      type: song|film|poem|book
    description: optional description
    mode: visual|textual (optional)
```

#### **tags**
Thematic categorization. Common tags:
- Emotional: `Depression`, `Therapy`, `Mania`
- Medical: `HRT`, `Meds`, `Testosterone`
- Social: `Date`, `First-date`, `Kiss`
- Identity: `Trans`, `Bipolar`, `Dysphoria`
- Activities: `Tarot`, `IG-story`
- Locations: `Pharmacy`, `Thomson-House`

---

## Parsing Notes

### Files with YAML Parse Errors (7 files)
Some files have malformed YAML headers due to:
1. Unescaped colons in multiline content
2. Missing quotes around strings with special characters
3. Poetry/prose mistakenly included in header section

Files with errors:
- `2024/2024-11-29.md`
- `2024/2024-11-08.md`
- `2024/2024-11-27.md`
- `2025/2025-03-06.md`
- `2025/2025-03-02.md`
- `2025/2025-01-19.md`
- `2025/2025-01-18.md`

### Minimal Examples (340 files)
The majority of entries (340 out of 373) contain only the three minimal fields:
```yaml
---
date: 2021-12-05
word_count: 758
reading_time: 2.9
---
```

---

## Statistical Overview

**Distribution of Extended Fields:**
- 29 entries (7.8%) include `city`
- 28 entries (7.5%) include `dates` timeline
- 28 entries (7.5%) include `people` metadata
- 27 entries (7.2%) include `epigraph`
- 26 entries (7.0%) include `tags`
- 25 entries (6.7%) include `notes`
- 21 entries (5.6%) include `events`
- 5 entries (1.3%) include original `poems`
- 5 entries (1.3%) include external `references`

**Time Distribution:**
Extended YAML headers appear primarily in:
- 2024-2025 entries (most recent)
- Concentrated around November 2024 - March 2025
- Earlier entries (2021-2023) predominantly use minimal format

This suggests an evolution in the journaling practice toward richer metadata and cross-referencing over time.

---

*Generated: 2025-11-12*
*Source: journal/content/md (380 markdown files)*
*Parser: parse_yaml_headers.py*
