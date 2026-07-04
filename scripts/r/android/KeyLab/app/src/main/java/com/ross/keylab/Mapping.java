package com.ross.keylab;

import java.util.HashMap;
import java.util.Map;

/**
 * Long-press mapping, hardcoded for now. Format: "base:symbol" pairs, comma-separated.
 * The base is matched case-insensitively against the character a key produces
 * with no modifiers. ':' separates base from symbol so '=' can be a base.
 */
public final class Mapping {

    static final long LONGPRESS_MS = 250;

    private static final String SPEC =
            "1:!,2:@,3:#,4:$,5:%,6:^,7:&,8:*,9:(,0:)," +
            "e:€,c:¢,y:¥,-:_,q:\\,w:|,r:®,t:™";

    private Mapping() {}

    /** Parses the hardcoded spec into a lowercase-base -> symbol map. Bad pairs are skipped. */
    static Map<Character, String> parse() {
        Map<Character, String> map = new HashMap<>();
        for (String pair : SPEC.split(",")) {
            int sep = pair.indexOf(':');
            if (sep <= 0 || sep >= pair.length() - 1) continue;
            char base = Character.toLowerCase(pair.charAt(0));
            String symbol = pair.substring(sep + 1);
            map.put(base, symbol);
        }
        return map;
    }
}
