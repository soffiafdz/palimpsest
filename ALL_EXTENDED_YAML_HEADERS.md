# Complete Compilation of Extended YAML Headers

This document contains ALL examples of YAML headers that extend beyond the minimal set:
- `date`
- `word_count`
- `reading_time`

**Total files with extended headers: 40**

---

## Example 1: 2024-11-08.md

**File**: `journal/content/md/2024/2024-11-08.md`

**Additional fields**: author, city, context, dates, epigraph, epigraph_attribution, events, locations, mode, my news, every time I end with a request, notes, people, references, source, tags, title, type

*Note: YAML parsing encountered errors, showing raw content*

```yaml
---
date: 2024-11-08
word_count: 835
reading_time: 3.2
epigraph: &ref |
  Every day I send you an e-mail, in it I write
  my news, every time I end with a request: if
  you’re there and you’re well,
  don’t write back.
epigraph_attribution: &auth Tadeusz Dąbrowski
city: Montréal
# If Locatons don't appear here but below and city can be inferred, accept it.
# People is needed due to alias/name/full-name heuristics.
people:
  - "@The-Editor (Bea)"
  - "@Majo (María-José)"
  - Clara
  - Sonny
  - "@Paty (Patricia)"
  - "@Vicky (Victoria)"
  - Louis
  - Marc-Antoine
  - "@Sasha (Alexandra)"
  - Raphaël
  - "@Mom (Laura)"
events: [Dating-Clara]
dates:
  - date: 2024-04-24
    # TODO: Make sure people and locations from context are merged with their own fields
    context: "Date at #Typhoon-Lounge and night with @Bea; Sent @Majo related journal snapshot."
    locations: Bea's
  - date: 2024-11-02
    context: "First date with @Clara at #Chez-Ernest and then #A&W."
  - date: 2024-11-07 
    # TODO: Make sure people and locations can be inferred from context
    context: "@Bea appears on Tinder; Vicky organized drinks evening at #Thomson-House. I post IG story with the sweater made by my @Mom."
    people: [Sasha, Marc-Antoine, Raphaël, Sonny, Paty, Clara]
    locations: The Neuro
  - date: .
    context: "@Clara went back to like the IG story she had seen the day before."
    locations: La graine brûlée
references:
  - content: *ref
    source:
      title: Orpheus and Eurydicus
      author: *auth
      type: poem
  - description: "Bea's tattoo on her leg"
    mode: visual
    source:
      title: To the Lighthouse
      type: book
      author: Virginia Woolf
tags: [Date, First-date, Introduction, IG-story, IG-return]
notes: Beginning of Clara arc: introduction and first date.
---
```

---

## Example 2: 2024-11-09.md

**File**: `journal/content/md/2024/2024-11-09.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, people, tags

```yaml
---
date: 2024-11-09
word_count: 970
reading_time: 3.7
epigraph: |
  "We'll see each other again, right? ...I hope?"
  "Yeah. No, yes. Definitively."
epigraph_attribution: Clara & Sofía
city: Montréal
people: ["@Majo", Alda, Aliza, Clara, "@Vero (Veronica)"]
dates:
  - date: 2024-05-25
    context: Reference to why I wanted to cancel with @Vero - Party at the Church.
  - date: 2024-11-08
    context: "Went to #Falafel-Yoni with @Majo. Talked about @Clara and how it felt different. Went bar-hopping without entering any. Mentioned sex-dreams with @Alda and @Aliza"
    locations:
      # TODO: When list, do not de-hyphenate.
      [
        Station Laurier,
        Station Rosemont,
        Dieu du ciel!,
        Siboire,
        Henrietta,
        Datcha,
        Darling,
        Bifteck,
        Station Saint-Laurent,
      ]
  - date: .
    context: "Second date with @Clara at #La-Maison-de-Mademoiselle-Dumpling. Told her about @Vero and the party at the Church and Lasertag the next day."
  - date: 2024-11-10
    context: Talk about going Lasertag with @Vero the next day.
events: [Dating-Clara, Friendship-Majo]
tags: [Sex-dream, Date]
---
```

---

## Example 3: 2024-11-11.md

**File**: `journal/content/md/2024/2024-11-11.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, locations, notes, people, tags

```yaml
---
date: 2024-11-11
word_count: 1701
reading_time: 6.5
epigraph: Dear diary, today, with @aldaprofka and @vero.raphael, I discovered there is actually some fun in killing 8 year olds
epigraph_attribution: Sofía
city: Montréal
people:
  - Alda
  - Renzo
  - Aliza
  - "@Vlad (Vladyslav)"
  - Valerie
  # TODO: Confirm if without context aliases are treated as a single entry
  - "@The couple"
  - "@NB Postdoc"
  - Sophie
  - "@Vero (Veronica)"
  - "@Vero's brother (Peter)"
  - Rowan
  - Bliss
  - Walter
  - Johnathan
  - Sylvia
  - "@Majo"
  - Emily
  - Neda
  - Daniel (Daniel Andrews)
  - Clara
  - "@Paty (Patricia)"
locations:
  - Thomson House
dates:
  #- date: Somewhen??
  #  context: "Went to #N with @NB-Postdoc"
  #- date: Somewhen??
  #  context: "Went to #N with @The-couple"
  - date: 2024-03-08
    context: "Think back about last date with @Sophie at #N."
  - date: 2024-10-15
    context: "Memory of meeting @Renzo back with @Alda of Chinese Noodles & #Old-Port."
    # TODO: Confirm this spelling
    locations: Lang-zhou Noodles
    #  - date: Somewhen??
    #  context: "Went to #McKibbins with @Aliza and @Vlad"
    #- date: Somewhen??
    #  context: "Went to #McKibbins with @Valerie"
  - date: 2024-11-10
    context: "Indian Food with @Renzo and then Birthday party of @Vero."
    locations: [Bawarchi, McDonald's, Vero's, Lasertag]
    people: [Alda, "@Vero's brother (Peter)", Rowan, Bliss]

  - date: .
    context: "Bought coffee beans for birthday of @Walter at @Baristello; Student's and Postdoc's Seminar; #Thomson-House with @Majo."
    people:
      [Johnathan, Sylvia, Emily, Neda, Daniel (Daniel Andrews), Clara, Paty]
tags: [Introduction]
notes: |
  Busy entry full of references.
  Mentioned:
  - meeting Renzo (approx Oct, Old Port);
  - a night out with Aliza and her lab & a date with Valerie (??, McKibbins);
  - date with the @Couple (~2022) & the @NB Postdoc (??) and Sophie (24-03-08) N
---
```

---

## Example 4: 2024-11-12.md

