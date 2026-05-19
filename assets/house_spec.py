from decimal import Decimal
from typing import List

from .models import HouseAsset, Floor, Room, Window


class WindowNode:
    def __init__(self, model: Window):
        self.model = model

    @property
    def area(self) -> Decimal:
        return self.model.area


class RoomNode:
    def __init__(self, model: Room, load_windows: bool = True):
        self.model = model
        self.windows = [WindowNode(w) for w in model.windows.all()] if load_windows else []

    @property
    def area(self) -> Decimal:
        return self.model.area

    @property
    def window_area(self) -> Decimal:
        total = Decimal('0.00')
        for w in self.windows:
            total += w.area
        return total

    def wall_area(self):
        return self.model.wall_area()


class FloorNode:
    def __init__(self, model: Floor, load_children: bool = True):
        self.model = model
        self.rooms = [RoomNode(r) for r in model.rooms.all()] if load_children else []

    @property
    def total_room_area(self) -> Decimal:
        total = Decimal('0.00')
        for r in self.rooms:
            total += r.area
        return total


class HouseSpec:
    def __init__(self, house: HouseAsset, load_children: bool = True):
        self.house = house
        self.floors = [FloorNode(f) for f in house.floors.all()] if load_children else []

    def total_floor_area(self) -> Decimal:
        total = Decimal('0.00')
        for f in self.floors:
            total += f.total_room_area
        return total

    def summary(self):
        total = self.total_floor_area()
        # Normalize to 2 decimal places for presentation
        total_str = f"{total.quantize(Decimal('0.01'))}"
        return {
            'house': str(self.house),
            'floors': len(self.floors),
            'total_floor_area': total_str,
        }
