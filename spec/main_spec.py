'''
tetron-appstore main spec: the app catalog (ASCAT-*), its publishing and
collection packages (ASPUB-*), the client library (ASCLI-*) and the gates
reconcile.py enforces (CON-AS*).
'''

from libspec import Spec
from . import catalog, publishing, client, constraints

class MainSpec(Spec):
    def modules(self):
        return [catalog, publishing, client, constraints]