**File**: `journal/content/md/2024/2024-11-12.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, locations, notes, people, tags

```yaml
---
date: 2024-11-12
word_count: 810
reading_time: 3.1
epigraph: Je t’écris pour t’informer que je viens de voir une souris courir dans mon appartemant.
epigraph_attribution: Sofía
city: Montréal
# TODO: If just one date, use locations field. No need for redundancy.
locations:
  # Figure out what will happen with all the merging context of MentionedDates.
  # It should be a field of the Entry-Date relationship, as it heavily depends on Entry.
  # People & Locations should merge in their own relationships.
  # TODO: Consult with Claude.
dates:
  # TODO: Check if ~ goes on its own field or it's inside date.
  - date: "~"
  - date: 2024-11-11
    context: "#Thomson-House with @Majo"
  - date: .
    context: "@Paty reached out on IG. Mock Candidady of @Aliza. Found mice."
    locations: [Boulangerie Jarry, Metro, Station Sherbrooke]
    people: [Didier, "Vicky", Alda]
  - date: 2024-11-13
    context: "Talk about video-call with @Majo and @Aliza, before my session with @Fabiola"
# TODO: If just one date, use people field. No need for redundancy.
people: [Didier, "@Majo", "@Paty", "@Vicky", Aliza, Alda, Fabiola]
events: [Candidacy-Aliza]
tags: [Mice, Candidacy]
notes: Mock candidacy of Aliza. First appearance of mice in the appartment.
---
```

---

## Example 5: 2024-11-13.md

**File**: `journal/content/md/2024/2024-11-13.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2024-11-13
word_count: 772
reading_time: 3.0
epigraph: |
  So you enjoyed [it] generally speaking?
  Also, there are not a lot of places where you can fight children legitimately
epigraph_attribution: Clara
city: Montréal
dates:
  - date: 2024-11-11
    context: "Conversation with @Majo regarding @Clara at #Thomson-House."
  - date: 2024-11-12
    context: Mice appearance.
  - date: .
    context: "Video-call with @Aliza and @Majo; Session with @Fabiola; #Oui-mais-non with @Alda."
people:
  ["@Clarabelais (Clara)", Aliza, Fabiola, Didier, Sophie, "@Majo", Alda, Louis]
events: [Candidacy-Aliza]
tags: [Therapy, IG-story, IG-return]
notes: Told Fabiola worries about parallels between Clara & Sophie. Clara revient à IG.
---
```

---

## Example 6: 2024-11-14.md

**File**: `journal/content/md/2024/2024-11-14.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2024-11-14
word_count: 1509
reading_time: 5.8
epigraph: hey, i really want to see you. it's very short notice, but are you free tomorrow? or this weekend?
epigraph_attribution: Sofía
city: Montréal
dates:
  # TODO: Double-check this
  - date: 2024-11-16
    context: "Make plans of going to #Cinéma-Moderne with @Miriam"
  - date: .
    context: Birthday of @Walter and first date with @Florence.
    locations: [The Neuro, McDonald's, Walter's, Brewsky, Station Jarry]
    # TODO: Check that the person mentioned in the dates MUST BE one of the ones in people.
    people:
      [
        Louis,
        Sasha,
        Marc-Antoine,
        Raphaël,
        Reza,
        Aliza,
        Melissa,
        Amélie,
        Jana,
        Mónica,
        Clara,
      ]
people:
  - "@Majo"
  - Walter
  - Florence
  - Louis
  - "@Sasha"
  - Marc-Antoine
  - Raphaël
  - Reza
  - Aliza
  - Clara
  - Miriam
  - "@Walter's friend (Melissa)"
  - Amélie
  - Jana
  - Mónica
events: [Dating-Clara]
tags: [Date, First-date, Motherhood, Pregnancy, Tarot, Trans, Bipolar]
notes: Mentions of pregnancy/menstruation dreams (unkwown dates). Intersection of themes about motherhood, bipolar and transness.
---
```

---

## Example 7: 2024-11-15.md

**File**: `journal/content/md/2024/2024-11-15.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2024-11-15
word_count: 859
reading_time: 3.3
epigraph: hi Sofía, sorry i am not really
epigraph_attribution: Clara
city: Montréal
dates:
  # TODO: All contexts should be converted into a set ordered by the date of the Entry they were mentioned in.
  # That way, everything is together for dates that don't have their own entry.
  # TODO: Correct these with actual date
  #- date: ???
  #  context: Posting picture of "old me" on IG
  #- date: Alexia's date
  #  context: Think about night with @Alexia to masturbate.
  #- date: Date with @The-couple
  #  context: Think about @The-couple and what could have happened to masturbate.
  # TODO: When people are "remembered", should they be in their own date or the date they were remembered in???
  # For now, keep both. The reference of what was remembered and the act of remembering (IF SIGNIFICANT TO THE DAY).
  - date: 2024-11-14
    context: Remember context of @Florence being hospitalized. Then, stream of memories as I masturbate that night.
    people: [Alexia, The couple, Mónica]
  # Consider using `.` to signal entry's date as `~` to signal NOT entry's date
  - date: .
    context: "@Sonny thinks I'm manic. "
    people: [Alda, Clara, Majo]
people:
  -
  - Sonny
  - "@Clarabelais (Clara)"
  - Florence
  - Alexia
  - "@The-couple"
  - "@Majo"
  - Alda
  - Mónica
