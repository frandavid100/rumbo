"""Run the conservative Mercadona first-party probe against the official v1_1 API.

The unversioned category-detail endpoints currently return 404 from GitHub-hosted
runners, while Mercadona's official versioned catalogue endpoints remain readable.
Keep the extraction/provenance logic in mercadona_first_party_probe.py unchanged.
"""

import mercadona_first_party_probe as probe

probe.API_ROOT = "https://tienda.mercadona.es/api/v1_1"

if __name__ == "__main__":
    raise SystemExit(probe.main())
