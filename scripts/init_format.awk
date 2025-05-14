#!/usr/bin/awk -f
#
# init_fmt.awk — remove leading space, mark paragraphs on >2 spaces
# and on sentence-ending + capital-start rules; preserve existing blanks.

BEGIN {
    prev = ""    # remember previous non-blank line
}

{
    line = $0
    # 1) strip leading/trailing whitespace
    sub(/^[ \t]+/, "", line)
    sub(/[ \t]+$/, "", line)

    # 2) skipe metadata header
    # 1a) skip metadata lines entirely
     if ( line ~ /^(Date|Words|Minutes):/ ) {
         print line
         prev = line
         next
     }

    # 3) preserve existing blank lines
    if (line == "") {
        print ""
        prev = ""
        next
    }

    # 4) paragraph break on ≥2 internal spaces
    #if (match(line, /(.*?) {2,}(.*)/, parts)) {
        #if (parts[1] != "")    print parts[1]
        #print ""               # paragraph break
        #if (parts[2] != "")    print parts[2]
        #prev = parts[2]
        #next
    #}

    # 4) paragraph break on ≥2 spaces, handling multiple runs per line
    if (index(line, "  ") > 0) {
        n = split(line, parts, /[ ]{2,}/)
        for (i = 1; i <= n; i++) {
            # print each segment
            if (parts[i] != "") print parts[i]
            # between segments, emit a blank line
            if (i < n)     print ""
        }
        prev = parts[n]
        next
    }

    # 5) paragraph break when previous line ended in . ! ? ` ' "
    #    and this one starts with a capital letter
    if (prev ~ /[\.!\?`'"=]$/ && line ~ /^[A-Z`'"¿¡]/) {
        print ""
    }

    # 6) otherwise, just print the line
    print line
    prev = line
}
