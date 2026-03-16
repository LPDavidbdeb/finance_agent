from django.db import migrations
from accounting.models import Account  # Direct import to preserve MPTT logic

def seed_statcan_tree(apps, schema_editor):
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

    # Ensure the root Expenses node exists
    expenses_root, _ = Account.objects.get_or_create(
        name='Expenses', 
        account_type='EXPENSE', 
        parent=None, 
        family=None
    )

    # Recursive function to build the MPTT tree
    def build_tree(data_node, parent_node):
        if isinstance(data_node, dict):
            for key, value in data_node.items():
                node, _ = Account.objects.get_or_create(
                    name=key, 
                    account_type='EXPENSE', 
                    parent=parent_node, 
                    family=None
                )
                build_tree(value, node)
        elif isinstance(data_node, list):
            for item in data_node:
                if isinstance(item, dict):
                    build_tree(item, parent_node)
                else:
                    Account.objects.get_or_create(
                        name=item, 
                        account_type='EXPENSE', 
                        parent=parent_node, 
                        family=None
                    )

    # Execute the build
    build_tree(statcan_categories, expenses_root)

    # CRITICAL: Force django-mptt to calculate the left/right tree mathematics
    Account.objects.rebuild()

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_account_global_reference'),
    ]

    operations = [
        migrations.RunPython(seed_statcan_tree),
    ]
