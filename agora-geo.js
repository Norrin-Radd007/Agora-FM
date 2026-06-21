/**
 * AGORA FM — UK Region Lookup (agora-geo.js)
 * Maps a UK postcode area / town / freeform address string to one of
 * 11 standard UK regions, using postcode-area prefixes. No external
 * API or key required.
 *
 * Usage:
 *   AgoraGeo.REGIONS                 -> ['Scotland', 'North East', ...]
 *   AgoraGeo.lookupRegion('G1 1AA')  -> 'Scotland'
 *   AgoraGeo.lookupRegion('12 Barbican Centre, London EC2Y 8NB') -> 'London'
 *   AgoraGeo.lookupRegion('Glasgow') -> 'Scotland'   (town-name fallback)
 */
var AgoraGeo = (function () {

  // ── Canonical region list (order = display order in UI) ──────────────────
  var REGIONS = [
    'Scotland',
    'Northern Ireland',
    'Wales',
    'North East',
    'North West',
    'Yorkshire & Humber',
    'East Midlands',
    'West Midlands',
    'East of England',
    'London',
    'South East',
    'South West'
  ];

  // ── Postcode AREA (the letters before the first digit) -> region ─────────
  // Covers all current UK postcode areas. Source: Royal Mail postcode area list.
  var POSTCODE_AREA_MAP = {
    // Scotland
    AB:'Scotland', DD:'Scotland', DG:'Scotland', EH:'Scotland', FK:'Scotland',
    G:'Scotland', HS:'Scotland', IV:'Scotland', KA:'Scotland', KW:'Scotland',
    KY:'Scotland', ML:'Scotland', PA:'Scotland', PH:'Scotland', TD:'Scotland',
    ZE:'Scotland',
    // Northern Ireland
    BT:'Northern Ireland',
    // Wales
    CF:'Wales', LD:'Wales', LL:'Wales', NP:'Wales', SA:'Wales', SY:'Wales',
    // North East England
    DH:'North East', DL:'North East', NE:'North East', SR:'North East', TS:'North East',
    // North West England
    BB:'North West', BL:'North West', CA:'North West', CH:'North West', CW:'North West',
    FY:'North West', L:'North West', LA:'North West', M:'North West', OL:'North West',
    PR:'North West', SK:'North West', WA:'North West', WN:'North West',
    // Yorkshire & The Humber
    BD:'Yorkshire & Humber', DN:'Yorkshire & Humber', HD:'Yorkshire & Humber',
    HG:'Yorkshire & Humber', HU:'Yorkshire & Humber', HX:'Yorkshire & Humber',
    LS:'Yorkshire & Humber', S:'Yorkshire & Humber', WF:'Yorkshire & Humber',
    YO:'Yorkshire & Humber',
    // East Midlands
    DE:'East Midlands', LE:'East Midlands', LN:'East Midlands', NG:'East Midlands',
    NN:'East Midlands',
    // West Midlands
    B:'West Midlands', CV:'West Midlands', DY:'West Midlands', HR:'West Midlands',
    ST:'West Midlands', TF:'West Midlands', WR:'West Midlands', WS:'West Midlands',
    WV:'West Midlands',
    // East of England
    AL:'East of England', CB:'East of England', CM:'East of England',
    CO:'East of England', IP:'East of England', LU:'East of England',
    NR:'East of England', PE:'East of England', SG:'East of England',
    SS:'East of England',
    // London
    E:'London', EC:'London', N:'London', NW:'London', SE:'London',
    SW:'London', W:'London', WC:'London', BR:'London', CR:'London',
    DA:'London', EN:'London', HA:'London', IG:'London', KT:'London',
    RM:'London', SM:'London', TW:'London', UB:'London', WD:'London',
    // South East England
    BN:'South East', GU:'South East', ME:'South East', MK:'South East',
    OX:'South East', PO:'South East', RG:'South East', RH:'South East',
    SL:'South East', SO:'South East', TN:'South East',
    // South West England
    BA:'South West', BH:'South West', BS:'South West', DT:'South West',
    EX:'South West', GL:'South West', PL:'South West', SN:'South West',
    SP:'South West', TA:'South West', TQ:'South West', TR:'South West'
  };

  // ── Town/city name fallback (used when no postcode is recognised) ────────
  var TOWN_MAP = {
    'glasgow':'Scotland','edinburgh':'Scotland','aberdeen':'Scotland','dundee':'Scotland',
    'inverness':'Scotland','stirling':'Scotland','perth':'Scotland','paisley':'Scotland',
    'belfast':'Northern Ireland','derry':'Northern Ireland','londonderry':'Northern Ireland',
    'cardiff':'Wales','swansea':'Wales','newport':'Wales','wrexham':'Wales','bangor':'Wales',
    'newcastle':'North East','sunderland':'North East','durham':'North East',
    'middlesbrough':'North East','gateshead':'North East','darlington':'North East',
    'manchester':'North West','liverpool':'North West','preston':'North West',
    'blackpool':'North West','bolton':'North West','carlisle':'North West',
    'chester':'North West','warrington':'North West','lancaster':'North West',
    'stockport':'North West','wigan':'North West',
    'leeds':'Yorkshire & Humber','sheffield':'Yorkshire & Humber','bradford':'Yorkshire & Humber',
    'hull':'Yorkshire & Humber','york':'Yorkshire & Humber','wakefield':'Yorkshire & Humber',
    'huddersfield':'Yorkshire & Humber','doncaster':'Yorkshire & Humber',
    'nottingham':'East Midlands','leicester':'East Midlands','derby':'East Midlands',
    'lincoln':'East Midlands','northampton':'East Midlands',
    'birmingham':'West Midlands','coventry':'West Midlands','wolverhampton':'West Midlands',
    'stoke':'West Midlands','worcester':'West Midlands','hereford':'West Midlands',
    'cambridge':'East of England','norwich':'East of England','ipswich':'East of England',
    'colchester':'East of England','chelmsford':'East of England','luton':'East of England',
    'peterborough':'East of England','southend':'East of England',
    'london':'London','croydon':'London','romford':'London','harrow':'London',
    'kingston':'London','bromley':'London',
    'brighton':'South East','reading':'South East','oxford':'South East',
    'southampton':'South East','portsmouth':'South East','milton keynes':'South East',
    'guildford':'South East','maidstone':'South East','slough':'South East',
    'crawley':'South East','tonbridge':'South East','windsor':'South East',
    'bristol':'South West','plymouth':'South West','exeter':'South West',
    'bournemouth':'South West','bath':'South West','gloucester':'South West',
    'swindon':'South West','taunton':'South West','truro':'South West'
  };

  /**
   * Extract the postcode "area" (leading letters) from a raw UK postcode.
   * Handles full postcodes (e.g. "EC2Y 8NB"), outward codes ("EC2Y"),
   * and postcodes embedded in a longer address string.
   */
  function extractPostcodeArea(text) {
    if (!text) return null;
    // UK postcode regex: 1-2 letters, 1-2 digits (+optional letter), space, digit, 2 letters
    var re = /\b([A-Z]{1,2})[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}\b/i;
    var m = text.match(re);
    if (m) return m[1].toUpperCase();
    // Outward-code-only match (no space, no inward part) e.g. "SW1A" typed alone
    var re2 = /\b([A-Z]{1,2})[0-9][0-9A-Z]?\b/i;
    var m2 = text.trim().match(re2);
    if (m2 && text.trim().length <= 5) return m2[1].toUpperCase();
    return null;
  }

  function lookupByTown(text) {
    var t = (text || '').toLowerCase();
    var towns = Object.keys(TOWN_MAP);
    for (var i = 0; i < towns.length; i++) {
      if (t.indexOf(towns[i]) !== -1) return TOWN_MAP[towns[i]];
    }
    return null;
  }

  /**
   * Resolve a region from a postcode, town name, or freeform address string.
   * Returns one of REGIONS, or null if nothing could be resolved.
   */
  function lookupRegion(input) {
    if (!input) return null;
    var area = extractPostcodeArea(input);
    if (area && POSTCODE_AREA_MAP[area]) return POSTCODE_AREA_MAP[area];
    return lookupByTown(input);
  }

  return {
    REGIONS: REGIONS,
    lookupRegion: lookupRegion,
    extractPostcodeArea: extractPostcodeArea
  };
})();
window.AgoraGeo = AgoraGeo;
