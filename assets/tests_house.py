from decimal import Decimal
from django.test import TestCase

from users.models import Family
from accounting.models import Account
from assets.models import TangibleAsset, HouseAsset, Floor, Room, Window
from assets.house_spec import HouseSpec


class HouseModelSpecTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='House Family')
        self.asset_account = Account.objects.create(
            name='Property', account_type=Account.AccountType.ASSET, family=self.family
        )
        self.t_asset = TangibleAsset.objects.create(
            family=self.family,
            account=self.asset_account,
            name='Family Home',
            purchase_value=Decimal('300000.00'),
            current_market_value=Decimal('320000.00')
        )
        self.house = HouseAsset.objects.create(tangible_asset=self.t_asset, address='123 Demo St')

        # Floor 1 with two rooms
        self.floor1 = Floor.objects.create(house=self.house, floor_number=1, name='Main')
        self.room1 = Room.objects.create(floor=self.floor1, name='Living Room', length=Decimal('5.00'), width=Decimal('4.00'), height=Decimal('2.5'))
        self.room2 = Room.objects.create(floor=self.floor1, name='Kitchen', length=Decimal('3.00'), width=Decimal('2.50'), height=Decimal('2.5'))

        # Windows in living room
        Window.objects.create(room=self.room1, height=Decimal('1.2'), width=Decimal('1.5'), quantity=2)

        # Floor 2 with one room
        self.floor2 = Floor.objects.create(house=self.house, floor_number=2, name='Upstairs')
        self.room3 = Room.objects.create(floor=self.floor2, name='Bedroom', length=Decimal('4.00'), width=Decimal('3.00'), height=Decimal('2.5'))

    def test_room_and_floor_areas(self):
        # Room areas
        self.assertEqual(self.room1.area, Decimal('20.00'))
        self.assertEqual(self.room2.area, Decimal('7.50'))
        self.assertEqual(self.room3.area, Decimal('12.00'))

        # Floor totals
        self.assertEqual(self.floor1.total_room_area(), Decimal('27.50'))
        self.assertEqual(self.floor2.total_room_area(), Decimal('12.00'))

    def test_window_areas_and_wall(self):
        # Window area in living room: 1.5*1.2*2 = 3.6
        windows = self.room1.windows.all()
        # We created a single Window record with quantity=2. Assert total quantity.
        total_qty = sum([w.quantity for w in windows])
        self.assertEqual(total_qty, 2)
        total_window_area = sum([w.area for w in windows])
        self.assertEqual(total_window_area, Decimal('3.60'))

        # Wall area: perimeter * height = 2*(5+4)*2.5 = 45.0
        self.assertEqual(self.room1.wall_area(), Decimal('45.00'))

    def test_house_spec_summary(self):
        spec = HouseSpec(self.house)
        summary = spec.summary()
        self.assertEqual(summary['floors'], 2)
        self.assertEqual(summary['total_floor_area'], '39.50')
