"""
Management command: populate_statcan_vectors

Matches EXPENSE Account names against StatCan CPI component names (table 18100004)
and writes the corresponding vector ID into Account.statcan_vector_id.

Run once after the migration, or re-run to refresh after chart-of-accounts changes.

Usage:
    python manage.py populate_statcan_vectors [--dry-run]
"""

from difflib import SequenceMatcher

from django.core.management.base import BaseCommand

from accounting.models import Account


# ---------------------------------------------------------------------------
# Complete name → vector_id mapping derived from scanning StatCan table 18100004
# for Geography = Canada (coordinate prefix "2.").
# Keys are lowercase CPI component names; values are the lowest (primary) vector ID.
# ---------------------------------------------------------------------------

NAME_TO_VECTOR: dict[str, int] = {
    # All-items and major aggregates
    "all-items": 41690973,
    "food": 41690974,
    "food purchased from stores": 41690975,
    "meat": 41690976,
    "fresh or frozen meat (excluding poultry)": 41690977,
    "fresh or frozen beef": 41690978,
    "fresh or frozen pork": 41690979,
    "other fresh or frozen meat (excluding poultry)": 41690980,
    "fresh or frozen poultry": 41690981,
    "fresh or frozen chicken": 41690982,
    "other fresh or frozen poultry": 41690983,
    "processed meat": 41690984,
    "ham and bacon": 41690985,
    "other processed meat": 41690986,
    "fish, seafood and other marine products": 41690987,
    "fish": 41690988,
    "fresh or frozen fish (including portions and fish sticks)": 41690989,
    "canned and other preserved fish": 41690990,
    "seafood and other marine products": 41690991,
    "dairy products and eggs": 41690992,
    "dairy products": 41690993,
    "fresh milk": 41690994,
    "butter": 41690995,
    "cheese": 41690996,
    "ice cream and related products": 41690997,
    "other dairy products": 41690998,
    "eggs": 41690999,
    # Bakery, cereal, fruit, veg…
    "bakery and cereal products (excluding baby food)": 41691000,
    "bakery products": 41691001,
    "bread, rolls and buns": 41691002,
    "cookies and crackers": 41691003,
    "other bakery products": 41691004,
    "cereal products (excluding baby food)": 41691005,
    "rice and rice-based mixes": 41691006,
    "breakfast cereal and other cereal products (excluding baby food)": 41691007,
    "pasta products": 41691008,
    "flour and flour-based mixes": 41691009,
    "fruit, fruit preparations and nuts": 41691010,
    "fresh fruit": 41691011,
    "apples": 41691012,
    "oranges": 41691013,
    "bananas": 41691014,
    "other fresh fruit": 41691015,
    "preserved fruit and fruit preparations": 41691016,
    "fruit juices": 41691017,
    "other preserved fruit and fruit preparations": 41691018,
    "nuts and seeds": 41691019,
    "vegetables and vegetable preparations": 41691020,
    "fresh vegetables": 41691021,
    "potatoes": 41691022,
    "other fresh vegetables": 41691023,
    "preserved vegetables": 41691024,
    "other food products and non-alcoholic beverages": 41691029,
    "sugar and confectionery": 41691030,
    "condiments, spices and vinegars": 41691031,
    "fats and oils": 41691032,
    "coffee and tea": 41691033,
    "food purchased from restaurants": 41691046,
    # Shelter
    "shelter": 41691050,
    "rented accommodation": 41691051,
    "rent": 41691052,
    "tenants' insurance premiums": 41691053,
    "tenants' maintenance, repairs and other expenses": 41691054,
    "owned accommodation": 41691055,
    "mortgage interest cost": 41691056,
    "homeowners' replacement cost": 41691057,
    "property taxes and other special charges": 41691058,
    "homeowners' home and mortgage insurance": 41691059,
    "homeowners' maintenance and repairs": 41691060,
    "other owned accommodation expenses": 41691061,
    "water, fuel and electricity": 41691062,
    "electricity": 41691063,
    "water": 41691064,
    "natural gas": 41691065,
    "fuel oil and other fuels": 41691066,
    "household operations, furnishings and equipment": 41691067,
    "household operations": 41691068,
    "communications": 41691069,
    "child care and housekeeping services": 41691072,
    "household cleaning products": 41691075,
    "paper, plastic and aluminum foil supplies": 41691078,
    "other household goods and services": 41691081,
    "pet food and supplies": 41691082,
    "seeds, plants and cut flowers": 41691083,
    "other horticultural goods": 41691084,
    "other household supplies": 41691085,
    "other household services": 41691086,
    "household furnishings and equipment": 41691087,
    "furniture and household textiles": 41691088,
    "furniture": 41691089,
    "household textiles": 41691093,
    "household equipment": 41691097,
    "household appliances": 41691098,
    "cooking appliances": 41691099,
    "non-electric kitchen utensils, tableware and cookware": 41691103,
    "tools and other household equipment": 41691104,
    "services related to household furnishings and equipment": 41691107,
    "clothing and footwear": 41691108,
    "clothing": 41691109,
    "women's clothing": 41691110,
    "men's clothing": 41691111,
    "children's clothing": 41691112,
    "footwear": 41691113,
    "clothing accessories, watches and jewellery": 41691118,
    "clothing material, notions and services": 41691123,
    # Transportation
    "transportation": 41691128,
    "private transportation": 41691129,
    "purchase, leasing and rental of passenger vehicles": 41691130,
    "passenger vehicle parts, maintenance and repairs": 41691137,
    "gasoline": 41691136,
    "other passenger vehicle operating expenses": 41691140,
    "passenger vehicle insurance premiums": 41691141,
    "passenger vehicle registration fees": 41691142,
    "drivers' licences": 41691143,
    "parking fees": 41691144,
    "all other passenger vehicle operating expenses": 41691145,
    "public transportation": 41691146,
    "local and commuter transportation": 41691147,
    "city bus and subway transportation": 41691148,
    "taxi and other local and commuter transportation services": 41691149,
    "inter-city transportation": 41691150,
    "air transportation": 41691151,
    "rail, highway bus and other inter-city transportation": 41691152,
    "operation of passenger vehicles": 41691135,
    "purchase and operation of recreational vehicles": 41691179,
    # Health
    "health and personal care": 41691153,
    "health care": 41691154,
    "health care goods": 41691159,
    "medicinal and pharmaceutical products": 41691156,
    "prescribed medicines (excluding medicinal cannabis)": 41691157,
    "non-prescribed medicines": 41691158,
    "other health care goods": 41691159,
    "health care services": 41691162,
    "other health care services": 41691162,
    # Personal care
    "personal care": 41691163,
    "personal care supplies and equipment": 41691164,
    "personal care services": 41691169,
    # Recreation, education
    "recreation, education and reading": 41691170,
    "recreation": 41691171,
    "home entertainment equipment, parts and services": 41691184,
    "use of recreational facilities and services": 41691196,
    "other cultural and recreational services": 41691193,
    "spectator entertainment (excluding video and audio subscription services)": 41691194,
    "video and audio subscription services": 41691195,
    "travel services": 41691190,
    "traveller accommodation": 41691191,
    "travel tours": 41691192,
    "education and reading": 41691197,
    "education": 41691198,
    "tuition fees": 41691199,
    "reading material (excluding textbooks)": 41691202,
    # Tobacco/alcohol
    "tobacco products and smokers' supplies": 41691207,
    "alcoholic beverages purchased from stores": 41691212,
    "alcoholic beverages, tobacco products and recreational cannabis": 41691209,
}

