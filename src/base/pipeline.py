import os

from src.query.query import Query
from src.query.local import LocalConditionExtractor
from src.query.call import APIConditionExtractor
from src.base.config import Config

class QueryQualificationPipeline:
    """
    'Mother class' that orchestrates the condition grepping phases:
    Initial Query -> Phase 1 (Local Agent) -> Phase 2 (API Call + Phantom Conditions).
    """

    def __init__(self):
        if not Config.has_api():
            print("\n" + "!" * 70)
            print("! AVERTISMENT: GEMINI_API_KEY was not found")
            print("! RUNNING ON BRUTE-MODE (WITHOUT API CALL).")
            print("!" * 70 + "\n")
        
        self.phase1 = LocalConditionExtractor()
        self.phase2 = APIConditionExtractor()

    def run(self, raw_query: str) -> Query:
        """Runs the full condition extraction pipeline on a user query string."""
        query = Query(text=raw_query)

        # Phase 1: Local deterministic extraction (currently TODO passthrough)
        query = self.phase1.process(query)

        # Phase 2: API intelligent extraction + Phantom conditions for unmentioned fields
        query = self.phase2.process(query)

        return query


if __name__ == "__main__":
    # Mic test rapid pe 2 query-uri din enunț (unul structurat, unul de ecosistem)
    pipeline = QueryQualificationPipeline()

    test_queries = [
    "Logistic companies in Romania",
    "Public software companies with more than 1,000 employees.",
    "Food and beverage manufacturers in France",
    "Companies that could supply packaging materials for a direct-to-consumer cosmetics brand",
    "Construction companies in the United States with revenue over $50 million",
    "Pharmaceutical companies in Switzerland",
    "B2B SaaS companies providing HR solutions in Europe",
    "Clean energy startups founded after 2018 with fewer than 200 employees",
    "Fast-growing fintech companies competing with traditional banks in Europe.",
    "E-commerce companies using Shopify or similar platforms",
    "Renewable energy equipment manufacturers in Scandinavia",
    "Companies that manufacture or supply critical components for electric vehicle battery production",
    
    "Logistics companies in Romania",
    "Software companies in the DACH region",
    "Fintech startups in Benelux",
    "Manufacturing firms in Central and Eastern Europe",
    "Cybersecurity companies in the Baltics",
    "E-commerce brands in the Nordics",
    "Biotech companies in Switzerland",
    "Automotive suppliers in Germany and Austria",
    "Cloud computing companies in the UK",
    "AI startups in the United States",
    "Telecommunications companies in Spain and Italy",
    "Clean energy firms in Canada",
    "Semiconductor manufacturers in Asia",
    "AgriTech companies in Latin America",
    "Marine shipping companies in Greece and Cyprus",

    # --- 16-30: Numere, Angajati, Venituri & Ani (Formate variate) ---
    "Public software companies with more than 1,000 employees",
    "Construction companies in the United States with revenue over $50 million",
    "Clean energy startups founded after 2018 with fewer than 200 employees",
    "Private healthcare companies with between 50 and 250 employees",
    "Retail companies with annual sales exceeding €100M",
    "Manufacturing firms established before 1995 with 500+ staff",
    "SaaS startups founded in 2021 with under 50 people",
    "Publicly traded banks with revenue above $1 billion",
    "Privately held logistics firms with 100-500 workers",
    "Tech companies started since 2019 with at least 20 team members",
    "Insurance companies generating over £25 million in yearly revenue",
    "Non-public biotech firms founded prior to 2015",
    "Wholesale distributors with a headcount of at least 1,500 employees",
    "Consulting agencies with turnover under $10M",
    "Unlisted hardware manufacturers established in 2010",

    # --- 31-50: Industrii & Verticale Noi (Testare dictionar _OFFERINGS) ---
    "EdTech companies providing online learning platforms in Europe",
    "MedTech manufacturers producing diagnostic medical devices",
    "PropTech startups building real estate management software",
    "InsurTech companies automating claims processing",
    "LegalTech SaaS solutions for law firms and corporate legal departments",
    "AgriTech companies developing smart farming and irrigation sensors",
    "Aerospace and defense contractors in the United States",
    "Industrial robotics and automation manufacturers in Germany",
    "Video game development studios in Poland",
    "Digital marketing and SEO agencies in the UK",
    "Cloud infrastructure and hosting providers in France",
    "Data analytics and business intelligence software companies",
    "3D printing and additive manufacturing companies",
    "Chemical manufacturing companies in Belgium and Netherlands",
    "Textile and apparel manufacturers in Italy",
    "Hospitality and hotel management software providers",
    "IoT and embedded systems developers in Sweden",
    "Blockchain and cryptocurrency exchanges in Switzerland",
    "Event management and ticketing platforms",
    "Pet food and veterinary products manufacturers",

    # --- 51-70: Ecosistem, Supply Chain & Relatii B2B/B2C ---
    "Companies that could supply packaging materials for a direct-to-consumer cosmetics brand",
    "Companies that manufacture or supply critical components for electric vehicle battery production",
    "Suppliers of raw ingredients for food and beverage manufacturers in France",
    "Contract manufacturers for pharmaceutical companies in Europe",
    "Companies providing cold chain logistics for vaccine distribution",
    "Hardware vendors supplying POS terminals to retail stores and restaurants",
    "Software vendors building ERP systems for manufacturing enterprises",
    "Companies that supply solar inverters for residential renewable energy installations",
    "B2B payment gateway providers for e-commerce marketplaces",
    "Companies manufacturing microchips for automotive electronics",
    "Packaging automation machinery suppliers for warehouse fulfillment centers",
    "Cybersecurity consultancies serving financial institutions and banks",
    "Companies providing fleet management software for trucking and delivery firms",
    "Suppliers of sustainable fabrics for fast-fashion clothing brands",
    "Companies offering KYC and identity verification solutions for fintechs",
    "Manufacturers of laboratory equipment for biotech research institutes",
    "IT outsourcing and staff augmentation companies in Romania",
    "Companies providing CRM software for real estate agencies",
    "Wholesale food distributors supplying hotels and restaurants",
    "Companies building charging station infrastructure for electric vehicles",

    # --- 71-85: Modele de Business & Cuvinte Contextuale ---
    "B2B SaaS companies providing HR solutions in Europe",
    "Fast-growing fintech companies competing with traditional banks in Europe",
    "E-commerce companies using Shopify or similar platforms",
    "Direct-to-consumer skincare and wellness brands in the US",
    "B2G software contractors working with public sector institutions",
    "Subscription box companies in the food and beverage space",
    "Two-sided marketplace platforms for freelance professionals",
    "Franchise restaurant chains in the United Kingdom",
    "Dropshipping and print-on-demand e-commerce platforms",
    "Open-source enterprise software companies founded after 2016",
    "White-label cosmetics manufacturers in Italy",
    "Peer-to-peer car sharing and mobility platforms",
    "On-demand grocery delivery startups in Western Europe",
    "Boutique management consulting firms with fewer than 100 employees",
    "Value-added resellers of enterprise cybersecurity hardware",

    # --- 86-100: Edge Cases (Scurte, fara cuvinte de legatura, combinatii grele) ---
    "Renewable energy equipment manufacturers in Scandinavia",
    "Pharmaceutical companies in Switzerland",
    "Food and beverage manufacturers in France",
    "Romanian software outsourcing 2015 100+ employees",
    "Publicly open telecommunications companies in Balkans",
    "Non-Public cybersecurity startups in Israel with under 150 staff",
    "German automotive 1000+ employees revenue > 100M",
    "French AI startups 2020",
    "Public cloud security companies in USA with over $200M ARR",
    "Private medical clinics in Bucharest and Cluj",
    "Solar panel installers in Spain with 50 to 200 workers",
    "B2B logistics SaaS founded since 2017",
    "UK fintech 2019 < 50 employees",
    "Publicly listed mining and metals companies in Australia",
    "Enterprise data warehousing software with revenue of at least $25 million",
    "Semiconductor foundry companies in Taiwan and South Korea",
    "Robotics and precision engineering manufacturers in Japan",
    "IT consulting and BPO firms in India with over 5,000 employees",
    "Fintech and digital payments startups in Brazil and Mexico",
    "Oil and gas equipment suppliers in the UAE and Saudi Arabia",
    "Mining and mineral processing companies in South Africa",
    "Textile and garment exporters in Turkey",
    "Renewable energy developers in Portugal and Ireland",
    "Automotive parts manufacturers in Czechia and Slovakia",
    "Software development agencies in Hungary and Bulgaria",
    "Maritime and shipbuilding companies in Croatia and Slovenia",
    "Agricultural equipment distributors in Serbia and Ukraine",
    "Wealth management and private banking firms in Singapore and Hong Kong",
    "AgriTech and dairy farming companies in New Zealand",
    "E-commerce logistics providers in the MENA region",
    "Telecommunications infrastructure vendors in Sub-Saharan Africa",
    "Pharmaceutical distributors in the ASEAN region",
    "Hospitality and resort management companies in the Iberian Peninsula",
    "Consumer electronics brands in China and Vietnam",
    "CleanTech startups in Argentina, Chile, and Colombia",

    # --- 121-140: Formate Numerice Grele (Zecimale, Simboluri Lipite, K/M/B, Intervale Scurte) ---
    "Enterprise SaaS companies with ARR >= $1.5B",
    "Boutique design agencies with <25 employees and turnover under €2.5 million",
    "Publicly listed retail chains with >10,000 workers",
    "Manufacturing companies with 1.5k to 5k employees",
    "Biotech firms founded in 2014 with at most 120 staff",
    "Logistics providers making at least £75.5M in annual sales",
    "Hardware startups started after 2022 with no more than 30 people",
    "Private construction firms with 250-1,000 employees and revenue > $120M",
    "Financial services companies established prior to 1980 with 2,000+ headcount",
    "Cybersecurity vendors with between 300 and 800 team members",
    "Food processing plants with yearly revenue exceeding $500 thousand",
    "Cloud software companies founded since 2016 generating over €15M ARR",
    "Unlisted pharmaceutical companies with minimum 400 employees",
    "Wholesale electronics distributors with maximum $50M turnover",
    "Non-public insurance brokers with 50+ staff established in 1998",
    "B2B marketplace startups 2021 <= 40 employees",
    "Public aerospace contractors > 5000 employees > $2B revenue",
    "German chemical manufacturers 1975 1000-3000 workers",
    "UK legaltech 2018 >= 15 employees < £5M sales",
    "US medtech founded before 2012 with revenue of at least $80.5 million",

    # --- 141-160: Capcane "Public" vs "Private" (False Positives Test) ---
    "Public relations and corporate communications agencies in London",
    "Private label food and cosmetics manufacturers in Poland",
    "Private equity and venture capital firms investing in European tech",
    "Companies building private cloud infrastructure for banks",
    "Public health consulting and epidemiology research organizations",
    "Public transport ticketing and fleet management systems in Europe",
    "Public safety and emergency response software providers in the US",
    "Private jet charter and business aviation operators in Switzerland",
    "Privately owned public relations firms with under 100 employees",
    "Publicly traded private equity firms in the United States",
    "Companies working with public schools and universities in Canada",
    "Private security guard and facility patrol services in France",
    "Public opinion polling and market research agencies",
    "Private wealth management advisories in Zurich and Geneva",
    "Not public software companies serving public sector clients",

    # --- 161-180: Industrii Grele, Fizice, Traditii & Nise Specifice ---
    "HVAC and industrial cooling equipment manufacturers in Italy",
    "Elevator and escalator maintenance companies in Germany",
    "Commercial printing and corrugated cardboard packaging suppliers",
    "Industrial plastics, polymers, and rubber manufacturers in Benelux",
    "Glass and ceramic building materials producers in Spain",
    "Craft breweries, wineries, and artisanal distilleries in France",
    "Commercial bakeries and frozen dough suppliers for supermarkets",
    "Aquaculture, fish farming, and seafood processing companies in Norway",
    "Sustainable forestry, timber, and paper mills in Finland and Sweden",
    "Waste management, recycling, and circular economy companies in Europe",
    "Water treatment and desalination plant contractors in Israel",
    "Green hydrogen and biofuel production companies in the Nordics",
    "Railway rolling stock and signaling equipment manufacturers",
    " Unmanned aerial vehicles (UAV) and commercial drone manufacturers",
    "Avionics and satellite communications hardware suppliers",
    "Tire and automotive rubber components manufacturers",
    "Office furniture and commercial interior fit-out manufacturers in Romania",
    "Dental implants and orthodontic equipment manufacturers in DACH",
    "Ophthalmology clinics and optical lenses manufacturers",
    " Veterinary clinics and animal hospital chains in the UK",

    # --- 181-200: Query-uri Neconcludente, Ambigue, Jargon de Business & Edge Cases ---
    "Fast-growing companies doing cool stuff with data and automation",
    "Medium-sized businesses looking for digital transformation",
    "Profitable legacy corporations in the industrial sector",
    "Next-gen disruptive platforms in the creator economy",
    "High-margin B2B service providers with recurring revenue",
    "RegTech and compliance automation software for financial institutions",
    "MarTech and AdTech platforms for programmatic advertising",
    "GovTech solutions digitizing municipal services and local administration",
    "SpaceTech startups developing nanosatellites and launch vehicles",
    "Quantum computing and photonics research companies",
    "Nanotechnology and advanced materials startups founded after 2017",
    "CAD/CAM software developers for engineering and architecture firms",
    "GIS, geospatial mapping, and satellite imagery analytics providers",
    "VoIP, unified communications, and contact center software vendors",
    "Data center colocation and bare-metal server hosting providers",
    "E-sports organizations and competitive gaming platforms",
    "Audio streaming, podcasting, and music licensing platforms",
    "Translation, localization, and interpreting agencies in Europe",
    "Accounting, tax preparation, and bookkeeping firms for SMEs",
    "Executive search, headhunting, and recruitment agencies in Bucharest",
    ]

    for q_text in test_queries:
        print("=" * 70)
        result_query = pipeline.run(q_text)
        print(f"QUERY: {result_query.text}\n")

        print("-> CONDITII ACTIVE (Ce cautam in baza de date):")
        for c in result_query.active_conditions:
            print(f"   [{c.source.upper()}] {c.field.value} {c.operator.value} {c.value} (conf={c.confidence:.2f})")

        print("\n-> CONDITII FANTOMA (Campuri marcate ca neimportante):")
        for c in result_query.phantom_conditions:
            print(f"   [PHANTOM] {c.field.value} -> {c.operator.value}")