events: [Dating-Clara]
tags: [Hypomania, Bipolar, Old-pictures]
notes: |
  References to bipolar impulsivity:
  The night I went with the couple (what's their name?).
  The urge to post a pre-transition picture.
  Fantasy with the couple (beyond the limits of sexuality).
---
```

---

## Example 8: 2024-11-16.md

**File**: `journal/content/md/2024/2024-11-16.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2024-11-16
word_count: 864
reading_time: 3.3
epigraph: |
  Yeah I'd love to.

  Thinking about you now cause I quickly went to support a friend doing stand up in a Mexican place, everything is in Spanish and I'm the only persona non Latina, experiencing your church feeling tonight.
epigraph_attribution: Clara
city: Montréal
dates:
  - date: 2024-11-15
    context: "@Clara replies to my text mentioning her going to the Stand-up in Spanish."
    people: [Majo]
  - date: .
    context: "Short-films with @Miriam at #Cinéma-Moderne. Pass by the #Pharmacy but it's closed."
    people: Misael
  - date: 2024-11-17
    context: "Plans to meet with @Alex at #Old-Port & brunch with @Sarah"
people: [Clara, "@Majo", Miriam, "@Elio (Alex)", Sarah, Misael]
events: [Dating-Clara]
tags: [Skipped-dose, Tinder]
notes: |
  This message is extremely significant.
  The stand-up friend Clara went to see is the same man she dances with next year and is seen kissing by Majo.
  Similarly Majo sends a reel: "Nos ilusionaste a las dos porque yo viví su historia como si fuera mía."
  "Cuando lo de Clara no se de, vamos a sufrir las dos"
---
```

---

## Example 9: 2024-11-19.md

**File**: `journal/content/md/2024/2024-11-19.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, locations, notes, people, tags

```yaml
---
date: 2024-11-19
word_count: 749
reading_time: 2.9
epigraph: |
  Are free anytim this weekend?

  You*
epigraph_attribution: Clara
city: Montréal
locations: [Café Nocturne, Le toasteur, Parc Jarry, Pharmacy, Brewsky]
dates:
  - date: 2024-11-17
    context: "Brunch with @Sarah at #Le-toasteur; drinks with @Alex at #Brewsky."
    people: Miriam
    locations: [Café Nocturne, Parc Jarry, Pharmacy]
  - date: 2024-11-18
    context: "@Nicola liked me on Hinge; Meaningless chat with @Isabelle on Tinder. Talk about first kiss."
    people: [Aliza, Majo]
  - date: .
    context: Session with @Fabiola
people: [Sarah, Alex, Fabiola, Miriam, "@Majo", Aliza, Nicola, Isabelle]
tags: [Therapy, Depression, Sexual-assault]
notes: |
  Nicola liked me on Hinge, not remembering me. Isabelle is just an anonymous tinder match.
  I tell Majo & Aliza how my first kiss with Jessica could be sexual assault.
---
```

---

## Example 10: 2024-11-24.md

**File**: `journal/content/md/2024/2024-11-24.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2024-11-24
word_count: 2101
reading_time: 8.1
epigraph: I thought about it, but I wasn't sure on our first date. I knew it after the second. And now, right now, I really, really want to kiss you.
epigraph_attribution: Sofía
city: Montréal
dates:
  - date: "~"
  - date: 2024-11-21
    context: Double-texted @Clara proposing going to the movies.
  - date: 2024-11-22
    context: "@Majo brings up a conversation with @Aliza."
    locations: Oui mais non
  - date: 2024-11-23
    context: "Day with @Majo & her friends before third date with @Clara."
    people: [Lavi, Zahra]
    locations:
      [
        Lola Rosa,
        Complexe Desjardins,
        Station Berri-UQAM,
        La graine brûlée,
        UQAM,
        Isle de Garde,
        Station Beaubien,
      ]
people: ["@Majo", Aliza, Lavi, Zahra, Clara]
events: [Dating-Clara]
tags: [Date, Trans, Kiss, Disclosure]
notes: |
  Long day with Majo. "You should not concern whether she likes you, but if  you like her"
  First time meeting Lavi.
  Ne plus jamais tomber amoroux vs ne plus jamais baiser. "She died".
  Third date with Clara. Told her I am trans. First kiss.
---
```

---

## Example 11: 2024-11-27.md

**File**: `journal/content/md/2024/2024-11-27.md`

**Additional fields**: city, context, dates, epigraph, events, locations, notes, people, poems, tags

*Note: YAML parsing encountered errors, showing raw content*

```yaml
---
date: 2024-11-27
word_count: 792
reading_time: 3.0
epigraph: &poem |
Por años, el rojo fue mi color favorito.
Qué ingenua;
¿cómo podría comparar el fuego y el vino
con la cálida bienvenida de
su mirada turquesa e infinita,
incendiada en la luz ámbar de la madrugada?
Ofrecí venderle un secreto.
Qué ingenua;
¿cómo podría guardar cualquier misterio
si, al mirarme así y sin decir nada,
el océano inquieto de sus ojos
me desarma, me desnuda y me vuelve a vestir?
poems:
  - title: Mi color favorito
  - content: *poem
city: Montréal
dates:
  - date: 2024-11-24
    context: Feeling sick; posted IG story with mug from @Paty.
  - date: 2024-11-25
    context: Told @Clara I'm sick. Call with @Majo about mentioning the word regret.
  - date: 2024-11-26
    context: Posted IG story about going to Mexico that @Paty saw.
  - date: .
    context: "@Aliza practiced her candidacy with @Majo and I; met with @Sarah; @Misael created group for his birthday."
    locations: Boulangerie Jarry
people: ["@Majo", Aliza, Louis, Sarah, Clara, "@Paty", Misael]
events: [Candidacy-Aliza, Dating-Clara]
tags: [Sick]
notes: |
  Sent awkward text about "regretting" our kiss due to being sick.
  Misael added Paty to the birthday group.
---
```

---

## Example 12: 2024-11-28.md

**File**: `journal/content/md/2024/2024-11-28.md`

**Additional fields**: city, dates, epigraph, events, notes, people, poems, tags

```yaml
---
date: 2024-11-28
word_count: 776
reading_time: 3.0
epigraph: &poem |
  Los he visto parar el tiempo al curvarse en un gesto.
  He probado de ellos el futuro en un beso sabor a promesa.
  Pero de tus labios, lo que más me fascina,
  es cuando dibujan sobre la noche mi nombre en un susurro.
poems:
  - title: tus labios
    content: *poem
city: Montréal
dates:
  # - date: ??
  #  context: "#Museo-Memoria-y-Tolerancia with @Paty"
  - date: .
    context: "Meeting with @Louis; @Meli sent an email; talks with @Majo and @Paty; tell @Alda about idea for date with @Clara."
  - date: 2024-11-29
    context: "@Aliza's Candidacy and plans about bar after."
#TODO: What's Melissa's last name??
people: [Louis, "@Meli (Melissa)", "@Majo", "@Paty", Aliza, Alda, Clara]
events: [Dating-Clara]
tags: [Emails, Old-pictures, Memories, Friendship]
notes: |
  Reference to the night of the Museo Memoria & Tolerancia with Paty.
  Reference to Misael's party in Xochimilco.
  Look up the date of both.
  I talked with Alda about the card game I later played with Clara.
  Used ChatGPT to translate the poem to French.
---
```

---

## Example 13: 2024-11-29.md

**File**: `journal/content/md/2024/2024-11-29.md`

**Additional fields**: city, content, context, dates, epigraph, events, locations, notes, people, poems, tags

*Note: YAML parsing encountered errors, showing raw content*

```yaml
---
date: 2024-11-29
word_count: 757
reading_time: 2.9
epigraph: &poem |
  I felt a quiet sadness after I wrote you a poem in my language, one you don't understand.

  Then, I was struck by how much more beautiful it reads in yours, a language I cannot speak.
poems:
  - title: my words, your language
    content: *poem
    notes: posted as an IG story with the photograph of the metro in a tunnel
  - title: strangers
    content: |
    I wonder if I write poems of people I have just met
    for the same reason I take photographs of people who do not know me
    Perhaps there is a particular beauty in creating art from complete strangers
    notes: |
    Posted as two IG stories.
    One blurry photograph of a stranger woman sitting on a bench in San Diego. 
    The second B&W of a man sitting beyond the pilars somewhere inside Central Park.
city: Montréal
locations: [Indigo, Urban Outfitters]
dates: 
  - date: 2024-11-28 
    context: Haven't replied to @Meli
  - date: .
    context: Shopping with @Alda for gifts for @Paty & @Misael; after-candidacy bar for @Aliza
    people: [Majo, Clara]
people: ["@Meli (Melissa)", Aliza, "@Majo", Misael, "@Paty", Alda, Clara]
events: [Candidacy-Aliza, Dating-Clara]
tags: [Emails, Insomnia, Post-midnight-stories, IG-stories]
notes: |
  Once again Clara returns to stories she has opened.
  I wondered if she read herself in the poems she liked or the ones she did not.
  Looked for presents for Misael.
---
```

---

## Example 14: 2024-12-03.md

**File**: `journal/content/md/2024/2024-12-03.md`

**Additional fields**: city, dates, epigraph, locations, notes, people, poems, tags

```yaml
---
date: 2024-12-03
word_count: 749
reading_time: 2.9
epigraph: &poem I miss the idea I built of you.
poems:
  - title: Muse
    content: *poem
city: Montréal
locations: [The Neuro]
dates:
  - 2024-11-29 (Renarrate shopping with @Alda and post-candidacy bar for @Aliza)
  - "2024-11-30 (Le Festival Triste at #Cinéma-Moderne with @Majo)"
  - 2024-12-01 (@Clara replied and told me about her housing issues.)
  - 2024-12-02 (Got irritated with @Sonny.)
  - ". (Sessions with @Franck and @Fabiola; got really drunk with raki before going to #Aliza's)"
people: [Franck, Fabiola, Aliza, Sonny, "@Majo", Clara]
tags: [Psychiatrist, Therapy, Meds, Alcohol, Raki, Dating-apps]
notes: |
  Increase the dose due to feeling down.
  Sips of *Raki*. Chekov's gun.
  Closed the apps.
---
```

---

## Example 15: 2024-12-04.md

**File**: `journal/content/md/2024/2024-12-04.md`

**Additional fields**: city, dates, epigraph, notes, people, poems, tags

```yaml
---
date: 2024-12-04
word_count: 760
reading_time: 2.9
epigraph: &poem |
  I shut close the drapes and turned off the lights.
  I took cover under the cold sheets, hiding myself
  from the coming storm within me.
poems:
  - title: The storm
    content: *poem
city: Montréal
dates:
  - "2024-12-03 (I told @Majo of feeling too drunk in the #Pharmacy before seeing @Aliza she tried to call me.)"
  - . (Cancelled my plans with @Majo; @Sonny transferred me the money for @Misael birthday.)
  - 2024-12-05 (Meeting with @Louis and postponed plans with @Majo.)
  - 2024-12-06 (Christmas lab lunch.)
people: [Aliza, Misael, "@María (María-José)", "@Majo (María-José)", Sonny]
tags: [Depression, Thesis, Raki, Dating, Motherhood]
notes: |
  Attended a talk about the process of thesis submission.
  Cancelled on Majo's plans.
  Fear of empty phone.
  "I am not capable of making life. Only death resides within me." (Dude, chill.)
---
```

---

## Example 16: 2024-12-08.md

**File**: `journal/content/md/2024/2024-12-08.md`

**Additional fields**: city, dates, epigraph, events, locations, notes, people, poems, tags

```yaml
---
date: 2024-12-08
word_count: 767
reading_time: 3.0
epigraph: &poem |
  I reach for the night we invented love, but the stars blur, their edges
  unspoken.

  A memory fading between dream and shadow, a moment unraveling in silence, its
  heartbeat dimmed, its warmth scattered like ashes.

  Tell me—did you feel it too, this quiet undoing?

  Or is it only me, grieving a ghost I can no longer hold?
poems:
  - title: I lost the night we invented love
    content: *poem
city: Montréal
locations: [Station Jarry]
dates:
  - 2024-12-07 (@Clara rainchecks with an IG voice message.)
  - 2024-12-08 (Last date of the year with @Clara in my house.)
people: Clara
events: [Dating-Clara]
tags: [Date, Voice]
notes: I realized I can't remember when I lost my virginity. Voice message from Clara.
---
```

---

## Example 17: 2025-01-11.md

**File**: `journal/content/md/2025/2025-01-11.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, locations, notes, people, tags

```yaml
---
date: 2025-01-11
word_count: 960
reading_time: 3.7
epigraph: |
  "haha you got me there; although be warned that i might take this as permission to let my corniest side out"

  "Please yes"

  "you've become my favourite notification"

  "now stop making me smile like this"
epigraph_attribution: Sofía & Clara
city: [Montréal, Philadelphia]
locations:
  Philadelphia: [Philadelphia Airport]
  Montréal: [Montréal Airport, Station Jarry]
dates:
  - date: 2025-01-09
    context: "@Clara texts me about the playlist and asks me to meet the next day."
    locations: [Philadelphia Airport, Montréal Airport]
  - date: 2025-01-10
    context: That January night.
    people: [Clara, Louis]
    locations: Station Jarry
  - date: .
    context: "@Clara wakes me up and leaves in the morning. We forget about the negatives."
people: [Clara, "@Dr-Perera (Hashana Perera)", "@Dr-Franck (Franck)", Louis]
events: [Dating-Clara, HRT-crisis]
tags: [Date, HRT, Meds, Drs]
notes: |
  I made appointments with Biron Lab, for D. Franck, and am informed of Perera's maternity leave.
  THAT night.
---
```

---

## Example 18: 2025-01-12.md

**File**: `journal/content/md/2025/2025-01-12.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2025-01-12
word_count: 751
reading_time: 2.9
epigraph: |
  well fuck

  it gets even worse
epigraph_attribution: Sofía
city: [Montréal, Tijuana]
# TODO: Find the name of this plaza in Tijuana by the border.
# locations:
# - Tijuana: "Plaza"
people:
  - "@Majo"
  - "@Dr-Perera"
  - Miguel (Miguel Ángel Fernández)
  - "@Mom (Laura)"
  - "@Les (Melissa Fernández)"
dates:
  - date: ???
    context: "Waiting for @Les with my @Mom, I walked through a small plaza testing my half-30mm."
    location: Plaza
  - date: .
    context: Research about DIY HRT. Attempt to fix Olympus camera.
events: [HRT-crisis, HRT-smuggling]
tags: [Film-camera, HRT, Meds]
notes: HRT crisis complicates. Research about buying DIY HRT.
---
```

---

## Example 19: 2025-01-16.md

**File**: `journal/content/md/2025/2025-01-16.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2025-01-16
word_count: 751
reading_time: 2.9
epigraph: Why what's happening?
epigraph_attribution: Clara
city: Montréal
dates:
  - 2025-01-05 (Remember how the last time I masturbated the mattress was soiled.)
  - "2025-01-13 (Lab meeting at #The-Neuro regarding @Louis grant; meeting @Alda at #Thomson-House, then moved to #Brutopia.)"
  - "2025-01-14 (Sick I went to #Biron; Therapy back home with @Fabiola; got bloodwork results.)"
  - "2025-01-24 (Made an appointment with the new Dr at the #Wellness-Hub)"
  - . (Bought crypto then ordered the E2 vial.)
people: [Louis, Alda, Fabiola, Sonny]
events: [HRT-crisis, Therapy, HRT-smuggling]
tags: [Testosterone, Therapy, HRT, Meds]
notes: HRT crisis complicates even further. Alarming hormones levels. Bought crypto then ordered the E2 vial.
---
```

---

## Example 20: 2025-01-17.md

**File**: `journal/content/md/2025/2025-01-17.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, references, tags

```yaml
---
date: 2025-01-17
word_count: 772
reading_time: 3.0
epigraph: hey cee, what would you prefer to do?
epigraph_attribution: Sofía
city: Montréal
dates:
  - 2025-01-10 (When talking about the dagger's tattoo on @Clara leg, 'we're watching it right now!' she exclaims.)
  - "2025-01-16 (@Louis proposes scheduling a meeting with @Sylvia and/or @Madeline, our meeting with @Mallar is confirmed; told @Clara about the HRT fiasco.)"
  - . (@Majo is flying back from Costa Rica. @Clara replies and tells me about her moving.)
  - "2025-01-19 (Rescheduled my meeting with @Majo. Will pick up my last HRT prescription at the #Pharmacy)"
people: [Clara, "@Majo", Sonny, Louis, Sylvia, Madeline, Mallar, Houssein]
events: [Dating-Clara, HRT-crisis]
tags: [Princess-Mononoke, HRT, Depression, Testosterone, Dysphoria]
references:
  - description: "Clara's tattoo on her leg"
    mode: visual
    source:
      title: Princess Mononoke
      type: film
      # TODO: Confirm director's name
      author: Miyasaki
notes: Propose Clara to meet.
---
```

---

## Example 21: 2025-01-18.md

**File**: `journal/content/md/2025/2025-01-18.md`

**Additional fields**: city, epigraph, epigraph_attribution, events, notes, people, tags

*Note: YAML parsing encountered errors, showing raw content*

```yaml
---
date: 2025-01-18
word_count: 746
reading_time: 2.9
epigraph: | 
According to Dr. Perera, other Wellness Hub doctors should know to refer patients seeking HRT to Hygea, and to refill the existing prescriptions of any patients worried about running out while on the Hygea wait list.

Patients should remember that they can ask for a copy of their endocrinology referral and submit it to any endo clinic, public or private. If patients ask for a general referral for HRT they can use it at any Montréal clinic with providers willing to prescribe HRT.
epigraph_attribution: Montréal Trans Patient Union
city: Montréal
people: [Hashana, "@Paty (Patricia)", Clara, "@Majo (María-José)"]
events: [HRT-crisis]
tags: [HRT]
notes: Start getting anxiety about the idea of 'having the conversation' with Clara.
---
```

---

## Example 22: 2025-01-19.md

**File**: `journal/content/md/2025/2025-01-19.md`

**Additional fields**: author, city, content, dates, epigraph, events, notes, people, poems, references, source, tags, title, type

*Note: YAML parsing encountered errors, showing raw content*

```yaml
---
date: 2025-01-19
word_count: 755
reading_time: 2.9
epigraph: &ref The snow was falling faintly through the universe and faintly falling on all
the living and the dead.
city: Montréal
dates:
  # - 2024-12-?? (Inside metro station the guard tells me I cannot take pictures.)
  - "2025-01-10 (I waited for Majo at the same spota I waited for @Clara at #Station-Jarry)"
  # TODO: Confirm that in my methods, when parsing words, to remove punctuation, including 's.
  - ". (Picked up the last HRT prescription before #Oui-mais-no; The Room Next Door at #Cinéma-du-Parc with @Majo.)"
people: ["@Majo"]
events: [HRT-crisis]
tags: [Post-midnight-stories, IG-stories]
poems:
  - title: Luces en los rieles
    content: |
      En el murmullo de venas eléctricas,
      el movimiento nos desdibuja.
      Nombres se desvanecen,
      anhelos dispersos como luces en los rieles.
      Aquí, entre reflejos y sombras,
      nos cruzamos sin mirarnos, sin saber siquiera
      si seguimos siendo nosotras.
references:
  - content: *ref
    source:
      title: The Room Next Door
      author: Almodóvar
      type: film
notes: Tell Majo how I am scared by the idea that my future with Clara has an expiration date.
---
```

---

## Example 23: 2025-02-02.md

**File**: `journal/content/md/2025/2025-02-02.md`

**Additional fields**: dates, notes

```yaml
---
date: 2025-02-02
word_count: 4682
reading_time: 18.0
dates: "~"
notes: "ChatGPT generated writing: Psychological deconstruction."
---
```

---

## Example 24: 2025-02-03.md

**File**: `journal/content/md/2025/2025-02-03.md`

**Additional fields**: dates, notes

```yaml
---
date: 2025-02-03
word_count: 1122
reading_time: 4.3
dates: "~"
notes: "ChatGPT generated writing: Psychiatric report"
---
```

---

## Example 25: 2025-02-04.md

**File**: `journal/content/md/2025/2025-02-04.md`

**Additional fields**: dates, notes

```yaml
---
date: 2025-02-04
word_count: 1154
reading_time: 4.4
dates: "~"
notes: "ChatGPT generated writing: Psychologist report"
---
```

---

## Example 26: 2025-02-08.md

**File**: `journal/content/md/2025/2025-02-08.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2025-02-08
word_count: 836
reading_time: 3.2
epigraph: If this were the way things end; if that ends up being our last goodbye... I think I am OK with that.
epigraph_attribution: Sofía
city: Montréal
dates:
  - "~"
  - date: 2025-01-25
    context: Eating dumplings with friends, then improptu date with @Clara.
    #TODO: Look into José's last name to avoid confusion with my dad.'
    people: [Alda, Renzo, "@José (José-Luis)"]
    locations: [Cinéma du Parc, Lola Rosa, Station Rosemont, Station Beaubien]
  - "2025-01-31 (Go to #The-Douglas to give a talk to @Aliza's lab; then dinner with @Majo.)" #TODO: Where???
  - 2025-02-04 (I text @Clara 'do i get to see you this week?' She hasn't replied.)
people: [Aliza, "@Majo", Clara]
tags: [Date]
events: [Dating-Clara]
notes: |
  I deleted IG. Clara reaches out sending me her phone number.
  First appearance of Sofibug. Date of January (best?).
  Ticket hidden in table's drawer. Fleeting kiss.
---
```

---

## Example 27: 2025-02-09.md

**File**: `journal/content/md/2025/2025-02-09.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2025-02-09
word_count: 858
reading_time: 3.3
epigraph: majo doesn't like clara anymore [...] eso me dio más tristeza que el ghosteo
epigraph_attribution: Sofía
city: Montréal
dates:
  - "2024-11-23 (Reintroduce the night I met @Lavi; she told @María she liked my makeup)"
  - date: 2025-02-08
    context: "Brunch with @María at #Larry's, walk around #Saint-Laurent, friperies, and a drink at #Dieu-du-ciel!"
  - ". (#Café Safran with @Majo and @Lavi; declined going to #Shub's and took the long way home instead.)"
people:
  - Aliza
  - "@Majo (María-José)"
  - "@María (María-José)"
  - Clara
  - "@Shub (Shubhendra)"
tags: Friendship
events: Fading-Clara
notes: |
  Explored the friperies and looked around St-Valentine cards.
  Parallelism between my night of January and Lavi's previous night with her date.
  Majo starts disliking Clara. Majo talks about the (ending) friendship with Aliza.
  After declining on going to Shub's house, I took the long way home.
---
```

---

## Example 28: 2025-02-10.md

**File**: `journal/content/md/2025/2025-02-10.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2025-02-10
word_count: 843
reading_time: 3.2
epigraph: le tomó el doble de días, pero, como jesucristo, clara ya resucitó
epigraph_attribution: Sofía
city: Montréal
dates:
  - ". (Lab's Movie Night #The-Neuro; @Clara apologizes for not replying.)"
people: ["@Majo", "@Clarizard (Clara)"]
tags: [Friendship, Testosterone, Dysphoria]
events: [Fading-Clara, HRT-crisis]
notes: |
  Explored the friperies and looked around St-Valentine cards.
  Parallelism between my night of January and Lavi's previous night with her date.
  Majo starts disliking Clara. Majo talks about the (ending) friendship with Aliza.
  After declining on going to Shub's house, I took the long way home.
---
```

---

## Example 29: 2025-02-13.md

**File**: `journal/content/md/2025/2025-02-13.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people

```yaml
---
date: 2025-02-13
word_count: 806
reading_time: 3.1
epigraph: |
  "Hey, I'd really like to see you this week. when are you free?"

  "Hey Sofibug
  "I might be free on Sunday, cancelling a hike because of the storm, if not then would Monday after work also do?"
epigraph_attribution: Sofía & Clara
city: Montréal
dates:
  - "2024-02-14 (In anxiety of the next one, thought back to last Valentine's with @Sophie at #Thomson-House)"
  - 2025-02-09 (@Majo tells me I looked sad when we met and she had the urge to hug me.)
  - . (Blocked @Sophie from appearing on my TikTok. Deleted her number and @Bea's)
people: [Sophie, Bea, Clara, "@Majo"]
events: [Fading-Clara, HRT-crisis, HRT-smuggling, Stormy-Valentine]
notes: |
  Buying the second vial of HRT from the Canadian Pharmacy.
  In expectation of our next meeting, I grieve the ideas of making use of the 120mm camera & the handwritten letters.
---
```

---

## Example 30: 2025-02-15.md

**File**: `journal/content/md/2025/2025-02-15.md`

**Additional fields**: city, dates, epigraph, events, notes, people, poems, tags

```yaml
---
date: 2025-02-15
word_count: 2531
reading_time: 9.7
epigraph: |
  Feliz San Valentín, Cari

  Entre tes yeux d'hiver
  et tes cheveux d'été,
  je trouve le printemps.

  Te quiero, S
city: Montréal
dates:
  - date: "~"
  - date: 2025-02-14
    context: "Valentine with friends."
    people: [María, Lavi]
    locations: [Oui mais non, Station Vendôme, The Glen, Lavi's]
  - date: 2025-02-15
    context: "Breakfast at #Lavi's; then meeting @Majo at #The-Glen."
    people: [Lavi, Clara]
  - date: 2025-02-18
    context: "Planned meeting with @Sarah"
people: ["@María", "@Majo", Lavi, Shubhendra, "@Vero", Alda, "@Ary (Clara)"]
events: [Fading-Clara, Stormy-Valentine]
tags: [IG, IG-story, Friendship, Tarot, Phone-off, Vegetarianism, Raki]
poems:
  # TODO: Check correct term
  - title: Saisons
    content: |
      Entre tes yeux d'hiver
      et tes cheveux d'été,
      je trouve le printemps.
notes: |
  Deep down I wanted to see Clara on Valentine's. 
  Bought valentine's card at Oui mais non. First time I turned off my phone.
  First mention of becoming vegetarian. Spent Valentine with Lavi and Majo. 
  Show Clara's profile to Lavi and Majo. They see a story of her sliding off the snow.
  This lays the groundwork for Majo's impression on Clara's appearance.
  Lavi plays with my Hinge and matches with the Piano instructor I'd meet months later.
---
```

---

## Example 31: 2025-02-16.md

**File**: `journal/content/md/2025/2025-02-16.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2025-02-16
word_count: 951
reading_time: 3.7
epigraph: Yo sería muy feliz viéndote hoy
epigraph_attribution: Aliza
city: Montréal
dates:
  - date: "."
    context: "Cancelled brunch at #Walter's; getting stranded at #The-Glen."
    # TODO: Look up the names of the libraries at C. Desjardins and Place des arts
    locations: [BAnQ, Complexe Desjardins]
    people: [Clara, Aliza, Walter, Majo, Alda]
  - date: 2025-02-17
    context: "Breakfast at #The-Glen. Plans with @Clara."
    people: [Majo]
people: [Clara, Aliza, Walter, "@Majo", Alda]
events: [Fading-Clara, Stormy-Valentine]
tags: [Storm, Raki]
notes: |
  Picked up Barthes book. Irrationally angry with Walter and Aliza.
  Got stranded with Majo at The Glen. She urges me to be assertive with Clara.
  Then jokes that she's used to dating men.
  "You're dating a straight girl! You're just like me!"
---
```

---

## Example 32: 2025-02-23.md

**File**: `journal/content/md/2025/2025-02-23.md`

**Additional fields**: city, dates, epigraph, epigraph_attribution, events, notes, people, tags

```yaml
---
date: 2025-02-23
word_count: 2500
reading_time: 9.6
epigraph: |
  no escribí en mi diario nada de lo que pasó después de san valentín.

  siento como si fuera a olvidarlo—los detalles; no sé si pensar eso hace que me den más o se me quiten las ganas de escribirlo.
epigraph_attribution: Sofía
city: Montréal
dates:
  # TODO: Check for exact dates
  # - date: ???
  #   context: "Think back of my first date at #Darling and my first (implied) rejection."
  #   people: Minas
  # - date: ???
  #   context: "@Clara waited for me at the exact spot where I waited for @Alexia"
  #   locations: Station Mont-Royal
  - date: 2025-02-14
    context: None of the women who @Lavi liked on Hinge matched me.
  - date: 2025-02-17
    context: The anti-date with @Clara
    people: [Louis, Sonny, Majo]
    # TODO: Find the name of the ramen place
    # locations: [Station Mont-Royal, Ramen, Station Laurier, Station Rosemont]
  - date: 2025-02-18
    context: "@Fabiola suggests me to date other people."
  - date: 2025-02-19
    context: "Dinner for @Majo's birthday."
    people: [Majo, Lavi, Jana]
  - date: 2025-02-20
    context: "Dinner with @Alda at #Lola-Rosa. I steal @Clara's receipt-note."
  - date: 2025-02-21
    context: "Night at #Unity."
    locations: Alda's
    people: [Alda, Majo, Seline, Shub, Lavi]
  - date: "."
    context: "Full week of silence since the Anti-date. Sitting at #Café-Pikolo before date with @Hilary at #Darling."
    people: Myriam
people:
  [
    "@Majo",
    Sonny,
    Louis,
    Alexia,
    Clara,
    Lavi,
    "@Shub",
    Seline,
    Alda,
    Hilary,
    Myriam,
    Fabiola,
  ]
events: [Fading-Clara, Stormy-Valentine]
tags: [Storm, Raki, Date, Therapy]
notes: |
  Narration of what happened on the Anti-date.
  The continuous unfortunate events and decisions that let to the catastrophic meeting.
  Sleep-deprivation, anxiety-induced and self-sabotaging binge-drinking.
  Mention of Unity night and the breaking-point of the Lavi-Majo friendship.
  Start of conversation with Myriam with whom nothing ever happens.
---
```

---

## Example 33: 2025-02-28.md

**File**: `journal/content/md/2025/2025-02-28.md`

**Additional fields**: city, dates, epigraph, events, notes, people, references, tags

```yaml
---
date: 2025-02-28
word_count: 1248
reading_time: 4.8
epigraph: &quote |
  Tenoch se disculpó. Su novia lo esperaba para ir al cine. Julio insistió en
  pagar la cuenta.

  Nunca volverán a verse.

  "Nos hablamos, ¿no?"

  "Sí..."
city: Montréal
dates:
  # - ??? (Like with the @Catfisher, I suspect the woman behind these photos was not real.)
  - 2025-02-25 (Indian dinner with @Sarah at Laval. @Myriam proposed to meet mid-March. Redownloaded IG using @Paty as an excuse.)
  - 2025-02-26 (I received the first vial of E2. I watch Y tu mamá también with @Majo. We read the Tarot.)
  - 2025-02-27 (Did not leave the apartment, I ordered two regular A&W burgers despite the initiative to be vegetarian. Then I did not sleep.)
  - . (Sexting with Gaelle. I texted @Clara at 4h54 - hey. i miss you.)
people:
  ["@Catfisher (Emily)", Lavi, Sarah, Myriam, Hilary, "@Paty", "@Majo", Gaelle]
events: [Fading-Clara, HRT-smuggling, Two-white-spaces]
tags: [Fabiola, IG-story, Tarot]
references:
  - content: *quote
    source:
      title: Y tu mamá también
      author: Alfonso Cuarón
      type: film
notes: |
  I redownloaded IG using Paty's salence from Telegram as an excuse.
  I watch Clara's story and wonder if it's about a past, potentially death connection.
  Dance deleting and saving Clara's number again and again. Then, I redownloaded Tinder.
  Afterwards, I sent a text: Hey. i miss you.
---
```

---

## Example 34: 2025-03-02.md

**File**: `journal/content/md/2025/2025-03-02.md`

**Additional fields**: author, city, dates, description, epigraph, locations, notes, people, references, source, tags, title, type

*Note: YAML parsing encountered errors, showing raw content*

```yaml
---
date: 2025-03-02
word_count: 2428
reading_time: 9.3
epigraph: Te amaré en este futuro y el próximo
city: [Montréal, Ciudad de México]
locations:
  # TODO: If there is a _, preserve hyphen and use _ as spacer instead
  # TODO: Name of the book shops
  - Montréal: [Place-d'armes, Complex-Desjardins, Palais-des-Congres, Book-shops, Station_Lionel-Groulx]
  - Ciudad de México: [Coyoacán]
people: ["@Majo", Zahra, Aliza, Clara, Kate, Alda, "@Kath (Katherine)", Hilary]
dates:
  # TODO: Check that mixture of levels is valid in YAML
  - ??? (Memory of watching a story of @Kate on Nuit Blanche years before.)
  - ??? Date with Clara (You cut your hair! - @Zahra notices from the day we met.)
  - ??? Coyoacán (I bought the red anklet with @Alda.)
  - ??? Night of Jan (I give the red anklet to @Clara. She tried to put it on, but coudn't.)
  - date: 2025-03-01
    description: Nuit Blanche with @Majo, @Zahra, and her friends.
    locations: [Place d'armes, Complex Desjardins, Palais des Congres, Book-shops, Station Lionel-Groulx]
  - . (Cancelled plans with @Aliza. Red-anklet on @Clara. Reply to @Kath. Text to @Hilary. @Paty texts before I delete IG again.)
references:
  - description: Song is playing on the television as I write.
    source:
      title: nadie va a pensar en ti mejor que yo
      author: Ed Maverick
      type: song
  - content: |
    Ya no será
    ya no
    no viviremos juntos
    no criaré a tu hijo
    no coseré tu ropa
    no te tendré de noche
    no te besaré al irme
    nunca sabrás quién fui
    por qué me amaron otros.
    
    No llegaré a saber
    por qué ni cómo nunca
    ni si era de verdad
    lo que dijiste que era
    ni quién fuiste
    ni qué fui para ti
    ni cómo hubiera sido
    vivir juntos
    querernos
    esperarnos
    estar.
    
    Ya no soy más que yo
    para siempre y tú
    ya
    no serás para mí
    más que tú. Ya no estás
    en un día futuro
    no sabré dónde vives
    con quién
    ni si te acuerdas.
    No me abrazarás nunca
    como esa noche
    nunca.
    
    No volveré a tocarte.
    
    No te veré morir.
    description: I keep repeating Idea's poem as a mantra.
    source:
      title: Ya no será
      author: Idea Vilariño
      type: poem
tags: [Vegetarian, Nuit-Blanche, Alcohol, IG-story, Red-anklet, Pole-dancing]
notes: |
  I talk about signs of Mania. I embrace the decision of becoming vegetarian.
  "I don't want to go home - at home is where I think and feel"
  I binge drunk. I wanted to puke and feel bad. I felt I deserved to be punished.
  Unflinched by the crack pipe smoker next to me at Lionel-Groulx.
  I see Clara's story from Nuit Blanche where she shot the screen with a Spanish phrase.
  The next day I think seeing the red anklet in her story. I deleted IG again.
---
```

---

## Example 35: 2025-03-04.md

**File**: `journal/content/md/2025/2025-03-04.md`

**Additional fields**: city, dates, epigraph, people, references, tags

```yaml
---
date: 2025-03-04
word_count: 1504
reading_time: 5.8
epigraph: &poem |
  No me abrazarás nunca
  como esa noche
  nunca
city: Montréal
people:
  - "@Majo"
  - Aliza
  - Fabiola
  - Daniel (Daniel Andrews)
  - Louis
  - Vlad
  - Katherine
  - Gaelle
dates:
  - 2025-03-02 (@Aliza took my cancellation gracefully. @Majo suggested coming over that midnight worried about my state.)
  - date: 2025-03-03
    locations: [The Neuro, Eaton Plaza]
    people: [Louis, Vlad]
  - date: .
    people: [Fabiola, Majo, Daniel]
    locations: Thomson House
references:
  - content: *poem
    source:
      title: Ya no será
      author: Idea Vilariño
      type: poem
tags: [Therapy]
---
```

---

## Example 36: 2025-03-05.md

**File**: `journal/content/md/2025/2025-03-05.md`

**Additional fields**: city, dates, epigraph, notes, people, references, tags

```yaml
---
date: 2025-03-05
word_count: 1063
reading_time: 4.1
epigraph: &poem |
  No llegaré a saber
  por qué ni cómo nunca
  ni si era de verdad
  lo que dijiste que era
city: Montréal
people: ["@Majo", Emily]
dates:
  # TODO: Separate this Emily with the Catfisher
  - date: 2025-03-04
    context: "I meet with @Majo and @Emily at Thomson. Dinner with @Majo at #Greenspot. Another sleepless night."
    people: [Majo, Emily]
    locations: [BAnQ, Thomson House, Greenspot, Station Peel]
  - date: .
    context: "I don't sleep. I go from missing @Clara at 1h, to wishing her good-riddance at 5h. I work a full day at #The-Neuro."
references:
  - content: *poem
    source:
      title: Ya no será
      author: Idea Vilariño
      type: poem
tags: [Mania, Testosterone]
notes: |
  I meet/talk more with Emily and realize I don't like her.
  Majo and I remain afte Emily leaves. She suggests I am in a mixed episode.
  They kick us out from Thomson after it closes..
  We have dinner at Greenspot (have we been there before?)
  I read all the IG conversation with Clara. I go from missing her to not caring.
  I go to work after a sleepless night.
---
```

---

## Example 37: 2025-03-06.md

**File**: `journal/content/md/2025/2025-03-06.md`

**Additional fields**: author, city, context, dates, epigraph, locations, notes, people, references, tags, title, type

*Note: YAML parsing encountered errors, showing raw content*

```yaml
---
date: 2025-03-06
word_count: 968
reading_time: 3.7
epigraph: &ref "Savoir qu'on n'écrit pas pour l'autre, savoir que ces choses que je vais écrire ne me feront jamais aimer de qui j'aime, savoir que l'écriture ne compense rien, ne sublime rien, qu'elle est précisément là où tu n'es pas — c'est le commencement de l'écriture."
references:
  - content: *ref
    title: Fragments d'un discours amoureux.
    author: Roland Barthes
    type: book
city: Montréal
dates:
  - 2025-03-05 (Proposed @Majo to buy her concert to Tamino.)
  - date: .
    context: Saw @Aliza to catch up after my cancellation. Posted a close-friends story. @Gaelle blocked me.
    locations: #TODO: What's the name of the Ramen place???
  - date: 2025-03-12 
    context: Made plans with @Miriam for dessert.
people: [Aliza, "@Majo", "@Cris (Cristina)", Sonny, Gaelle, Antonija, Lavi, Miriam]
tags: [Mania, Testosterone, IG-Story]
notes: |
We foolishly believe Sonny's ticket to Montréal is cheap.
Majo offered to pay 100 USD for her ticket.
Galle no longer was on Tinder and she blocked me on Telegram.
---
```

---

## Example 38: 2025-03-08.md

**File**: `journal/content/md/2025/2025-03-08.md`

**Additional fields**: city, dates, epigraph, events, notes, people, references, tags

```yaml
---
date: 2025-03-08
word_count: 2160
reading_time: 8.3
epigraph: &ref |
  Ya dime si quieres estar conmigo o si mejor me voy.
  Tus besos dicen que tú sí me quieres, pero tus palabras no.
  Y, al chile, yo hasta moriría por ti, pero dices que no.
  No eres directa, neta, ya me estás cansando; sé concreta, por favor.
references:
  - content: *ref
    title: Fuentes de Ortiz
    author: Ed Maverick
    type: song
city: Montréal
dates:
  - date: 2025-03-07
    context: "Dinner at #The-Glen, a movie and a text back at my place"
    locations: [BAnQ, Station Jarry, SAQ]
    people: [Majo, Clara]
  - date: .
    context: I texted back.
people: ["@Majo", Reza, Clara, "@Shub", Mahsa, Sylvia, Seline]
events: Two-white-spaces
tags: [IG-Story, CIHR, Tarot, Before-Trilogy]
notes: |
  This is the moment that Majo says gave up on the whole Clara thing.
  I am back to square one, she says I said.
  There is no mention of this in the text, but I believe her.
---
```

---

## Example 39: 2025-03-09.md

**File**: `journal/content/md/2025/2025-03-09.md`

**Additional fields**: city, epigraph, epigraph_attribution, locations, notes, people

```yaml
---
date: 2025-03-09
word_count: 811
reading_time: 3.1
epigraph: |
  creo que no es sorpresa
  es como wtf
  pensé que era más ajustada a la realidad [...]
  pero regresó y me da vibes that she's definitely not okay [...]
  this could get toxic
  espero que me esté equivocando
epigraph_attribution: María José
city: Montréal
locations: [Boulangerie Jarry, BAnQ, The Neuro, Metro]
people: "@Majo"
notes: |
  I picked up the Despentes book that Clara will see at the café in a couple of weeks.
  I fell on the ice coming out of the office.
---
```

---

## Example 40: 2025-03-11.md

**File**: `journal/content/md/2025/2025-03-11.md`

**Additional fields**: dates, epigraph, events, notes, people, references, tags

```yaml
---
date: 2025-03-11
word_count: 1519
reading_time: 5.8
epigraph: &ref |
  Y, ¿de qué sirve hablar? No te quiero ver.
  ¿De qué sirve verte si no te puedo tener aquí?
  Y verte así.
references:
  content: *ref
  source:
    type: song
    title: nadie va a pensar en ti mejor que yo
    author: Ed Maverick
dates:
  - date: ?? Majo & Emily
    context: Told @Fabiola about my meeting, and disliking @Emily, and how @Majo asked me how worried she should have been about my state.
  - date: ?? Date with Anne-Sophie
    context: "Remember having a date with @Anne-Sophie at #Café-Velours"
  - date: 2025-03-10
    context: I tell the lab I feel sick and will skip the meeting; trouble sleeping at night.
    people: [Louis, Daniel]
  - date: .
    people: [Fabiola, Sonny, Yuval, Alda]
    locations: [BAnQ, La Taverne Atlantic, Oui mais non]
people: [Louis, Daniel (Daniel Andrews)]
tags: [Therapy, Depression]
events: Fading-Clara
notes: |
  Let her go, says Sonny.
  What do you want from her?, asked Fabiola
---
```

---

