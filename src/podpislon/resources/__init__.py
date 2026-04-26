"""Resource modules — one per API tag."""

from podpislon.resources.company import CompanyResource
from podpislon.resources.documents import DocumentsResource
from podpislon.resources.payments import PaymentsResource

__all__ = ["CompanyResource", "DocumentsResource", "PaymentsResource"]
