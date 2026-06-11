"""
Patch SSL verification for environments with self-signed proxy certificates
(e.g., corporate VPNs, GitHub Codespaces network inspection).

Must be imported BEFORE yfinance and curl_cffi to take effect.
"""

import os
import ssl
import warnings

# Python ssl module — for urllib/httpx
ssl._create_default_https_context = ssl._create_unverified_context

# requests library env vars
os.environ.setdefault("PYTHONHTTPSVERIFY", "0")

# Suppress InsecureRequestWarning from urllib3/requests
try:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# curl_cffi — used by yfinance 1.x
# Monkey-patch Session.__init__ so verify=False is the default for every session
try:
    import curl_cffi.requests as _cffi_req

    _orig_init = _cffi_req.Session.__init__

    def _patched_init(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        _orig_init(self, *args, **kwargs)

    _cffi_req.Session.__init__ = _patched_init
except Exception:
    pass

warnings.filterwarnings("ignore", message="Unverified HTTPS request")
