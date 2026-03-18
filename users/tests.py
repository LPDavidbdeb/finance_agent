from django.test import TestCase
from datetime import date
from users.models import Family, FamilyMember

class FamilyMemberTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Test Family")

    def test_current_age(self):
        """Test age calculation logic."""
        today = date.today()
        # Person born exactly 20 years ago
        member = FamilyMember(
            family=self.family,
            first_name="John",
            last_name="Doe",
            date_of_birth=date(today.year - 20, today.month, today.day),
            sex="M",
            role="PARENT"
        )
        self.assertEqual(member.current_age, 20)
        
        # Person born 20 years ago + 1 day (birthday tomorrow)
        # Handle cases where today is Feb 29
        try:
            dob = date(today.year - 20, today.month, today.day + 1)
        except ValueError:
            # If today is end of month, go to next month
            dob = date(today.year - 20, today.month + 1, 1)
            
        member.date_of_birth = dob
        self.assertEqual(member.current_age, 19)

    def test_financial_milestones_child(self):
        """Test milestones for a child."""
        # Born in 2010-05-15
        member = FamilyMember(
            family=self.family,
            first_name="Kid",
            last_name="Doe",
            date_of_birth=date(2010, 5, 15),
            sex="F",
            role="CHILD"
        )
        
        milestones = member.financial_milestones
        # Age 15 in 2025. Resp deadline is Dec 31, 2025.
        self.assertEqual(milestones['resp_grant_deadline'], date(2025, 12, 31))
        # TFSA on 18th birthday: 2028-05-15
        self.assertEqual(milestones['tfsa_eligibility'], date(2028, 5, 15))

    def test_financial_milestones_parent(self):
        """Test milestones for a parent."""
        # Born in 1980-05-15
        member = FamilyMember(
            family=self.family,
            first_name="Parent",
            last_name="Doe",
            date_of_birth=date(1980, 5, 15),
            sex="M",
            role="PARENT",
            expected_age_at_retirement=60
        )
        
        milestones = member.financial_milestones
        # Planned retirement at age 60: 2040-05-15
        self.assertEqual(milestones['planned_retirement'], date(2040, 5, 15))
        # RRSP to RRIF at age 71: 2051. Deadline Dec 31, 2051.
        self.assertEqual(milestones['rrsp_to_rrif_deadline'], date(2051, 12, 31))
