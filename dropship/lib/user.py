
class User():

    def __init__(self, username, password, first, last):
        self.username = username
        self.password = password
        self.first = first
        self.last = last

    @property
    def fullname(self):
        return self.first + " " + self.last

    @property
    def fullname_rev(self):
        return self.last + ", " + self.first
    
    def to_dict(self):
        return {
            "username": self.username,
            "password": self.password,
            "first": self.first,
            "last": self.last,
            "fullname": self.fullname
        }
    
