from dataclasses import dataclass

@dataclass(slots=True)
class People:
    admins: list[int] = []
    bad_users: list[int] = []
