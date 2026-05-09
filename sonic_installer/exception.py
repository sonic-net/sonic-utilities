"""
Module sonic-installer exceptions
"""

class SonicRuntimeException(Exception):
    """SONiC Runtime Excpetion class used to report SONiC related errors
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.notes = []

    def __str__(self):
        msg = super().__str__()
        if self.notes:
            msg += "\n" + "\n".join(self.notes)
        return msg

    def add_note(self, note):
        self.notes.append(note)
