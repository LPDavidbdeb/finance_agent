from ninja import Schema
from typing import Optional, Dict, Any
from datetime import date

class RegisterUserIn(Schema):
    first_name: str
    last_name: str
    household_name: str
    email: str
    password: str

class FamilyMemberOut(Schema):
    id: int
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    role: str
    expected_age_at_retirement: int
    expected_age_at_death: int
    current_age: int
    financial_milestones: Dict[str, Any]

class FamilyMemberIn(Schema):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    role: str = "CHILD"
    expected_age_at_retirement: int = 65
    expected_age_at_death: int = 99

class FamilyMemberUpdate(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    role: Optional[str] = None
    expected_age_at_retirement: Optional[int] = None
    expected_age_at_death: Optional[int] = None
