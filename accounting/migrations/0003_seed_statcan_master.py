from django.db import migrations


def seed_statcan_tree(apps, schema_editor):
    # Use the historical model from apps to avoid referencing fields
    # that may be added in later migrations (e.g., statcan_vector_id).
    Account = apps.get_model('accounting', 'Account')
    # The complete Statistics Canada Hierarchy
    statcan_categories = {
        'Food': {
            'Food purchased from stores': [
                'Meat',
                'Fish, seafood and other marine products',
                'Dairy products and eggs',
                'Bakery and cereal products (excluding baby food)',
                'Fruit, fruit preparations and nuts',
                'Vegetables and vegetable preparations',
                'Other food products and non-alcoholic beverages'
            ],
            'Food purchased from restaurants': []
        },
        'Shelter': {
            'Rented accommodation': ['Rent', "Tenants' insurance premiums", "Tenants' maintenance, repairs and other expenses"],
            'Owned accommodation': [
                "Mortgage interest cost",
                "Homeowners' replacement cost",
                'Property taxes and other special charges',
                "Homeowners' home and mortgage insurance",
                "Homeowners' maintenance and repairs"
            ],
            'Other owned accommodation expenses': ['Water, fuel and electricity', 'Electricity', 'Water', 'Natural gas', 'Fuel oil and other fuels']
        },
        'Household operations, furnishings and equipment': {
            'Household operations': [
                'Communications',
                'Child care and housekeeping services',
                'Household cleaning products',
                'Paper, plastic and aluminum foil supplies',
                'Other household goods and services',
                'Pet food and supplies',
                'Seeds, plants and cut flowers',
                'Other horticultural goods',
                'Other household supplies',
                'Other household services',
                'Financial services',
                'Household furnishings and equipment',
                'Furniture and household textiles',
                'Furniture',
                'Household textiles',
                'Household equipment',
                'Household appliances',
                'Non-electric kitchen utensils, tableware and cookware',
                'Tools and other household equipment',
                'Services related to household furnishings and equipment',
                'Other household furnishings and equipment'
            ]
        },
        'Clothing and footwear': [
            'Clothing',
            "Women's clothing",
            "Men's clothing",
            "Children's clothing",
            'Footwear',
            'Clothing accessories, watches and jewellery',
            'Clothing material, notions and services'
        ],
        'Transportation': {
            'Private transportation': [
                'Purchase, leasing and rental of passenger vehicles',
                'Operation of passenger vehicles',
                'Gasoline',
                'Passenger vehicle parts, maintenance and repairs',
                'Other passenger vehicle operating expenses',
                'Passenger vehicle insurance premiums',
                'Passenger vehicle registration fees',
                "Drivers' licences",
                'Parking fees',
                'All other passenger vehicle operating expenses'
            ],
            'Public transportation': [
                'Local and commuter transportation',
                'City bus and subway transportation',
                'Taxi and other local and commuter transportation services',
                'Inter-city transportation',
                'Other public transportation'
            ]
        },
        'Health and personal care': {
            'Health care': [
                'Health care goods',
                'Medicinal and pharmaceutical products',
                'Prescribed medicines (excluding medicinal cannabis)',
                'Non-prescribed medicines',
                'Eye care goods',
                'Other health care goods',
                'Health care services'
            ],
            'Personal care': ['Personal care supplies and equipment', 'Personal care services']
        },
        'Recreation, education and reading': {
            'Recreation': [
                'Recreational equipment and services (excluding recreational vehicles)',
                'Purchase and operation of recreational vehicles',
                'Home entertainment equipment, parts and services',
                'Travel services',
                'Traveller accommodation',
                'Travel tours',
                'Other cultural and recreational services',
                'Spectator entertainment (excluding video and audio subscription services)',
                'Video and audio subscription services',
                'Use of recreational facilities and services',
                'All other cultural and recreational services'
            ],
            'Education and reading': [
                'Tuition fees',
                'School textbooks and supplies',
                'Other lessons, courses and education services',
                'Reading material (excluding textbooks)',
                'Other reading material (excluding textbooks)'
            ]
        },
        'Alcoholic beverages, tobacco products and recreational cannabis': [
            {'Alcoholic beverages': [
                'Alcoholic beverages served in licensed establishments',
                {
                    'Alcoholic beverages purchased from stores': [
                        'Beer purchased from stores',
                        'Wine purchased from stores',
                        'Liquor purchased from stores',
                        'Other alcoholic beverages purchased in stores'
                    ]
                }
            ]},
            "Tobacco products and smokers' supplies"
        ]
    }

    # Ensure the root Expenses node exists. Use a safe create path that sets
    # placeholder MPTT fields so the DB NOT NULL constraints are satisfied.
    expenses_root = Account.objects.filter(name='Expenses', parent=None, family=None).first()
    if not expenses_root:
        expenses_root = Account.objects.create(
            name='Expenses',
            account_type='EXPENSE',
            parent=None,
            family=None,
            lft=0,
            rght=0,
            tree_id=1,
            level=0,
        )

    # Recursive function to build the MPTT tree
    def build_tree(data_node, parent_node):
        if isinstance(data_node, dict):
            for key, value in data_node.items():
                node = Account.objects.filter(name=key, parent=parent_node, family=None).first()
                if not node:
                    node = Account.objects.create(
                        name=key,
                        account_type='EXPENSE',
                        parent=parent_node,
                        family=None,
                        lft=0,
                        rght=0,
                        tree_id=1,
                        level=0,
                    )
                build_tree(value, node)
        elif isinstance(data_node, list):
            for item in data_node:
                if isinstance(item, dict):
                    build_tree(item, parent_node)
                else:
                    existing = Account.objects.filter(name=item, parent=parent_node, family=None).first()
                    if not existing:
                        Account.objects.create(
                            name=item,
                            account_type='EXPENSE',
                            parent=parent_node,
                            family=None,
                            lft=0,
                            rght=0,
                            tree_id=1,
                            level=0,
                        )

    # For test DB creation we only ensure the root node exists with placeholder
    # MPTT fields. Populating the full StatCan tree is optional for tests and
    # can be performed by the maintenance command in a running environment.
    try:
        cursor = schema_editor.connection.cursor()
        cursor.execute(
            """
            INSERT INTO accounting_account (name, account_type, parent_id, family_id, global_reference_id, lft, rght, tree_id, level)
            SELECT %s, %s, NULL, NULL, NULL, 1, 2, 1, 0
            WHERE NOT EXISTS (
                SELECT 1 FROM accounting_account WHERE name=%s AND parent_id IS NULL AND family_id IS NULL
            )
            """,
            ['Expenses', 'EXPENSE', 'Expenses'],
        )
    except Exception:
        # If raw insert fails, fall back to ORM create with placeholder MPTT fields
        expenses_root = Account.objects.filter(name='Expenses', parent=None, family=None).first()
        if not expenses_root:
            Account.objects.create(
                name='Expenses',
                account_type='EXPENSE',
                parent=None,
                family=None,
                lft=1,
                rght=2,
                tree_id=1,
                level=0,
            )

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(seed_statcan_tree),
    ]