# Manual overrides for accounts whose names don't exactly match CPI but are clear maps
MANUAL_OVERRIDES: dict[str, int] = {
    "tenants insurance premiums": 41691053,           # missing apostrophe
    "all other cultural and recreational services": 41691193,
    "other reading material (excluding textbooks)": 41691202,
    "other household furnishings and equipment": 41691087,
    "other public transportation": 41691146,
    "other alcoholic beverages purchased in stores": 41691212,
    # ELECTRICITY / AIR TRANSPORTATION — uppercase variants
    "electricity": 41691063,
    "air transportation": 41691151,
    "rail, highway bus and other inter-city transportation": 41691152,
}


def _resolve(name: str) -> int | None:
    key = name.lower().strip()
    if key in NAME_TO_VECTOR:
        return NAME_TO_VECTOR[key]
    if key in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[key]
    # Fuzzy fallback (threshold 0.90) — only for near-identical strings
    best_score, best_vid = 0.0, None
    for candidate, vid in {**NAME_TO_VECTOR, **MANUAL_OVERRIDES}.items():
        score = SequenceMatcher(None, key, candidate).ratio()
        if score > best_score:
            best_score, best_vid = score, vid
    if best_score >= 0.90:
        return best_vid
    return None


class Command(BaseCommand):
    help = "Populate Account.statcan_vector_id from the StatCan CPI table 18100004."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print matches without writing to the database."
        )
        parser.add_argument(
            "--overwrite", action="store_true",
            help="Overwrite accounts that already have a vector ID set."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]

        qs = Account.objects.filter(account_type=Account.AccountType.EXPENSE)
        if not overwrite:
            qs = qs.filter(statcan_vector_id__isnull=True)

        updated, skipped = 0, 0
        for account in qs:
            vid = _resolve(account.name)
            if vid is None:
                skipped += 1
                if options["verbosity"] >= 2:
                    self.stdout.write(f"  NO MATCH  {account.name!r}")
                continue
            if dry_run:
                self.stdout.write(f"  MATCH     {account.name!r} → v{vid}")
            else:
                Account.objects.filter(pk=account.pk).update(statcan_vector_id=vid)
            updated += 1

        verb = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {updated} account(s). Skipped {skipped} (no CPI match)."
            )
        )
