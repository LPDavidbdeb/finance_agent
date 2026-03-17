from ninja import Schema

class RegisterUserIn(Schema):
    first_name: str
    last_name: str
    household_name: str
    email: str
    password: str
