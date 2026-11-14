import re
from typing import Optional

from src.query.query import Condition, Field, Operator, Query
from src.base.config import Config


class LocalConditionExtractor:
    """
    Phase 1: Fast, zero-cost local rule/regex extractor for obvious hard facts.
    Adapts its aggressiveness based on whether Phase 2 (API) is available.
    """

    _MULTIPLIERS: dict[str, int] = {
        "k": 1_000,
        "thousand": 1_000,
        "m": 1_000_000,
        "mil": 1_000_000,
        "million": 1_000_000,
        "millions": 1_000_000,
        "b": 1_000_000_000,
        "bil": 1_000_000_000,
        "billion": 1_000_000_000,
        "billions": 1_000_000_000,
    }

    # --- DICTIONARE GLOBALE EXTINSE (200+ SCENARII) ---
    _GEO_EXPANSIONS: dict[str, list[str]] = {
        # Regiuni Globale & Europene
        "scandinavia": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "scandinavian": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "nordics": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "nordic": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "dach region": ["Germany", "Austria", "Switzerland", "Berlin", "Munich", "Vienna", "Zurich"],
        "dach": ["Germany", "Austria", "Switzerland", "Berlin", "Munich", "Vienna", "Zurich"],
        "benelux": ["Belgium", "Netherlands", "Luxembourg", "Brussels", "Amsterdam"],
        "baltics": ["Estonia", "Latvia", "Lithuania", "Tallinn", "Riga", "Vilnius"],
        "baltic": ["Estonia", "Latvia", "Lithuania", "Tallinn", "Riga", "Vilnius"],
        "balkans": ["Romania", "Bulgaria", "Greece", "Serbia", "Croatia", "Slovenia", "Albania"],
        "balkan": ["Romania", "Bulgaria", "Greece", "Serbia", "Croatia", "Slovenia", "Albania"],
        "central and eastern europe": ["Romania", "Poland", "Czechia", "Czech Republic", "Hungary", "Bulgaria", "Slovakia", "Croatia", "Slovenia"],
        "cee": ["Romania", "Poland", "Czechia", "Czech Republic", "Hungary", "Bulgaria", "Slovakia"],
        "eastern europe": ["Romania", "Poland", "Czechia", "Hungary", "Bulgaria", "Slovakia", "Ukraine"],
        "western europe": ["Germany", "France", "United Kingdom", "UK", "Netherlands", "Belgium", "Switzerland", "Austria"],
        "iberian peninsula": ["Spain", "Portugal", "Madrid", "Barcelona", "Lisbon"],
        "iberia": ["Spain", "Portugal", "Madrid", "Barcelona", "Lisbon"],
        "europe": ["Germany", "France", "United Kingdom", "Romania", "Poland", "Spain", "Italy", "Netherlands", "Sweden", "Switzerland", "Austria", "Belgium"],
        "european": ["Germany", "France", "United Kingdom", "Romania", "Poland", "Spain", "Italy", "Netherlands", "Sweden", "Switzerland"],
        "emea": ["United Kingdom", "Germany", "France", "UAE", "Saudi Arabia", "South Africa", "Netherlands", "Spain", "Italy"],
        "mena region": ["UAE", "United Arab Emirates", "Dubai", "Saudi Arabia", "Egypt", "Qatar", "Israel", "Morocco"],
        "mena": ["UAE", "United Arab Emirates", "Dubai", "Saudi Arabia", "Egypt", "Qatar", "Israel"],
        "gcc": ["UAE", "United Arab Emirates", "Saudi Arabia", "Qatar", "Kuwait", "Bahrain", "Oman"],
        "sub-saharan africa": ["South Africa", "Nigeria", "Kenya", "Ghana", "Johannesburg", "Nairobi"],
        "asean region": ["Singapore", "Vietnam", "Thailand", "Indonesia", "Malaysia", "Philippines"],
        "asean": ["Singapore", "Vietnam", "Thailand", "Indonesia", "Malaysia", "Philippines"],
        "asia": ["Singapore", "Japan", "South Korea", "China", "India", "Taiwan", "Vietnam", "Hong Kong"],
        "apac": ["Singapore", "Japan", "South Korea", "Australia", "New Zealand", "India", "China", "Taiwan"],
        "latin america": ["Brazil", "Mexico", "Argentina", "Colombia", "Chile", "Peru"],
        "latam": ["Brazil", "Mexico", "Argentina", "Colombia", "Chile", "Peru"],
        "north america": ["United States", "USA", "US", "Canada", "Mexico"],
        # Tari & Gentilice
        "romania": ["Romania", "Bucharest", "Cluj", "Timisoara", "Iasi", "Brasov"],
        "romanian": ["Romania", "Bucharest", "Cluj", "Timisoara", "Iasi", "Brasov"],
        "the united states": ["United States", "USA", "US", "New York", "California", "Texas"],
        "united states": ["United States", "USA", "US", "New York", "California", "Texas"],
        "the us": ["United States", "USA", "US", "New York", "California", "Texas"],
        "usa": ["United States", "USA", "US", "New York", "California", "Texas"],
        "u.s.": ["United States", "USA", "US"],
        "the uk": ["United Kingdom", "UK", "London", "England"],
        "united kingdom": ["United Kingdom", "UK", "London", "England"],
        "uk": ["United Kingdom", "UK", "London", "England"],
        "canada": ["Canada", "Toronto", "Vancouver", "Montreal"],
        "canadian": ["Canada", "Toronto", "Vancouver", "Montreal"],
        "germany": ["Germany", "Berlin", "Munich", "Frankfurt", "Hamburg"],
        "german": ["Germany", "Berlin", "Munich", "Frankfurt", "Hamburg"],
        "austria": ["Austria", "Vienna"],
        "austrian": ["Austria", "Vienna"],
        "switzerland": ["Switzerland", "Zurich", "Geneva", "Basel", "Bern"],
        "swiss": ["Switzerland", "Zurich", "Geneva", "Basel", "Bern"],
        "france": ["France", "Paris", "Lyon"],
        "french": ["France", "Paris", "Lyon"],
        "spain": ["Spain", "Madrid", "Barcelona"],
        "spanish": ["Spain", "Madrid", "Barcelona"],
        "portugal": ["Portugal", "Lisbon", "Porto"],
        "italy": ["Italy", "Milan", "Rome", "Turin"],
        "italian": ["Italy", "Milan", "Rome", "Turin"],
        "poland": ["Poland", "Warsaw", "Krakow", "Wroclaw"],
        "polish": ["Poland", "Warsaw", "Krakow"],
        "netherlands": ["Netherlands", "Amsterdam", "Rotterdam"],
        "dutch": ["Netherlands", "Amsterdam", "Rotterdam"],
        "belgium": ["Belgium", "Brussels", "Antwerp"],
        "belgian": ["Belgium", "Brussels", "Antwerp"],
        "sweden": ["Sweden", "Stockholm", "Gothenburg"],
        "swedish": ["Sweden", "Stockholm"],
        "norway": ["Norway", "Oslo"],
        "denmark": ["Denmark", "Copenhagen"],
        "finland": ["Finland", "Helsinki"],
        "ireland": ["Ireland", "Dublin"],
        "greece": ["Greece", "Athens", "Thessaloniki"],
        "cyprus": ["Cyprus", "Nicosia", "Limassol"],
        "czech republic": ["Czech Republic", "Czechia", "Prague"],
        "czechia": ["Czech Republic", "Czechia", "Prague"],
        "slovakia": ["Slovakia", "Bratislava"],
        "hungary": ["Hungary", "Budapest"],
        "bulgaria": ["Bulgaria", "Sofia"],
        "croatia": ["Croatia", "Zagreb"],
        "slovenia": ["Slovenia", "Ljubljana"],
        "serbia": ["Serbia", "Belgrade"],
        "ukraine": ["Ukraine", "Kyiv", "Lviv"],
        "turkey": ["Turkey", "Istanbul", "Ankara"],
        "israel": ["Israel", "Tel Aviv", "Jerusalem"],
        "uae": ["United Arab Emirates", "UAE", "Dubai", "Abu Dhabi"],
        "united arab emirates": ["United Arab Emirates", "UAE", "Dubai", "Abu Dhabi"],
        "saudi arabia": ["Saudi Arabia", "Riyadh", "Jeddah"],
        "south africa": ["South Africa", "Johannesburg", "Cape Town"],
        "india": ["India", "Bangalore", "Mumbai", "Delhi", "Hyderabad"],
        "china": ["China", "Shanghai", "Beijing", "Shenzhen"],
        "japan": ["Japan", "Tokyo", "Osaka"],
        "south korea": ["South Korea", "Korea", "Seoul"],
        "korea": ["South Korea", "Korea", "Seoul"],
        "taiwan": ["Taiwan", "Taipei", "Hsinchu"],
        "singapore": ["Singapore"],
        "hong kong": ["Hong Kong"],
        "vietnam": ["Vietnam", "Ho Chi Minh City", "Hanoi"],
        "australia": ["Australia", "Sydney", "Melbourne"],
        "new zealand": ["New Zealand", "Auckland", "Wellington"],
        "brazil": ["Brazil", "Sao Paulo", "Rio de Janeiro"],
        "mexico": ["Mexico", "Mexico City", "Monterrey"],
        "argentina": ["Argentina", "Buenos Aires"],
        "chile": ["Chile", "Santiago"],
        "colombia": ["Colombia", "Bogota", "Medellin"],
        # Orase importante mentionate individual
        "bucharest": ["Bucharest", "Romania"],
        "cluj": ["Cluj", "Cluj-Napoca", "Romania"],
        "brasov": ["Brasov", "Romania"],
        "timisoara": ["Timisoara", "Romania"],
        "iasi": ["Iasi", "Romania"],
        "london": ["London", "United Kingdom", "UK"],
        "zurich": ["Zurich", "Switzerland"],
        "geneva": ["Geneva", "Switzerland"],
        "paris": ["Paris", "France"],
        "berlin": ["Berlin", "Germany"],
        "munich": ["Munich", "Germany"],
        "vienna": ["Vienna", "Austria"],
        "amsterdam": ["Amsterdam", "Netherlands"],
        "dublin": ["Dublin", "Ireland"],
        "madrid": ["Madrid", "Spain"],
        "barcelona": ["Barcelona", "Spain"],
        "milan": ["Milan", "Italy"],
        "warsaw": ["Warsaw", "Poland"],
        "prague": ["Prague", "Czechia", "Czech Republic"],
        "budapest": ["Budapest", "Hungary"],
        "dubai": ["Dubai", "United Arab Emirates", "UAE"],
    }

    _BUSINESS_MODELS: dict[str, list[str]] = {
        "b2b": ["B2B", "business-to-business", "enterprise"],
        "b2c": ["B2C", "direct-to-consumer", "DTC", "consumer"],
        "b2g": ["B2G", "business-to-government", "government contractor", "public sector"],
        "direct-to-consumer": ["direct-to-consumer", "DTC", "B2C", "consumer"],
        "dtc": ["direct-to-consumer", "DTC", "B2C"],
        "saas": ["SaaS", "software as a service", "cloud", "subscription"],
        "subscription box": ["subscription", "subscription box", "DTC", "B2C", "recurring"],
        "recurring revenue": ["subscription", "SaaS", "recurring revenue"],
        "subscription": ["subscription", "SaaS", "recurring"],
        "two-sided marketplace": ["marketplace", "two-sided marketplace", "platform", "peer-to-peer"],
        "marketplace": ["marketplace", "platform"],
        "marketplaces": ["marketplace", "platform"],
        "peer-to-peer": ["peer-to-peer", "P2P", "marketplace", "sharing platform"],
        "franchise": ["franchise", "chain", "franchising"],
        "dropshipping": ["dropshipping", "print-on-demand", "e-commerce", "online fulfillment"],
        "print-on-demand": ["print-on-demand", "dropshipping", "custom printing"],
        "white-label": ["white-label", "private label", "contract manufacturing", "B2B"],
        "private label": ["private label", "white-label", "contract manufacturing", "B2B"],
        "contract manufacturers": ["contract manufacturing", "CMO", "CDMO", "B2B", "manufacturer"],
        "open-source": ["open-source", "open source", "developer tools"],
        "wholesale": ["wholesale", "distributor", "distribution", "B2B", "supplier"],
        "distributors": ["distributor", "distribution", "wholesale", "supplier", "B2B"],
        "exporters": ["exporter", "export", "international trade", "B2B", "supplier"],
        "resellers": ["reseller", "value-added reseller", "VAR", "channel partner", "B2B"],
        "bpo": ["BPO", "business process outsourcing", "outsourcing", "IT services", "B2B"],
        "outsourcing": ["outsourcing", "staff augmentation", "IT services", "consulting", "B2B"],
        "staff augmentation": ["staff augmentation", "outsourcing", "IT staffing", "B2B"],
        "consulting": ["consulting", "consultancy", "advisory", "professional services", "agency", "B2B"],
        "consultancies": ["consulting", "consultancy", "advisory", "professional services", "B2B"],
        "advisories": ["advisory", "consulting", "wealth management", "professional services"],
        "agencies": ["agency", "consulting", "services", "B2B"],
        "agency": ["agency", "consulting", "services", "B2B"],
        "brokers": ["broker", "brokerage", "intermediary", "agency"],
        "contractors": ["contractor", "service provider", "B2B"],
        "vendors": ["vendor", "supplier", "provider", "B2B"],
        "suppliers": ["B2B", "supplier", "manufacturer", "distributor", "wholesale"],
        "supplier": ["B2B", "supplier", "manufacturer", "distributor"],
        "supplying": ["B2B", "supplier", "distributor"],
        "supply": ["B2B", "supplier", "manufacturer", "distributor", "wholesale"],
        "producers": ["producer", "manufacturer", "manufacturing", "production", "B2B"],
        "manufacturers": ["B2B", "manufacturer", "manufacturing", "production"],
        "manufacturer": ["B2B", "manufacturer", "manufacturing", "production", "supplier"],
        "manufacturing": ["manufacturer", "manufacturing", "production"],
        "manufacture": ["B2B", "manufacturer", "manufacturing", "production", "supplier"],
    }

    _OFFERINGS_KEYWORDS: dict[str, list[str]] = {
        # Deep Tech, AI, Software & Telecom
        "software": ["software", "SaaS", "platform", "application", "cloud", "IT"],
        "it": ["IT services", "information technology", "software development", "tech support"],
        "tech": ["technology", "software", "IT", "SaaS", "digital solutions"],
        "digital transformation": ["digital transformation", "IT consulting", "cloud migration", "software modernization"],
        "ai": ["artificial intelligence", "AI", "machine learning", "ML", "deep learning", "data science"],
        "artificial intelligence": ["artificial intelligence", "AI", "machine learning", "ML"],
        "quantum computing": ["quantum computing", "quantum hardware", "quantum algorithms", "deep tech"],
        "photonics": ["photonics", "optics", "lasers", "optical components"],
        "nanotechnology": ["nanotechnology", "nanomaterials", "advanced materials", "materials science"],
        "advanced materials": ["advanced materials", "nanomaterials", "composite materials", "specialty materials"],
        "spacetech": ["SpaceTech", "aerospace", "satellites", "nanosatellites", "launch vehicles", "space technology"],
        "nanosatellites": ["nanosatellites", "small satellites", "CubeSats", "SpaceTech"],
        "launch vehicles": ["launch vehicles", "rockets", "orbital launch", "space propulsion"],
        "cybersecurity": ["cybersecurity", "security", "information security", "network security", "infosec"],
        "cloud security": ["cloud security", "cybersecurity", "information security", "cloud"],
        "private cloud": ["private cloud", "cloud infrastructure", "hybrid cloud", "enterprise cloud", "IaaS"],
        "cloud infrastructure": ["cloud infrastructure", "cloud computing", "hosting", "IaaS", "servers"],
        "cloud computing": ["cloud computing", "cloud infrastructure", "SaaS", "PaaS", "IaaS"],
        "colocation": ["data center colocation", "bare-metal servers", "data center", "server hosting"],
        "hosting": ["web hosting", "cloud hosting", "data center", "servers"],
        "data warehousing": ["data warehousing", "data warehouse", "big data", "cloud data", "analytics"],
        "data analytics": ["data analytics", "business intelligence", "BI", "big data", "data science"],
        "business intelligence": ["business intelligence", "BI", "data analytics", "reporting"],
        "erp": ["ERP", "enterprise resource planning", "business management software"],
        "crm": ["CRM", "customer relationship management", "sales software"],
        "cad": ["CAD", "CAM", "computer-aided design", "3D modeling software", "engineering software"],
        "gis": ["GIS", "geospatial mapping", "satellite imagery", "spatial analytics", "location intelligence"],
        "geospatial": ["geospatial mapping", "GIS", "satellite imagery", "earth observation"],
        "voip": ["VoIP", "unified communications", "UCaaS", "contact center software", "telephony"],
        "unified communications": ["unified communications", "VoIP", "contact center", "video conferencing"],
        "contact center": ["contact center software", "call center", "customer support platform", "VoIP"],
        "kyc": ["KYC", "know your customer", "identity verification", "AML", "compliance", "fraud prevention"],
        "identity verification": ["identity verification", "KYC", "authentication", "biometrics"],
        "pos": ["POS", "point of sale", "payment terminals", "retail hardware"],
        "payment gateway": ["payment gateway", "payment processing", "fintech", "merchant services"],
        "digital payments": ["digital payments", "payment processing", "fintech", "mobile payments"],
        "fleet management": ["fleet management", "telematics", "GPS tracking", "logistics software"],
        "iot": ["IoT", "Internet of Things", "embedded systems", "connected devices", "smart sensors"],
        "embedded systems": ["embedded systems", "firmware", "IoT", "microcontrollers", "hardware"],
        "blockchain": ["blockchain", "Web3", "cryptocurrency", "decentralized", "digital assets"],
        "cryptocurrency": ["cryptocurrency", "crypto exchange", "blockchain", "digital assets"],
        "video game": ["video games", "game development", "gaming studio", "interactive entertainment"],
        "e-sports": ["esports", "e-sports", "competitive gaming", "gaming platform", "gaming tournaments"],
        "esports": ["esports", "e-sports", "competitive gaming", "gaming platform"],
        "gaming": ["gaming", "video games", "game platform", "interactive entertainment"],
        "audio streaming": ["audio streaming", "music streaming", "podcasting", "digital audio"],
        "podcasting": ["podcasting", "audio streaming", "media platform", "digital audio"],
        "music licensing": ["music licensing", "audio rights", "music publishing", "streaming"],
        "3d printing": ["3D printing", "additive manufacturing", "rapid prototyping"],
        "additive manufacturing": ["additive manufacturing", "3D printing", "industrial 3D"],
        "semiconductor": ["semiconductors", "microchips", "integrated circuits", "wafers", "foundry"],
        "microchips": ["microchips", "semiconductors", "integrated circuits", "chip manufacturing"],
        "consumer electronics": ["consumer electronics", "electronic devices", "smart devices", "appliances"],
        "electronics": ["electronics", "electronic components", "hardware", "devices"],
        "hardware": ["hardware", "electronics", "devices", "computer hardware", "equipment"],
        "telecommunications": ["telecommunications", "telecom", "network operator", "connectivity", "5G"],
        # Verticals (-Tech) & Business Services
        "fintech": ["fintech", "financial technology", "payments", "digital banking", "finance"],
        "fintechs": ["fintech", "financial technology", "payments", "digital banking"],
        "regtech": ["RegTech", "regulatory technology", "compliance automation", "risk and compliance software"],
        "compliance automation": ["compliance automation", "RegTech", "regulatory compliance software", "GRC"],
        "martech": ["MarTech", "marketing technology", "marketing automation", "digital marketing platform"],
        "adtech": ["AdTech", "advertising technology", "programmatic advertising", "ad network"],
        "programmatic advertising": ["programmatic advertising", "AdTech", "digital advertising", "DSP"],
        "govtech": ["GovTech", "government technology", "public sector software", "municipal digitization"],
        "edtech": ["EdTech", "education technology", "e-learning", "online learning platform"],
        "online learning": ["e-learning", "online learning", "EdTech", "training platform"],
        "medtech": ["MedTech", "medical devices", "diagnostic equipment", "healthcare technology"],
        "medical devices": ["medical devices", "diagnostic devices", "MedTech", "medical equipment"],
        "proptech": ["PropTech", "real estate software", "property management"],
        "real estate management": ["property management software", "real estate software", "PropTech"],
        "insurtech": ["InsurTech", "insurance technology", "claims automation", "insurance software"],
        "claims processing": ["claims processing", "insurance claims", "InsurTech"],
        "legaltech": ["LegalTech", "legal software", "contract management", "law practice management"],
        "agritech": ["AgriTech", "agriculture technology", "smart farming", "precision agriculture"],
        "smart farming": ["smart farming", "precision agriculture", "AgriTech", "irrigation sensors"],
        "cleantech": ["CleanTech", "clean energy", "environmental technology", "sustainability", "green tech"],
        "biotech": ["biotechnology", "biotech", "life sciences", "pharma", "therapeutics"],
        "pharmaceutical": ["pharmaceutical", "biotech", "drug manufacturing", "life sciences", "pharma"],
        "laboratory equipment": ["laboratory equipment", "scientific instruments", "lab supplies"],
        "hr": ["HR solutions", "human resources software", "HRIS", "payroll", "recruitment"],
        "recruitment": ["recruitment", "executive search", "headhunting", "talent acquisition", "staffing"],
        "headhunting": ["headhunting", "executive search", "recruitment agency", "talent acquisition"],
        "executive search": ["executive search", "headhunting", "leadership recruitment", "staffing"],
        "accounting": ["accounting", "bookkeeping", "tax preparation", "audit", "financial advisory"],
        "tax preparation": ["tax preparation", "tax advisory", "accounting", "bookkeeping"],
        "bookkeeping": ["bookkeeping", "accounting services", "payroll", "tax"],
        "translation": ["translation", "localization", "interpreting", "language services"],
        "localization": ["localization", "translation services", "multilingual content"],
        "public relations": ["public relations", "PR agency", "corporate communications", "media relations"],
        "corporate communications": ["corporate communications", "public relations", "PR", "strategic communications"],
        "market research": ["market research", "public opinion polling", "consumer insights", "data polling"],
        "digital marketing": ["digital marketing", "SEO", "advertising agency", "performance marketing"],
        "seo": ["SEO", "search engine optimization", "digital marketing", "content marketing"],
        "design": ["design agency", "UI/UX design", "branding", "creative studio", "graphic design"],
        "event management": ["event management", "ticketing platform", "event software"],
        "ticketing": ["ticketing", "event ticketing", "booking platform", "transit ticketing"],
        "public safety": ["public safety software", "emergency response systems", "dispatch software"],
        "emergency response": ["emergency response", "public safety", "incident management"],
        "security guard": ["security guard services", "facility patrol", "physical security", "manned guarding"],
        "public health": ["public health consulting", "epidemiology", "health policy", "clinical research"],
        "epidemiology": ["epidemiology", "public health research", "infectious disease analysis"],
        # Finance, Banking & Investment
        "banks": ["banking", "financial services", "commercial banking", "retail banking", "loans"],
        "private banking": ["private banking", "wealth management", "asset management", "investment advisory"],
        "wealth management": ["wealth management", "asset management", "financial planning", "private banking"],
        "private equity": ["private equity", "venture capital", "investment management", "buyouts"],
        "venture capital": ["venture capital", "VC", "startup investing", "private equity"],
        "financial services": ["financial services", "banking", "wealth management", "finance", "lending"],
        "insurance": ["insurance", "underwriting", "risk management", "insurer", "insurance brokerage"],
        # Classic Industries, Manufacturing, Energy, Food & Medical
        "packaging": ["packaging", "packaging materials", "containers", "bottles", "jars", "boxes", "tubes"],
        "packaging automation": ["packaging machinery", "packaging automation", "industrial packaging"],
        "corrugated cardboard": ["corrugated cardboard", "cardboard packaging", "paperboard", "boxes"],
        "commercial printing": ["commercial printing", "print services", "packaging printing", "offset printing"],
        "logistic": ["logistics", "supply chain", "freight", "shipping", "warehousing", "transportation"],
        "logistics": ["logistics", "supply chain", "freight", "shipping", "warehousing", "transportation"],
        "cold chain": ["cold chain logistics", "temperature-controlled logistics", "refrigerated transport"],
        "marine shipping": ["marine shipping", "maritime transport", "ocean freight", "shipping lines"],
        "maritime": ["maritime", "shipbuilding", "marine engineering", "shipping"],
        "shipbuilding": ["shipbuilding", "shipyard", "marine vessels", "naval architecture"],
        "construction": ["construction", "general contractor", "building construction", "infrastructure"],
        "building materials": ["building materials", "construction materials", "glass", "ceramics", "cement"],
        "glass": ["glass manufacturing", "flat glass", "glass containers", "industrial glass"],
        "ceramic": ["ceramics", "ceramic tiles", "sanitaryware", "building materials"],
        "plastics": ["plastics manufacturing", "polymers", "injection molding", "industrial plastics"],
        "polymers": ["polymers", "plastics", "synthetic resins", "elastomers"],
        "rubber": ["rubber products", "elastomers", "industrial rubber", "tires"],
        "tire": ["tires", "automotive rubber", "tire manufacturing", "rubber components"],
        "hvac": ["HVAC", "heating, ventilation, and air conditioning", "industrial cooling", "refrigeration"],
        "industrial cooling": ["industrial cooling", "HVAC", "chillers", "refrigeration systems"],
        "elevator": ["elevators", "escalators", "lift maintenance", "vertical transportation"],
        "escalator": ["escalators", "elevators", "moving walkways"],
        "railway": ["railway equipment", "rolling stock", "rail signaling", "locomotives"],
        "rolling stock": ["rolling stock", "railway vehicles", "trains", "railcars"],
        "uav": ["UAV", "unmanned aerial vehicles", "commercial drones", "aerial robotics"],
        "drone": ["drones", "UAV", "unmanned aerial systems", "aerial imaging"],
        "avionics": ["avionics", "aircraft electronics", "flight systems", "aerospace hardware"],
        "satellite communications": ["satellite communications", "satcom", "telecommunications", "aerospace"],
        "private jet": ["private jet charter", "business aviation", "aircraft charter", "aviation"],
        "business aviation": ["business aviation", "aircraft charter", "private aviation", "flight services"],
        "office furniture": ["office furniture", "commercial furniture", "interior fit-out", "workplace design"],
        "furniture": ["furniture manufacturing", "interior furnishings", "commercial furniture"],
        "oil and gas": ["oil and gas", "petroleum equipment", "oilfield services", "energy infrastructure"],
        "clean energy": ["clean energy", "renewable energy", "sustainability", "green tech"],
        "renewable energy": ["renewable energy", "wind turbines", "solar panels", "energy storage"],
        "hydrogen": ["green hydrogen", "hydrogen production", "fuel cells", "clean energy"],
        "biofuel": ["biofuels", "renewable fuels", "biomass energy", "biodiesel"],
        "water treatment": ["water treatment", "wastewater management", "desalination", "water purification"],
        "desalination": ["desalination", "water treatment", "reverse osmosis", "water infrastructure"],
        "waste management": ["waste management", "recycling", "circular economy", "environmental services"],
        "recycling": ["recycling", "waste management", "material recovery", "circular economy"],
        "forestry": ["forestry", "timber", "sustainable forestry", "wood products", "paper mills"],
        "timber": ["timber", "lumber", "wood processing", "forestry"],
        "paper mills": ["paper mills", "pulp and paper", "packaging paper", "cellulose"],
        "agricultural equipment": ["agricultural machinery", "farm equipment", "tractors", "irrigation systems"],
        "dairy": ["dairy farming", "dairy products", "milk processing", "agriculture"],
        "aquaculture": ["aquaculture", "fish farming", "seafood processing", "mariculture"],
        "seafood": ["seafood processing", "fisheries", "aquaculture", "food production"],
        "food and beverage": ["food", "beverage", "food processing", "beverage production"],
        "food": ["food", "food products", "food processing", "food distribution", "beverage"],
        "raw ingredients": ["food ingredients", "raw materials", "agricultural commodities", "food supply"],
        "breweries": ["craft brewery", "beer production", "brewing", "beverages"],
        "wineries": ["winery", "wine production", "vineyards", "beverages"],
        "distilleries": ["distillery", "spirits production", "alcoholic beverages"],
        "bakeries": ["commercial bakery", "baked goods", "frozen dough", "food manufacturing"],
        "frozen dough": ["frozen dough", "bakery supplies", "commercial baking"],
        "solar panel": ["solar panels", "photovoltaic", "solar installation", "renewable energy"],
        "solar inverters": ["solar inverters", "photovoltaic inverters", "solar equipment", "power electronics"],
        "charging station": ["EV charging stations", "charging infrastructure", "electric vehicle supply equipment"],
        "electric vehicle battery": ["electric vehicle battery components", "battery cells", "lithium-ion battery"],
        "battery": ["battery components", "battery cells", "lithium-ion battery", "energy storage"],
        "automotive parts": ["automotive parts", "auto components", "Tier 1 supplier", "vehicle components"],
        "e-commerce": ["e-commerce", "ecommerce", "online retail", "digital storefront"],
        "shopify": ["Shopify", "e-commerce platform", "online store"],
        "aerospace": ["aerospace", "aviation", "space technology", "defense"],
        "defense": ["defense", "military", "aerospace and defense", "security contractor"],
        "robotics": ["robotics", "industrial robots", "automation", "mechatronics"],
        "precision engineering": ["precision engineering", "CNC machining", "industrial manufacturing", "tooling"],
        "industrial automation": ["industrial automation", "robotics", "process automation", "machinery"],
        "automation": ["automation", "process automation", "workflow automation", "industrial automation"],
        "chemical": ["chemicals", "chemical manufacturing", "specialty chemicals", "industrial chemicals"],
        "textile": ["textiles", "fabrics", "apparel manufacturing", "garments"],
        "apparel": ["apparel", "clothing", "fashion", "garment manufacturing"],
        "sustainable fabrics": ["sustainable fabrics", "eco-friendly textiles", "organic fabrics", "textile supply"],
        "skincare": ["skincare", "cosmetics", "beauty products", "personal care"],
        "wellness": ["wellness", "health and wellness", "supplements", "personal care"],
        "cosmetics": ["cosmetics", "beauty", "skincare", "personal care", "makeup"],
        "hospitality": ["hospitality", "hotels", "resort management", "hotel management", "lodging"],
        "resort management": ["resort management", "hospitality management", "hotels and resorts"],
        "hotel management": ["hotel management software", "hospitality", "booking engine"],
        "pet food": ["pet food", "animal nutrition", "pet care", "veterinary products"],
        "veterinary": ["veterinary clinics", "animal hospital", "veterinary products", "animal health"],
        "dental": ["dental implants", "orthodontic equipment", "dental devices", "dentistry"],
        "orthodontic": ["orthodontic equipment", "dental aligners", "dental devices"],
        "ophthalmology": ["ophthalmology clinics", "eye care", "optical lenses", "vision care"],
        "optical lenses": ["optical lenses", "eyewear", "ophthalmic optics", "photon-optics"],
        "car sharing": ["car sharing", "mobility platform", "ride sharing", "fleet sharing"],
        "mobility": ["mobility", "transportation", "urban mobility", "car sharing"],
        "grocery delivery": ["grocery delivery", "on-demand delivery", "q-commerce", "food delivery"],
        "restaurant": ["restaurants", "food service", "dining", "hospitality"],
        "medical clinics": ["medical clinics", "healthcare clinics", "outpatient care", "medical center"],
        "healthcare": ["healthcare", "medical services", "hospitals", "clinics", "health"],
        "mining": ["mining", "mineral extraction", "metals and mining", "mineral processing"],
        "metals": ["metals", "metallurgy", "steel", "metal fabrication"],
        "retail": ["retail", "consumer goods", "stores", "merchandising"],
        "management consulting": ["management consulting", "strategy consulting", "business advisory"],
    }

    _TARGET_MARKETS_KEYWORDS: dict[str, list[str]] = {
        "cosmetics": ["cosmetics", "beauty", "personal care", "skincare"],
        "beauty": ["beauty", "cosmetics", "personal care", "skincare"],
        "direct-to-consumer": ["direct-to-consumer", "DTC", "e-commerce brands"],
        "healthcare": ["healthcare", "medical", "hospitals", "clinics"],
        "vaccine": ["pharmaceuticals", "vaccine distribution", "healthcare", "biotech"],
        "automotive": ["automotive", "electric vehicles", "EV", "vehicles"],
        "electric vehicles": ["electric vehicles", "EV", "automotive"],
        "electric vehicle": ["electric vehicles", "EV", "automotive", "battery production"],
        "banks": ["banking", "financial services", "traditional banks"],
        "financial institutions": ["financial institutions", "banking", "finance", "fintech"],
        "fintechs": ["fintech", "financial services", "digital banking"],
        "law firms": ["law firms", "legal sector", "corporate legal departments", "attorneys"],
        "legal departments": ["corporate legal", "law firms", "legal sector"],
        "retail stores": ["retail stores", "retailers", "merchants", "brick-and-mortar"],
        "supermarkets": ["supermarkets", "grocery stores", "food retail", "hypermarkets"],
        "restaurants": ["restaurants", "hospitality", "food service", "hotels"],
        "hotels": ["hotels", "hospitality", "resorts", "lodging"],
        "warehouse": ["warehouses", "fulfillment centers", "logistics", "supply chain"],
        "trucking": ["trucking", "freight", "delivery firms", "transportation", "logistics"],
        "clothing brands": ["fashion brands", "apparel", "clothing", "retail"],
        "real estate agencies": ["real estate agencies", "property managers", "realtors", "real estate"],
        "biotech research": ["biotech research", "laboratories", "research institutes", "life sciences"],
        "public sector": ["public sector", "government", "municipalities", "state institutions"],
        "public schools": ["public schools", "universities", "education sector", "schools"],
        "universities": ["universities", "higher education", "academic institutions"],
        "freelance": ["freelancers", "independent contractors", "gig economy", "professionals"],
        "residential": ["residential", "homeowners", "consumer"],
        "manufacturing enterprises": ["manufacturing", "industrial enterprises", "factories"],
        "e-commerce marketplaces": ["e-commerce", "online marketplaces", "digital commerce"],
        "smes": ["SMEs", "small and medium enterprises", "small businesses"],
        "engineering": ["engineering firms", "architecture firms", "construction", "industrial design"],
        "architecture firms": ["architecture firms", "architects", "engineering and construction"],
    }

    _STOPWORDS: set[str] = {
        "a", "an", "the", "and", "or", "for", "to", "in", "on", "at", "by", "with",
        "from", "of", "that", "which", "who", "could", "would", "should", "can",
        "company", "companies", "firm", "firms", "business", "businesses", "brand",
        "brands", "looking", "find", "search", "more", "than", "less", "over", "under",
        "using", "similar", "providing", "competing", "critical", "working", "building",
        "producing", "developing", "serving", "offering", "automating", "space", "region",
        "doing", "cool", "stuff", "sized", "sector", "corporations", "organizations",
    }

    def __init__(self, brute_mode: Optional[bool] = None):
        self.brute_mode = brute_mode if brute_mode is not None else (not Config.has_api())

    def process(self, query: Query) -> Query:
        text = query.text
        occupied_spans: list[tuple[int, int]] = []

        # 1. STANDARD HARD-FACTS (Ruleaza MEREU, si cu API si fara API)
        self._extract_is_public(query, text, occupied_spans)
        self._extract_employee_count(query, text, occupied_spans)
        self._extract_revenue(query, text, occupied_spans)
        self._extract_year_founded(query, text, occupied_spans)

        # 2. BRUTE-MODE OVERDRIVE (Ruleaza cand nu avem API Key sau ca fallback la 503)
        if self.brute_mode:
            self._extract_brute_mode_semantics(query, text, occupied_spans)

        return query

    # =========================================================================
    # HELPERE PENTRU SPANS SI OPERATORI
    # =========================================================================

    @staticmethod
    def _is_overlapping(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
        start, end = span
        for o_start, o_end in occupied:
            if max(start, o_start) < min(end, o_end):
                return True
        return False

    @staticmethod
    def _get_unoccupied_text(text: str, occupied: list[tuple[int, int]]) -> str:
        chars = list(text)
        for start, end in occupied:
            for i in range(start, min(end, len(chars))):
                chars[i] = " "
        return "".join(chars)

    @staticmethod
    def _add_matched_condition(
        query: Query,
        occupied: list[tuple[int, int]],
        field: Field,
        operator: Operator,
        value: object,
        span: tuple[int, int],
        confidence: float = 1.0,
    ) -> None:
        if not LocalConditionExtractor._is_overlapping(span, occupied):
            occupied.append(span)
            query.add_condition(
                Condition(
                    field=field,
                    operator=operator,
                    value=value,
                    source="local",
                    confidence=confidence,
                    span=span,
                )
            )

    @staticmethod
    def _parse_operator(op_text: str | None, has_plus: bool = False) -> Operator:
        if has_plus:
            return Operator.GTE
        if not op_text:
            return Operator.EQ

        cleaned = op_text.strip().lower()
        if cleaned in {">=", "at least", "minimum", "min", "no less than", "starting from"}:
            return Operator.GTE
        if cleaned in {">", "more than", "over", "above", "greater than", "exceeding", "beyond", "after", "since", "later than", "newer than"}:
            return Operator.GT
        if cleaned in {"<=", "at most", "maximum", "max", "no more than", "up to"}:
            return Operator.LTE
        if cleaned in {"<", "less than", "fewer than", "under", "below", "before", "prior to", "earlier than", "older than"}:
            return Operator.LT
        return Operator.EQ

    def _parse_number(self, num_str: str, mult_str: str | None = None) -> int:
        clean_num = float(num_str.replace(",", "").strip())
        multiplier = 1
        if mult_str:
            multiplier = self._MULTIPLIERS.get(mult_str.strip().lower(), 1)
        return int(clean_num * multiplier)

    # =========================================================================
    # EXTRACTORI HARD-FACTS (STANDARD MODE)
    # =========================================================================

    def _extract_is_public(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        # Excludem "private equity/label/cloud/network/jet/banking/wealth/security"
        private_pattern = re.compile(
            r"\b(?:non[-\s]?public|not\s+public|unlisted|privately[-\s]+(?:held|owned)|private(?!\s+(?:equity|label|cloud|network|jet|banking|wealth|security)))\b",
            re.IGNORECASE,
        )
        for match in private_pattern.finditer(text):
            self._add_matched_condition(
                query, occupied, Field.IS_PUBLIC, Operator.EQ, False, match.span(), confidence=1.0
            )
            return

        public_pattern = re.compile(
            r"(?<![-\w])(?:publicly[-\s]+(?:traded|listed|open|owned)|stock[-\s]+listed|listed\s+on\s+stock\s+exchange|public(?!\s+(?:relations|sector|health|transport|service|services|opinion|domain|institutions|schools|safety|transit)))\b",
            re.IGNORECASE,
        )
        for match in public_pattern.finditer(text):
            self._add_matched_condition(
                query, occupied, Field.IS_PUBLIC, Operator.EQ, True, match.span(), confidence=1.0
            )
            return

    def _extract_employee_count(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        range_pattern = re.compile(
            r"(?:\b(?:with|having)\s+)?(?:\bbetween\s+)?(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?P<m1>k|thousand)?\s*(?:and|to|-)\s*(?P<high>\d[\d,]*(?:\.\d+)?)\s*(?P<m2>k|thousand)?\s+(?:employees|employee|staff|people|workers|headcount|team\s+members)\b",
            re.IGNORECASE,
        )
        for match in range_pattern.finditer(text):
            span = match.span()
            if not self._is_overlapping(span, occupied):
                low_val = self._parse_number(match.group("low"), match.group("m1"))
                high_val = self._parse_number(match.group("high"), match.group("m2"))
                occupied.append(span)
                query.add_condition(Condition(Field.EMPLOYEE_COUNT, Operator.GTE, low_val, "local", 1.0, span))
                query.add_condition(Condition(Field.EMPLOYEE_COUNT, Operator.LTE, high_val, "local", 1.0, span))
                return

        emp_pattern = re.compile(
            r"(?:\b(?:with|having)\s+)?(?:\ba\s+headcount\s+of\s+)?(?P<op>more\s+than|less\s+than|fewer\s+than|at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|up\s+to|over|under|above|below|greater\s+than|exceeding|minimum|maximum|min|max|>=|<=|>|<|=)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|million)?(?P<plus>\+)?\s+(?:employees|employee|staff|people|workers|team\s+members|headcount)\b",
            re.IGNORECASE,
        )
        for match in emp_pattern.finditer(text):
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.EMPLOYEE_COUNT, op, val, match.span(), confidence=1.0
            )

    def _extract_revenue(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        # Includem minimum, maximum, min, max, no more than, no less than si la revenue!
        rev_prefix_pattern = re.compile(
            r"\b(?:with\s+)?(?:annual\s+|yearly\s+)?(?:revenue|revenues|turnover|sales|arr)\s+(?:of\s+)?(?P<op>more\s+than|less\s+than|fewer\s+than|at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|minimum|maximum|min|max|over|under|above|below|greater\s+than|exceeding|beyond|up\s+to|>=|<=|>|<|=)?\s*(?:[$€£Çú]|usd|eur|gbp)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|mil|million|millions|b|bil|billion|billions)?(?P<plus>\+)?\b",
            re.IGNORECASE,
        )
        for match in rev_prefix_pattern.finditer(text):
            # Evitam confuzia cu "recurring revenue" fara numar
            if not match.group("num"):
                continue
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.REVENUE, op, val, match.span(), confidence=1.0
            )

        rev_suffix_pattern = re.compile(
            r"(?:\b(?:with|making|generating|earning)\s+)?(?P<op>more\s+than|less\s+than|fewer\s+than|at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|minimum|maximum|min|max|over|under|above|below|greater\s+than|exceeding|beyond|up\s+to|>=|<=|>|<|=)?\s*(?P<curr>[$€£Çú]|usd\s*|eur\s*|gbp\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|mil|million|millions|b|bil|billion|billions)?(?P<plus>\+)?\s*(?:in\s+)?(?:annual\s+|yearly\s+)?(?:revenue|revenues|turnover|sales|arr)\b",
            re.IGNORECASE,
        )
        for match in rev_suffix_pattern.finditer(text):
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.REVENUE, op, val, match.span(), confidence=1.0
            )

    def _extract_year_founded(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        year_explicit_pattern = re.compile(
            r"\b(?:founded|established|started|created|launched|incorporated)?\s*(?P<op>after|since|before|prior\s+to|in|on|later\s+than|earlier\s+than|newer\s+than|older\s+than|from|>=|<=|>|<|=)\s+(?P<year>(?:19|20)\d{2})\b"
            r"|\b(?:founded|established|started|created|launched|incorporated)\s+(?P<year_direct>(?:19|20)\d{2})\b",
            re.IGNORECASE,
        )
        for match in year_explicit_pattern.finditer(text):
            year_str = match.group("year") or match.group("year_direct")
            if not year_str:
                continue
            op_str = match.group("op")
            if op_str and op_str.strip().lower() in {"since", "from"}:
                op = Operator.GTE
            else:
                op = self._parse_operator(op_str)
            self._add_matched_condition(
                query, occupied, Field.YEAR_FOUNDED, op, int(year_str), match.span(), confidence=1.0
            )

        bare_year_pattern = re.compile(r"\b(?P<year>19[5-9]\d|20[0-2]\d)\b")
        for match in bare_year_pattern.finditer(text):
            span = match.span()
            if not self._is_overlapping(span, occupied):
                self._add_matched_condition(
                    query, occupied, Field.YEAR_FOUNDED, Operator.EQ, int(match.group("year")), span, confidence=0.85
                )

    # =========================================================================
    # BRUTE-MODE FALLBACK (CAND LIPSESTE CHEIA API SAU PICA CU 503)
    # =========================================================================

    def _extract_brute_mode_semantics(
        self, query: Query, text: str, occupied: list[tuple[int, int]]
    ) -> None:
        # 1. Geografie / Regiuni
        address_values: list[str] = []
        for geo_key in sorted(self._GEO_EXPANSIONS.keys(), key=len, reverse=True):
            expanded_locations = self._GEO_EXPANSIONS[geo_key]
            pattern = re.compile(rf"(?:\b(?:in|from|based\s+in|located\s+in)\s+)?(?:\bthe\s+)?\b{re.escape(geo_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for loc in expanded_locations:
                        if loc not in address_values:
                            address_values.append(loc)

        # Verificam si "US" cu majuscule (ex: "US medtech...") fara sa confundam cu pronumele "us"
        for match in re.finditer(r"\bUS\b", text):
            if not self._is_overlapping(match.span(), occupied):
                occupied.append(match.span())
                for loc in self._GEO_EXPANSIONS["usa"]:
                    if loc not in address_values:
                        address_values.append(loc)

        if address_values:
            query.add_condition(
                Condition(Field.ADDRESS, Operator.IN, address_values, "local", 0.85)
            )

        for_split = re.search(r"\b(?:for|serving|to|working\s+with|competing\s+with)\b", text, re.IGNORECASE)

        # 2. Core Offerings (Industrii specifice primele, iar termenii generici la final)
        offerings_values: list[str] = []
        generic_keys = {"software", "hardware", "retail", "it", "tech", "automation", "electronics"}
        sorted_off_keys = sorted(
            self._OFFERINGS_KEYWORDS.keys(),
            key=lambda k: (k not in generic_keys, len(k)),
            reverse=True,
        )
        for off_key in sorted_off_keys:
            off_expanded = self._OFFERINGS_KEYWORDS[off_key]
            pattern = re.compile(rf"\b{re.escape(off_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                # Daca termenul e dupa "for"/"serving" si e un segment de clienti (ex: "for banks"), il lasam pentru Target Markets!
                if for_split and match.start() >= for_split.start() and off_key in self._TARGET_MARKETS_KEYWORDS:
                    continue
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in off_expanded:
                        if item not in offerings_values:
                            offerings_values.append(item)

        if offerings_values:
            query.add_condition(
                Condition(Field.CORE_OFFERINGS, Operator.IN, offerings_values, "local", 0.85)
            )

        # 3. Target Markets
        tm_values: list[str] = []
        for tm_key in sorted(self._TARGET_MARKETS_KEYWORDS.keys(), key=len, reverse=True):
            tm_expanded = self._TARGET_MARKETS_KEYWORDS[tm_key]
            pattern = re.compile(rf"\b{re.escape(tm_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in tm_expanded:
                        if item not in tm_values:
                            tm_values.append(item)

        if tm_values:
            query.add_condition(
                Condition(Field.TARGET_MARKETS, Operator.IN, tm_values, "local", 0.85)
            )

        # 4. Business Model (Cautam doar inainte de "for"/"serving" ca sa nu luam modelul clientului)
        bm_values: list[str] = []
        bm_limit = for_split.start() if for_split else len(text)

        for bm_key in sorted(self._BUSINESS_MODELS.keys(), key=len, reverse=True):
            bm_expanded = self._BUSINESS_MODELS[bm_key]
            pattern = re.compile(rf"\b{re.escape(bm_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if match.start() < bm_limit and not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in bm_expanded:
                        if item not in bm_values:
                            bm_values.append(item)

        if bm_values:
            query.add_condition(
                Condition(Field.BUSINESS_MODEL, Operator.IN, bm_values, "local", 0.80)
            )

        # 5. Fallback pe cuvintele ramase NEOCUPATE pentru DESCRIPTION
        unoccupied_text = self._get_unoccupied_text(text, occupied).lower()
        remainder_words = re.findall(r"\b(?:3d|ai|it|ev|hr|bi|vr|ar|pr|uav|gis|cad|cam|bpo|[a-z]{3,})\b", unoccupied_text)
        desc_keywords: list[str] = []
        for word in remainder_words:
            if word not in self._STOPWORDS and word not in desc_keywords:
                desc_keywords.append(word)

        for item in offerings_values[:3]:
            if item not in desc_keywords:
                desc_keywords.append(item)

        if desc_keywords:
            query.add_condition(
                Condition(Field.DESCRIPTION, Operator.IN, desc_keywords, "local", 0.70)
            )